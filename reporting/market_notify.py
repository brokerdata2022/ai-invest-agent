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

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import MARKET_DIRECTION_LABEL, fetch_one_dict, resolve_telegram_credentials  # noqa: E402
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def fetch_latest_market_synthesis(conn):
    query = """
        SELECT cluster_count, direction, confidence, summary, source_refs, created_at
        FROM market_synthesis
        ORDER BY created_at DESC
        LIMIT 1
    """
    return fetch_one_dict(conn, query)


def format_message(row) -> str:
    if row is None:
        return "🌍 Синтезу стану ринку ще немає."

    label = MARKET_DIRECTION_LABEL.get(row["direction"], row["direction"])
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
    parser.parse_args()  # лише для --help/валідації: скрипт без параметрів

    token, chat_id = resolve_telegram_credentials()

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
