#!/usr/bin/env python3
"""
Сповіщення в Telegram про нових кандидатів-новачків, знайдених і
верифікованих analysis/news_analysis/discover_candidates.py
(candidate_assets). Тільки форматування готового результату, жодної
аналітики (reporting/CLAUDE.md).

Дедуп (2026-09-28, критичний фікс, той самий принцип що
news_notify.py): `notified_at IS NULL` — раніше скрипт завжди показував
ПОТОЧНИЙ список (останні 10 унікальних тикерів), тож той самий тикер
міг з'являтись у сповіщенні щодня, навіть якщо про нього нема нічого
нового. Тепер — лише тикери, знайдені/оновлені (`discover_candidates.py`
UPSERT-ить один рядок на тикер НА ДЕНЬ) з часу останнього успішного
сповіщення.

Використання (після analysis/news_analysis/discover_candidates.py):
    python candidates_notify.py
"""

import argparse
import logging

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import fetch_dicts, mark_notified, resolve_telegram_credentials  # noqa: E402
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_unnotified_candidates(conn, limit: int = 10) -> list[dict]:
    """Тикери, ще не надіслані в Telegram (`notified_at IS NULL`) —
    власний запит, не імпорт з analysis/ (reporting/CLAUDE.md:
    контейнерна незалежність)."""
    return fetch_dicts(
        conn,
        """
        SELECT id, ticker, company_name, reasoning, discovered_at
        FROM candidate_assets
        WHERE notified_at IS NULL
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "🆕 Нових кандидатів-новачків немає."

    lines = [f"🆕 Нові кандидати-новачки ({len(rows)}):", ""]
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
        rows = fetch_unnotified_candidates(conn, limit=args.limit)
        if not rows:
            logger.info("Нових кандидатів немає — сповіщення не надсилається")
            return

        text = format_message(rows)
        send_telegram_message(token, chat_id, text)
        mark_notified(conn, "candidate_assets", [row["id"] for row in rows])
        logger.info("Надіслано в Telegram: %d кандидатів", len(rows))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
