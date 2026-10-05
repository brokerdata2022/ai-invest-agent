#!/usr/bin/env python3
"""
Надсилає в Telegram наш ВЛАСНИЙ прогноз наступного значення показника
(analysis/forecasting/ → metric_forecasts) — закриває явний пропуск,
зафіксований у PLAN.md, Фаза 2: "поки що metric_forecasts тільки
зберігається, нікуди не показується".

Три точки зору в одному повідомленні (саме та "третя точка зору", про
яку PLAN.md):
1. останнє ВІДОМЕ значення (факт, raw_observations),
2. НАШ прогноз на наступний період (LLM, analysis/forecasting/),
3. РИНКОВЕ очікування на найближчий запланований реліз
   (release_log.expected_value, ForexFactory — те саме число, проти
   якого analysis/expectations/ потім порівняє факт).

Ринкове очікування показується СИРИМ рядком, без числового
порівняння з нашим прогнозом: `release_log.expected_value` — текст
джерела ("3.2%", "-150K"), його приведення до спільних одиниць живе в
analysis/expectations/comparison_methods.py і є АНАЛІЗОМ, якому не
місце в reporting/ (reporting/CLAUDE.md: тільки представлення).
Порівняння "наш прогноз vs ринковий" у числах — окрема задача в
analysis/, якщо знадобиться.

Тільки форматування вже готового результату, жодної аналітики.

Використання (після analysis/forecasting/update_forecasts.py):
    python forecast_notify.py
    python forecast_notify.py --limit 10
"""

import argparse
import logging

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import (  # noqa: E402
    DIRECTION_EMOJI,
    bold,
    escape_html,
    fetch_dicts,
    format_local_dt,
    mark_notified,
    resolve_telegram_credentials,
)
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402
from telegram_notify import METRIC_LABELS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Лише LLM-прогнози: `linear_trend` лишається в тій самій таблиці як
# базова лінія для backtest (analysis/forecasting/trend.py) — це
# внутрішній інструмент оцінки якості, не висновок для користувача.
METHOD = "llm"


def fetch_unnotified_forecasts(conn, limit: int = 10) -> list[dict]:
    """Ще НЕ надіслані прогнози (notified_at IS NULL) разом з останнім
    відомим фактичним значенням, на якому прогноз побудований.
    `last_actual` — LEFT JOIN: прогноз лишається вартим відправки й
    тоді, коли рядок спостереження чомусь не знайшовся."""
    query = """
        SELECT f.id, f.source, f.metric_id, f.based_on_observed_at, f.periods_ahead,
               f.forecast_value, f.direction, f.confidence, f.summary, f.created_at,
               o.value AS last_actual
        FROM metric_forecasts f
        LEFT JOIN v_observations_latest_revision o
               ON o.source = f.source
              AND o.metric_id = f.metric_id
              AND o.observed_at = f.based_on_observed_at
        WHERE f.method = %s
          AND f.notified_at IS NULL
        ORDER BY f.created_at DESC
        LIMIT %s
    """
    return fetch_dicts(conn, query, (METHOD, limit))


def fetch_next_release(conn, metric_id: str):
    """Найближчий ЩЕ НЕ вийшлий запланований реліз цього показника
    (refresh_calendar.py заводить їх наперед) — саме той період, який і
    прогнозується. None, якщо календар на нього ще не заведений."""
    rows = fetch_dicts(
        conn,
        """
        SELECT scheduled_at, expected_value, impact_level
        FROM release_log
        WHERE metric_id = %s
          AND status = 'pending'
          AND scheduled_at >= now()
        ORDER BY scheduled_at
        LIMIT 1
        """,
        (metric_id,),
    )
    return rows[0] if rows else None


def format_forecast_block(row: dict, next_release) -> list[str]:
    label = METRIC_LABELS.get(row["metric_id"], row["metric_id"])
    emoji = DIRECTION_EMOJI.get(row["direction"], "❓")

    lines = [bold(f"🔮 {label}")]

    if row.get("last_actual") is not None:
        lines.append(
            f"Останнє відоме: {float(row['last_actual']):.6g} "
            f"({escape_html(row['based_on_observed_at'])})"
        )
    else:
        lines.append(f"Побудовано на даних до {escape_html(row['based_on_observed_at'])}")

    confidence_suffix = (
        f" · впевненість {float(row['confidence']):.2f}"
        if row.get("confidence") is not None else ""
    )
    forecast_text = f"{float(row['forecast_value']):.6g}"
    lines.append(f"{emoji} Наш прогноз: {bold(forecast_text)}{confidence_suffix}")

    if next_release is not None:
        when = escape_html(format_local_dt(next_release["scheduled_at"]))
        if next_release.get("expected_value"):
            lines.append(
                f"Ринкове очікування: {escape_html(next_release['expected_value'])} "
                f"(реліз {when})"
            )
        else:
            lines.append(f"Наступний реліз: {when} (ринкового прогнозу немає)")

    if row.get("summary"):
        lines.append(f"→ {escape_html(row['summary'])}")

    lines.append("")
    return lines


def format_message(rows: list[dict], next_releases: dict) -> str:
    lines = [bold(f"🔮 Наш прогноз наступних значень ({len(rows)}):"), ""]
    for row in rows:
        lines.extend(format_forecast_block(row, next_releases.get(row["metric_id"])))
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_unnotified_forecasts(conn, limit=args.limit)
        if not rows:
            logger.info("Нових прогнозів немає — сповіщення не надсилається")
            return

        next_releases = {
            row["metric_id"]: fetch_next_release(conn, row["metric_id"]) for row in rows
        }
        text = format_message(rows, next_releases)
        send_telegram_message(token, chat_id, text, parse_mode="HTML")
        mark_notified(conn, "metric_forecasts", [row["id"] for row in rows])
        logger.info("Надіслано в Telegram: %d прогноз(и)", len(rows))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
