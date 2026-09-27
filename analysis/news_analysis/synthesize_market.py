#!/usr/bin/env python3
"""
LLM-синтез глобального контексту (docs/news-purpose.md, "Ціль 4" —
де зараз великий капітал): risk-on/risk-off висновок із найбільш
підтверджених geopolitical/general історій за вікно + власного
макро-контексту (дохідності/ставки/долар — уже живі FRED/ECB/BOJ ряди).

Відрізняється від synthesize.py (Ціль 1): там LLM зіставляв новинний
сигнал ОДНОГО активу з його ж ціною; тут geopolitical/general новини
не прив'язані до активу (asset_id=NULL, docs/decisions.md, 2026-09-25)
— aggregate_by_asset() тут не застосовний, замість нього
aggregate.py:top_clusters() (найбільш підтверджені історії, не по
активу).

Межа шарів / формат виходу / провайдер — той самий принцип, що
synthesize.py (SynthesisResult/parse_response/call_llm дубльовані
навмисно, кожен LLM-скрипт самодостатній — той самий підхід, що вже є
між relevance_filter.py й synthesize.py).

Використання:
    python synthesize_market.py
    python synthesize_market.py --max-age-days 3 --top 5
"""

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection, fetch_recent  # noqa: E402
from news_analysis._db import fetch_relevant_for_aggregation, log_llm_call, save_market_synthesis  # noqa: E402
from news_analysis.aggregate import NewsCluster, cluster_articles, top_clusters  # noqa: E402
from news_analysis.deepseek_client import call_deepseek  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DIRECTIONS = frozenset({"up", "down", "neutral", "unclear"})
_REQUIRED_FIELDS = ("direction", "confidence", "summary", "reasoning")

# Не CLI-прапорець — сама суть Цілі 4 саме ці два потоки (asset_id=NULL,
# не прив'язані до активу, на відміну від watchlist).
STREAMS = ("geopolitical", "general")

# Ярлик → (source, metric_id) у raw_observations. Фіксований список,
# дублює стиль reporting/telegram_notify.py:_METRIC_SOURCE (без прямого
# імпорту з monitoring/ — контейнерна незалежність).
MACRO_CONTEXT_METRICS: dict[str, tuple[str, str]] = {
    "US 10Y Treasury Yield": ("fred", "treasury_10y"),
    "US 2Y Treasury Yield": ("fred", "treasury_2y"),
    "US Fed Funds Rate": ("fred", "fed_funds_rate"),
    "EUR/USD": ("fred", "eurusd"),
    "USD/JPY": ("fred", "usdjpy_fx_rate"),
    "Eurozone Deposit Rate": ("ecb", "eurozone_deposit_rate"),
    "Japan Policy Rate": ("boj", "japan_policy_rate"),
}

LLM_PROVIDER = os.environ.get("SYNTHESIS_LLM_PROVIDER", "deepseek")

SYSTEM_PROMPT = (
    "Ти макро-стратег. Тобі дають дві речі: (1) макро-контекст — "
    "останні значення ключових ставок/дохідностей/валютних пар "
    "(поточне і попереднє, щоб бачити напрямок), (2) НАЙБІЛЬШ "
    "ПІДТВЕРДЖЕНІ геополітичні й загальноринкові новинні історії за "
    "вікно (дублікати з різних видань уже об'єднані, відсортовано за "
    "кількістю незалежних джерел — природна міра важливості)."
    "\n\n"
    "Твоя задача — risk-on чи risk-off, спираючись на ОБИДВА входи "
    "РАЗОМ: новини БЕЗ підтвердження макро-контекстом (наприклад, "
    "стаття каже про ескалацію, а дохідності/долар не рухаються) "
    "важать менше, ніж ті, що узгоджуються з фактичним рухом ставок/"
    "валют. direction: up (risk-on — капітал у ризикові активи), down "
    "(risk-off — втеча в безпечні активи), neutral (збалансовано, "
    "немає домінантного напрямку), unclear (немає чіткого сигналу)."
    "\n\n"
    "НІКОЛИ не давай прямих торгових рекомендацій ('купити'/'продати'/"
    "'входити в позицію') — тільки описові характеристики. Відповідай "
    "ЛИШЕ JSON-об'єктом з полями: direction (одне з: up, down, neutral, "
    "unclear), confidence (число від 0 до 1 — наскільки новини й "
    "макро-контекст узгоджуються), summary (1-2 речення: який стан "
    "ринку і чому), reasoning (коротке обґрунтування для аудиту)."
)


@dataclass
class SynthesisResult:
    direction: str
    confidence: float
    summary: str
    reasoning: str


class SynthesisResponseError(ValueError):
    pass


