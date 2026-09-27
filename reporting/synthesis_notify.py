#!/usr/bin/env python3
"""
Сповіщення в Telegram про причинну атрибуцію ціна↔новини — вже
пораховану analysis/news_analysis/synthesize.py (news_synthesis).
Тільки форматування готового результату, жодної аналітики
(reporting/CLAUDE.md).

Використання (після analysis/news_analysis/synthesize.py):
    python synthesis_notify.py --limit 5
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

_DIRECTION_EMOJI = {"up": "🟢", "down": "🔴", "neutral": "⚪", "unclear": "❓"}


def fetch_recent_synthesis(conn, limit: int = 5) -> list[dict]:
    query = """
        SELECT asset_id, cluster_count, net_lean, price_pct_change,
               direction, confidence, summary, created_at
        FROM news_synthesis
        ORDER BY created_at DESC
        LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(query, (limit,))
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "🔍 Нових синтезів ціна/новини немає."

    lines = [f"🔍 Причинна атрибуція ціна/новини ({len(rows)}):", ""]
    for row in rows:
        emoji = _DIRECTION_EMOJI.get(row["direction"], "❓")
        lines.append(
            f"{emoji} {row['asset_id']}: ціна {float(row['price_pct_change']):+.2f}%, "
            f"новини {row['net_lean']:+d} ({row['cluster_count']} історій)"
        )
        lines.append(row["summary"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5)
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
        rows = fetch_recent_synthesis(conn, limit=args.limit)
    finally:
        conn.close()

    text = format_message(rows)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: %d синтезів", len(rows))


if __name__ == "__main__":
    main()
