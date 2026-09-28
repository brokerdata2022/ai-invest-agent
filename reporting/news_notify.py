#!/usr/bin/env python3
"""
Сповіщення в Telegram про релевантні новини, вже проаналізовані
DeepSeek (analysis/news_analysis/run_news_analysis.py). Тільки
форматування готового аналізу — жодної інтерпретації тут
(reporting/CLAUDE.md).

Використання (після analysis/news_analysis/run_news_analysis.py):
    python news_notify.py --limit 5
    python news_notify.py --stream watchlist --limit 5
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

def fetch_recent_relevant(
    conn, stream: str = None, limit: int = 5, max_age_days: int = 7
) -> list[dict]:
    """Останні релевантні (is_relevant=true) висновки DeepSeek — за
    published_at СТАТТІ (коли вона фактично вийшла), не за created_at
    АНАЛІЗУ (коли ми її проаналізували). Це не одне й те саме: стаття
    може пролежати в raw_news тижнями (append-only, ніколи не
    видаляється, rule 6 CLAUDE.md) і потрапити в аналіз пізніше —
    сортування за created_at показало б її як "останню новину", хоча
    вона вже давно застаріла. max_age_days відсікає такий "хвіст" —
    навіть релевантна, але місяцями стара стаття (живо виявлено
    2026-09-26 — липнева стаття про ставку в результатах у вересні)
    не повинна виглядати як актуальний сигнал у сповіщенні.

    Без дедуплікації "вже надіслано раніше" — той самий підхід, що й
    telegram_notify.py (завжди останній стан, не чергу подій); якщо
    стане незручно — окреме рішення в docs/decisions.md."""
    query = """
        SELECT n.title, n.url, n.stream, n.published_at,
               a.asset_id, a.direction, a.confidence, a.summary
        FROM news_analysis a
        JOIN raw_news n ON n.id = a.raw_news_id
        WHERE a.is_relevant = true
          AND n.published_at >= now() - (%s || ' days')::interval
    """
    params: list = [max_age_days]
    if stream is not None:
        query += " AND n.stream = %s"
        params.append(stream)
    query += " ORDER BY n.published_at DESC LIMIT %s"
    params.append(limit)

    return fetch_dicts(conn, query, tuple(params))


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "📰 Релевантних новин не знайдено."

    lines = [f"📰 Релевантні новини ({len(rows)}):", ""]
    for row in rows:
        emoji = DIRECTION_EMOJI.get(row["direction"], "❓")
        asset = row["asset_id"] or "—"
        lines.append(f"{emoji} [{asset}] {row['title']}")
        lines.append(row["summary"])
        lines.append(row["url"])
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=["watchlist", "general", "geopolitical"], default=None)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--max-age-days", type=int, default=7,
        help="не показувати статті, опубліковані раніше N днів тому",
    )
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_recent_relevant(
            conn, stream=args.stream, limit=args.limit, max_age_days=args.max_age_days
        )
    finally:
        conn.close()

    text = format_message(rows)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: %d новин", len(rows))


if __name__ == "__main__":
    main()
