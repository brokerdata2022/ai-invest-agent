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

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import DIRECTION_EMOJI, fetch_dicts, resolve_telegram_credentials  # noqa: E402
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def fetch_recent_synthesis(conn, limit: int = 5) -> list[dict]:
    query = """
        SELECT asset_id, cluster_count, net_lean, price_pct_change,
               direction, confidence, summary, created_at
        FROM news_synthesis
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_dicts(conn, query, (limit,))


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "🔍 Нових синтезів ціна/новини немає."

    lines = [f"🔍 Причинна атрибуція ціна/новини ({len(rows)}):", ""]
    for row in rows:
        emoji = DIRECTION_EMOJI.get(row["direction"], "❓")
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

    token, chat_id = resolve_telegram_credentials()

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
