#!/usr/bin/env python3
"""
Сповіщення в Telegram про сюрприз факт/очікування — уже пораховане
analysis/expectations/compare_releases.py (expectation_comparisons).
Тільки форматування готового результату, жодної аналітики
(reporting/CLAUDE.md).

За замовчуванням — тільки impact_level high/medium (release_log):
low-показники не варті окремого сповіщення (той самий принцип, що
"короткий звіт, не повний дамп", reporting/CLAUDE.md).

Використання (після analysis/expectations/compare_releases.py):
    python expectations_notify.py --limit 5
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-ingestion")
)
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402
from telegram_notify import METRIC_LABELS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_IMPACT_LEVELS = ("high", "medium")


def fetch_recent_comparisons(
    conn, limit: int = 5, impact_levels: tuple = DEFAULT_IMPACT_LEVELS
) -> list[dict]:
    query = """
        SELECT ec.metric_id, ec.source, ec.observed_at, ec.actual_value,
               ec.expected_value_raw, ec.expected_value_parsed, ec.surprise,
               ec.surprise_pct, ec.comparison_method, ec.created_at,
               rl.impact_level
        FROM expectation_comparisons ec
        JOIN release_log rl ON rl.id = ec.release_log_id
        WHERE rl.impact_level = ANY(%s)
        ORDER BY ec.created_at DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (list(impact_levels), limit))
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "📊 Нових порівнянь факт/очікування немає."

    lines = [f"📊 Факт vs очікування ({len(rows)}):", ""]
    for row in rows:
        label = METRIC_LABELS.get(row["metric_id"], row["metric_id"])
        pct_suffix = f" ({row['surprise_pct']:+.1f}%)" if row["surprise_pct"] is not None else ""
        lines.append(f"{label} — {row['observed_at']}")
        lines.append(
            f"Факт {float(row['actual_value']):.4g} vs очікування "
            f"{float(row['expected_value_parsed']):.4g} (прогноз: {row['expected_value_raw']})"
        )
        lines.append(f"Сюрприз: {float(row['surprise']):+.4g}{pct_suffix}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--impact", nargs="+", default=list(DEFAULT_IMPACT_LEVELS),
        help="рівні impact_level для показу (за замовчуванням high medium)",
    )
    args = parser.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не задані в .env (див. .env.example)"
        )
        sys.exit(1)

    conn = get_connection()
    try:
        rows = fetch_recent_comparisons(conn, limit=args.limit, impact_levels=tuple(args.impact))
    finally:
        conn.close()

    text = format_message(rows)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: %d порівнянь", len(rows))


if __name__ == "__main__":
    main()
