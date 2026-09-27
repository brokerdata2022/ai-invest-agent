#!/usr/bin/env python3
"""
LLM знаходить нові перспективні акції з general-потоку новин
(docs/news-purpose.md, "Ціль 3") — активи, яких ще немає в S&P 500
universe скринінгу. Рішення користувача (2026-09-27): LLM сам відбирає
кандидатів прямо з промпту (не Tier A/B/C перепрогін), єдина тверда
вимога — акція має бути РЕАЛЬНО торгованою, не вигадкою LLM і не
приватним стартапом/чуткою про IPO.

"Реально торгована" перевіряється ДЕТЕРМІНОВАНО, не на слово LLM:
Twelve Data (уже наше джерело живих цін) повинна повернути ≥2
спостереження для тикера (verify_tradable() нижче) — інакше кандидат
відкидається. "Ще немає в наших списках" — звірка з живим S&P 500
universe (collect_universe.py:fetch_sp500_constituents()).

Формат виходу — analysis/CLAUDE.md "Формат виходу LLM-аналізу":
summary/direction/confidence не застосовні тут (це не сигнал по вже
відстежуваному активу, а список нових імен) — мінімум полів адаптовано
під задачу: ticker/company_name/reasoning на кожного кандидата.
Заборона "купити/продати" — та сама, що в решті LLM-скриптів.

Свідома спрощеність (docs/decisions.md, 2026-09-27): "поточний список"
кандидатів ротується за СВІЖІСТЮ (10 найновіших унікальних тикерів),
не за порівняльним рангом — користувач попросив покластись на
LLM-відбір, не будувати composite-score-подібний критерій для
кандидатів.

Використання:
    python discover_candidates.py
    python discover_candidates.py --max-age-days 3 --top 5
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_INGESTION_DIR = os.path.join(_ANALYSIS_DIR, "..", "data-ingestion")
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, _DATA_INGESTION_DIR)

from collect_universe import fetch_sp500_constituents  # noqa: E402
from common.db import get_connection, insert_observations  # noqa: E402
from quotes.twelvedata_adapter import TwelveDataAdapter  # noqa: E402

from news_analysis._db import fetch_relevant_for_aggregation, log_llm_call, save_candidate  # noqa: E402
from news_analysis.aggregate import NewsCluster, cluster_articles, top_clusters  # noqa: E402
from news_analysis.deepseek_client import call_deepseek  # noqa: E402
from news_analysis.prices import PriceChange, fetch_price_change  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Не CLI-прапорець — стрім general навмисно обраний як найширший
# фінансовий контекст без прив'язки до активу (geopolitical — вузький
# курований набір тем, малоймовірно містить нові тикери).
STREAM = "general"

LLM_PROVIDER = os.environ.get("SYNTHESIS_LLM_PROVIDER", "deepseek")

SYSTEM_PROMPT = (
    "Ти аналітик, що шукає нові інвестиційні ідеї серед фінансових "
    "новин. Тобі дають найбільш підтверджені (кількома незалежними "
    "джерелами) історії за вікно."
    "\n\n"
    "Запропонуй 3-5 РЕАЛЬНИХ, конкретних, публічно торгованих акцій "
    "(є на біржі, доступні через популярні брокери), які виглядають "
    "перспективними на основі цих новин. КРИТИЧНО: тільки реальні "
    "тикери реальних публічних компаній — НІКОЛИ не вигадуй тикер. "
    "НІКОЛИ не пропонуй приватні стартапи, чутки про майбутнє IPO, "
    "криптовалюти чи компанії зі списку 'вже відстежуємо' нижче. Якщо "
    "жодна новина не вказує на конкретну нову публічну компанію — "
    "поверни порожній список candidates, це нормальний результат."
    "\n\n"
    "НІКОЛИ не давай прямих торгових рекомендацій ('купити'/'продати'/"
    "'входити в позицію') — тільки описове обґрунтування, чому компанія "
    "привертає увагу. Відповідай ЛИШЕ JSON-об'єктом з полем "
    "'candidates' — списком об'єктів з полями: ticker (тикер біржі, "
    "напр. NVDA), company_name (повна назва), reasoning (коротке "
    "обґрунтування на основі новин)."
)


class CandidateResponseError(ValueError):
    pass


def build_prompt(clusters: list[NewsCluster], already_tracked: list[str]) -> str:
    lines = [
        f"Уже відстежуємо (НЕ пропонувати ці тикери): {', '.join(sorted(already_tracked))}",
        "",
        f"Найбільш підтверджені історії за вікно ({len(clusters)}):",
    ]
    for c in clusters:
        lines.append(f"- [{c.source_count} джерел] {c.representative_title}")
        if c.summaries:
            lines.append(f"  → {c.summaries[0]}")
    return "\n".join(lines)


def parse_response(raw_content: str) -> list[dict]:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise CandidateResponseError(
            f"Відповідь LLM не є коректним JSON: {raw_content!r}"
        ) from e

    candidates = data.get("candidates")
    if candidates is None:
        raise CandidateResponseError(f"У відповіді LLM бракує поля 'candidates': {data!r}")
    if not isinstance(candidates, list):
        raise CandidateResponseError(f"'candidates' має бути списком: {candidates!r}")

    for c in candidates:
        missing = [f for f in ("ticker", "company_name", "reasoning") if not c.get(f)]
        if missing:
            raise CandidateResponseError(f"Кандидату бракує полів {missing}: {c!r}")

    return candidates


def call_llm(prompt: str, system_prompt: str, api_key: str) -> str:
    if LLM_PROVIDER == "deepseek":
        return call_deepseek(prompt, api_key=api_key, system_prompt=system_prompt)
    raise ValueError(
        f"Непідтримуваний SYNTHESIS_LLM_PROVIDER={LLM_PROVIDER!r} — наразі реалізовано "
        "лише 'deepseek' (Anthropic-клієнт з'явиться разом зі свідомим переходом, "
        "docs/decisions.md, 2026-09-27)."
    )


def verify_tradable(conn, ticker: str, twelvedata_api_key: str) -> Optional[PriceChange]:
    """Детермінована перевірка "реально торгується" — LLM пропонує,
    Twelve Data підтверджує (чи ні). Повертає PriceChange, якщо тикер
    реальний і має ≥2 спостереження ціни; None — якщо тикер вигаданий/
    невідомий Twelve Data, чи (поки що) без достатньої історії."""
    try:
        records = TwelveDataAdapter(api_key=twelvedata_api_key, ticker=ticker).collect(limit=10)
    except (ValueError, requests.exceptions.RequestException):
        logger.info("%s: Twelve Data не визнає тикер — відкинуто", ticker)
        return None

    if not records:
        return None
    insert_observations(conn, records)
    return fetch_price_change(conn, ticker, days=30)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--top", type=int, default=8, help="скільки найбільш підтверджених історій урахувати")
    args = parser.parse_args()

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY") if LLM_PROVIDER == "deepseek" else None
    if LLM_PROVIDER == "deepseek" and not deepseek_key:
        logger.error("DEEPSEEK_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    twelvedata_key = os.environ.get("TWELVEDATA_API_KEY")
    if not twelvedata_key:
        logger.error("TWELVEDATA_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    conn = get_connection()
    try:
        articles = fetch_relevant_for_aggregation(conn, stream=STREAM, max_age_days=args.max_age_days)
        clusters = cluster_articles(articles)
        top = top_clusters(clusters, limit=args.top)
        logger.info("%d кластерів усього, %d найбільш підтверджених урахуємо", len(clusters), len(top))

        if not top:
            logger.info("Немає general-кластерів за вікно — нічого пропонувати")
            return

        already_tracked = [c["symbol"] for c in fetch_sp500_constituents()]
        prompt = build_prompt(top, already_tracked)

        try:
            raw_content = call_llm(prompt, SYSTEM_PROMPT, deepseek_key)
            candidates = parse_response(raw_content)
        except CandidateResponseError:
            logger.exception("Некоректна відповідь LLM — прогін пропущено")
            return
        except requests.exceptions.RequestException:
            logger.exception("Мережева помилка виклику LLM — прогін пропущено")
            return

        logger.info("LLM запропонував %d кандидатів", len(candidates))

        llm_call_id = log_llm_call(
            conn,
            provider=LLM_PROVIDER,
            purpose="candidate_discovery",
            prompt=prompt,
            response=raw_content,
            source_ref=None,
        )

        saved = 0
        for candidate in candidates:
            ticker = candidate["ticker"].upper()
            if ticker in already_tracked:
                logger.info("%s: уже в S&P 500 universe — не новий актив, пропущено", ticker)
                continue

            price = verify_tradable(conn, ticker, twelvedata_key)
            if price is None:
                logger.info("%s: не підтверджено як реально торгований — пропущено", ticker)
                continue

            save_candidate(
                conn,
                ticker=ticker,
                company_name=candidate["company_name"],
                reasoning=candidate["reasoning"],
                source_refs=[{"title": c.representative_title, "source_count": c.source_count} for c in top],
                llm_call_id=llm_call_id,
            )
            saved += 1
            logger.info("%s (%s): підтверджено, збережено — %s", ticker, candidate["company_name"], candidate["reasoning"])

        logger.info("Готово: %d кандидатів підтверджено й збережено", saved)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
