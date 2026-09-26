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
import os
import sys

from dotenv import load_dotenv
import requests

# data-ingestion не є валідним іменем Python-пакета (дефіс у назві),
# тож додаємо його вміст напряму в sys.path, щоб дістати common.db —
# той самий підхід, що й telegram_notify.py.
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-ingestion")
)
from common.db import get_connection  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"

_DIRECTION_EMOJI = {"up": "🟢", "down": "🔴", "neutral": "⚪", "unclear": "❓"}


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

    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "📰 Релевантних новин не знайдено."

    lines = [f"📰 Релевантні новини ({len(rows)}):", ""]
    for row in rows:
        emoji = _DIRECTION_EMOJI.get(row["direction"], "❓")
        asset = row["asset_id"] or "—"
        lines.append(f"{emoji} [{asset}] {row['title']}")
        lines.append(row["summary"])
        lines.append(row["url"])
        lines.append("")
    return "\n".join(lines).rstrip()


def send_telegram_message(token: str, chat_id: str, text: str) -> dict:
    url = TELEGRAM_API_URL.format(token=token)
    response = requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=15)
    response.raise_for_status()
    return response.json()


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

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не задані в .env (див. .env.example)"
        )
        sys.exit(1)

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
