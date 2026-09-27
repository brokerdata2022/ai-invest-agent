#!/usr/bin/env python3
"""
Сповіщення в Telegram про стан ринку (risk-on/risk-off) — вже
пораховане analysis/news_analysis/synthesize_market.py (market_synthesis).
Тільки форматування готового результату, жодної аналітики
(reporting/CLAUDE.md).

Використання (після analysis/news_analysis/synthesize_market.py):
    python market_notify.py
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DIRECTION_LABEL = {
    "up": "🟢 risk-on",
    "down": "🔴 risk-off",
    "neutral": "⚪ збалансовано",
    "unclear": "❓ немає чіткого сигналу",
}


def fetch_latest_market_synthesis(conn):
    query = """
        SELECT cluster_count, direction, confidence, summary, source_refs, created_at
        FROM market_synthesis
        ORDER BY created_at DESC
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
        if row is None:
            return None
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row))


def format_message(row) -> str:
    if row is None:
        return "🌍 Синтезу стану ринку ще немає."

    label = _DIRECTION_LABEL.get(row["direction"], row["direction"])
    lines = [
        f"🌍 Стан ринку: {label} (упевненість {float(row['confidence']):.2f})",
        row["summary"],
        "",
        f"На основі {row['cluster_count']} найбільш підтверджених історій:",
    ]
    for ref in row["source_refs"]:
        lines.append(f"- [{ref['source_count']} джерел] {ref['title']}")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
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
        row = fetch_latest_market_synthesis(conn)
    finally:
        conn.close()

    text = format_message(row)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: стан ринку %s", row["direction"] if row else "(немає)")


if __name__ == "__main__":
    main()