def fetch_macro_context(conn) -> dict[str, dict]:
    """Останнє й попереднє значення кожної метрики з
    MACRO_CONTEXT_METRICS — best-effort, метрика без достатньої історії
    просто пропускається (не блокує решту)."""
    context = {}
    for label, (source, metric_id) in MACRO_CONTEXT_METRICS.items():
        observations = fetch_recent(conn, source, metric_id, limit=2)
        if not observations:
            continue
        entry = {
            "latest_value": str(observations[0]["value"]),
            "latest_date": str(observations[0]["observed_at"]),
        }
        if len(observations) > 1:
            entry["previous_value"] = str(observations[1]["value"])
            entry["previous_date"] = str(observations[1]["observed_at"])
        context[label] = entry
    return context


def build_prompt(clusters: list[NewsCluster], macro: dict) -> str:
    lines = ["Макро-контекст:"]
    if macro:
        for label, entry in macro.items():
            if "previous_value" in entry:
                lines.append(
                    f"- {label}: {entry['latest_value']} ({entry['latest_date']}), "
                    f"попереднє {entry['previous_value']} ({entry['previous_date']})"
                )
            else:
                lines.append(f"- {label}: {entry['latest_value']} ({entry['latest_date']})")
    else:
        lines.append("- немає даних")

    lines.append("")
    lines.append(f"Найбільш підтверджені історії за вікно ({len(clusters)}):")
    for c in clusters:
        lines.append(f"- [{c.source_count} джерел, напрямок {c.dominant_direction}] {c.representative_title}")
        if c.summaries:
            lines.append(f"  → {c.summaries[0]}")
    return "\n".join(lines)


def parse_response(raw_content: str) -> SynthesisResult:
    try:
        data = json.loads(raw_content)
    except json.JSONDecodeError as e:
        raise SynthesisResponseError(
            f"Відповідь LLM не є коректним JSON: {raw_content!r}"
        ) from e

    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise SynthesisResponseError(f"У відповіді LLM бракує полів {missing}: {data!r}")

    direction = data["direction"]
    if direction not in _DIRECTIONS:
        raise SynthesisResponseError(f"Неочікуване значення direction: {direction!r}")

    try:
        confidence = float(data["confidence"])
    except (TypeError, ValueError) as e:
        raise SynthesisResponseError(f"confidence не число: {data['confidence']!r}") from e
    if not 0 <= confidence <= 1:
        raise SynthesisResponseError(f"confidence поза межами [0,1]: {confidence}")

    return SynthesisResult(
        direction=direction,
        confidence=confidence,
        summary=data["summary"],
        reasoning=data["reasoning"],
    )


def call_llm(prompt: str, system_prompt: str, api_key: str) -> str:
    if LLM_PROVIDER == "deepseek":
        return call_deepseek(prompt, api_key=api_key, system_prompt=system_prompt)
    raise ValueError(
        f"Непідтримуваний SYNTHESIS_LLM_PROVIDER={LLM_PROVIDER!r} — наразі реалізовано "
        "лише 'deepseek' (Anthropic-клієнт з'явиться разом зі свідомим переходом, "
        "docs/decisions.md, 2026-09-27)."
    )


def synthesize_market(
    clusters: list[NewsCluster], macro: dict, api_key: str
) -> tuple[SynthesisResult, str, str]:
    """Той самий контракт, що synthesize.synthesize_asset(): повертає
    (результат, промпт, сира_відповідь) для обов'язкового логування
    (rule 5)."""
    prompt = build_prompt(clusters, macro)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
    result = parse_response(raw_content)
    return result, prompt, raw_content


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--top", type=int, default=8, help="скільки найбільш підтверджених історій урахувати")
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY") if LLM_PROVIDER == "deepseek" else None
    if LLM_PROVIDER == "deepseek" and not api_key:
        logger.error("DEEPSEEK_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    conn = get_connection()
    try:
        articles = []
        for stream in STREAMS:
            articles.extend(
                fetch_relevant_for_aggregation(conn, stream=stream, max_age_days=args.max_age_days)
            )
        clusters = cluster_articles(articles)
        top = top_clusters(clusters, limit=args.top)
        logger.info("%d кластерів усього, %d найбільш підтверджених урахуємо", len(clusters), len(top))

        if not top:
            logger.info("Немає geopolitical/general кластерів за вікно — нічого синтезувати")
            return

        macro = fetch_macro_context(conn)
        logger.info("Макро-контекст: %d показників", len(macro))

        try:
            result, prompt, raw_content = synthesize_market(top, macro, api_key)
        except SynthesisResponseError:
            logger.exception("Некоректна відповідь LLM — синтез пропущено")
            return
        except requests.exceptions.RequestException:
            logger.exception("Мережева помилка виклику LLM — синтез пропущено")
            return

        llm_call_id = log_llm_call(
            conn,
            provider=LLM_PROVIDER,
            purpose="market_context_synthesis",
            prompt=prompt,
            response=raw_content,
            source_ref=None,
        )
        save_market_synthesis(
            conn,
            clusters=top,
            macro=macro,
            window_days=args.max_age_days,
            result=result,
            llm_call_id=llm_call_id,
        )
        logger.info(
            "Готово: direction=%s confidence=%.2f: %s",
            result.direction, result.confidence, result.summary,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
