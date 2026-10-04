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

Межа шарів / формат виходу — той самий принцип, що synthesize.py;
провайдер, розбір відповіді й аудит-лог виклику — спільні
(`llm_common.py`), тут лишається лише своє: SYSTEM_PROMPT,
build_prompt() і макро-контекст.

Використання:
    python synthesize_market.py
    python synthesize_market.py --max-age-days 3 --top 5
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection, fetch_recent  # noqa: E402
from llm_common import (  # noqa: E402
    SynthesisResponseError,
    call_llm,
    log_llm_call,
    parse_synthesis_response,
    require_api_key,
    resolve_provider,
)
from news_analysis._db import fetch_relevant_for_aggregation, save_market_synthesis  # noqa: E402
from news_analysis.aggregate import NewsCluster, cluster_articles, top_clusters  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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

# Торгові сесії (спек користувача 2026-09-28: "після відкриття
# азіатської/європейської/американської сесій, 3 рази/добу за часом
# сесій, не 1 раз/добу у фіксовану годину").
#
# Навіщо сесія в ПРОМПТІ, а не лише в розкладі: той самий набір новин
# і макро-контексту читається інакше залежно від того, який ринок щойно
# відкрився. Азія вранці реагує на вчорашнє закриття США; Нью-Йорк
# відкривається вже знаючи, що зробила Європа. Без цього три прогони за
# добу дали б три майже однакові висновки з однакових даних.
SESSIONS = {
    "asia": (
        "Щойно відкрилась АЗІАТСЬКА сесія (Токіо). Азійські ринки першими "
        "реагують на те, що сталось за ніч — насамперед на закриття США й "
        "на нічні новини. Враховуй саме цю реакцію-відповідь."
    ),
    "europe": (
        "Щойно відкрилась ЄВРОПЕЙСЬКА сесія (Лондон). Європа відкривається, "
        "вже бачачи результат азіатської сесії, і додає власний потік "
        "європейських даних та новин ЄЦБ."
    ),
    "us": (
        "Щойно відкрилась АМЕРИКАНСЬКА сесія (Нью-Йорк) — найбільший обсяг "
        "торгів доби. США відкриваються, знаючи і Азію, і Європу; саме тут "
        "найчастіше формується домінантний напрямок дня."
    ),
}

DEFAULT_SESSION = "daily"

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


def build_prompt(
    clusters: list[NewsCluster], macro: dict, session: str = DEFAULT_SESSION
) -> str:
    lines = []
    session_context = SESSIONS.get(session)
    if session_context:
        lines.append(session_context)
        lines.append("")
    lines.append("Макро-контекст:")
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


def synthesize_market(
    clusters: list[NewsCluster], macro: dict, api_key: str,
    session: str = DEFAULT_SESSION,
):
    """Той самий контракт, що synthesize.synthesize_asset(): повертає
    (результат, промпт, сира_відповідь) для обов'язкового логування
    (rule 5)."""
    prompt = build_prompt(clusters, macro, session=session)
    raw_content = call_llm(prompt, SYSTEM_PROMPT, api_key)
    result = parse_synthesis_response(raw_content)
    return result, prompt, raw_content


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--session", choices=sorted(SESSIONS), default=None,
        help="торгова сесія, що щойно відкрилась (asia/europe/us) — додає "
             "контекст у промпт і дає ОКРЕМИЙ рядок на добу; без неї "
             "прогін зберігається як 'daily' (сумісність зі старим "
             "одноразовим розкладом)",
    )
    parser.add_argument("--max-age-days", type=int, default=7)
    parser.add_argument("--top", type=int, default=8, help="скільки найбільш підтверджених історій урахувати")
    args = parser.parse_args()

    session = args.session or DEFAULT_SESSION

    api_key = require_api_key()

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
            result, prompt, raw_content = synthesize_market(
                top, macro, api_key, session=session
            )
        except SynthesisResponseError:
            logger.exception("Некоректна відповідь LLM — синтез пропущено")
            return
        except requests.exceptions.RequestException:
            logger.exception("Мережева помилка виклику LLM — синтез пропущено")
            return

        llm_call_id = log_llm_call(
            conn,
            provider=resolve_provider(),
            purpose="market_context_synthesis",
            prompt=prompt,
            response=raw_content,
            source_ref=session,
        )
        save_market_synthesis(
            conn,
            clusters=top,
            macro=macro,
            window_days=args.max_age_days,
            result=result,
            llm_call_id=llm_call_id,
            session=session,
        )
        logger.info(
            "Готово [%s]: direction=%s confidence=%.2f: %s",
            session, result.direction, result.confidence, result.summary,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
