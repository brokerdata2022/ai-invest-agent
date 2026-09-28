#!/usr/bin/env python3
"""
Сповіщення в Telegram про поточний список кандидатів-новачків — вже
знайдених і верифікованих analysis/news_analysis/discover_candidates.py
(candidate_assets). Тільки форматування готового результату, жодної
аналітики (reporting/CLAUDE.md).

Використання (після analysis/news_analysis/discover_candidates.py):
    python candidates_notify.py
"""

import argparse
import logging

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import fetch_dicts, resolve_telegram_credentials  # noqa: E402
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_current_candidates(conn, limit: int = 10) -> list[dict]:
    """Останні `limit` унікальних тикерів (за найновішим discovered_at
    кожного) — власний запит, не імпорт з analysis/ (reporting/CLAUDE.md:
    контейнерна незалежність, той самий принцип, що telegram_notify.py:_METRIC_SOURCE).
    Дублює news_analysis/_db.py:fetch_current_candidates() навмисно."""
    return fetch_dicts(
        conn,
        """
        SELECT ticker, company_name, reasoning, discovered_at FROM (
            SELECT DISTINCT ON (ticker) ticker, company_name, reasoning, discovered_at
            FROM candidate_assets
            ORDER BY ticker, discovered_at DESC
        ) t
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "🆕 Список кандидатів-новачків ще порожній."

    lines = [f"🆕 Кандидати-новачки ({len(rows)}):", ""]
    for row in rows:
        lines.append(f"{row['ticker']} — {row['company_name']}")
        lines.append(row["reasoning"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_current_candidates(conn, limit=args.limit)
    finally:
        conn.close()

    text = format_message(rows)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: %d кандидатів", len(rows))


if __name__ == "__main__":
    main()
