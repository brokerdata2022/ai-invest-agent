#!/usr/bin/env python3
"""
Щоденний дайджест (docs/news-purpose.md, "Ціль 5"): кілька СПРАВДІ
важливих подій за останні --hours, не список усього релевантного.
Жодного нового LLM-виклику — усі "важливі події" вже пораховані
попередніми кроками (news_synthesis/market_synthesis/
expectation_comparisons/candidate_assets), тут лише форматування
готового (reporting/CLAUDE.md).

Обмеження Telegram (4096 символів на повідомлення) — рішення
користувача: не різати один довгий текст на частини, кожна подія з
топ-списку йде ОКРЕМИМ повідомленням (природно короткі за
конструкцією, ліміт ніколи не досягається).

Використання:
    python daily_digest.py
    python daily_digest.py --hours 12
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

_DIRECTION_EMOJI = {"up": "🟢", "down": "🔴", "neutral": "⚪", "unclear": "❓"}
_MARKET_DIRECTION_LABEL = {
    "up": "🟢 risk-on", "down": "🔴 risk-off",
    "neutral": "⚪ збалансовано", "unclear": "❓ немає чіткого сигналу",
}


def _fetch_dicts(conn, query: str, params: tuple) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_recent_news_synthesis(conn, hours: int) -> list[dict]:
    return _fetch_dicts(
        conn,
        """
        SELECT asset_id, cluster_count, net_lean, price_pct_change, direction, confidence, summary
        FROM news_synthesis
        WHERE created_at >= now() - (%s || ' hours')::interval
        ORDER BY created_at DESC
        """,
        (hours,),
    )


def fetch_recent_market_synthesis(conn, hours: int) -> dict | None:
    rows = _fetch_dicts(
        conn,
        """
        SELECT cluster_count, direction, confidence, summary
        FROM market_synthesis
        WHERE created_at >= now() - (%s || ' hours')::interval
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (hours,),
    )
    return rows[0] if rows else None


def fetch_recent_surprises(conn, hours: int) -> list[dict]:
    """Тільки impact_level high/medium — той самий фільтр, що вже в
    expectations_notify.py."""
    return _fetch_dicts(
        conn,
        """
        SELECT ec.metric_id, ec.observed_at, ec.actual_value, ec.expected_value_raw,
               ec.expected_value_parsed, ec.surprise, ec.surprise_pct
        FROM expectation_comparisons ec
        JOIN release_log rl ON rl.id = ec.release_log_id
        WHERE ec.created_at >= now() - (%s || ' hours')::interval
          AND rl.impact_level IN ('high', 'medium')
        ORDER BY ec.created_at DESC
        """,
        (hours,),
    )


def fetch_recent_candidates(conn, hours: int) -> list[dict]:
    """НОВІ рядки candidate_assets за вікно — не весь поточний список,
    тільки те, що з'явилось за --hours (docs/news-purpose.md, "Ціль 3")."""
    return _fetch_dicts(
        conn,
        """
        SELECT ticker, company_name, reasoning
        FROM candidate_assets
        WHERE discovered_at >= now() - (%s || ' hours')::interval
        ORDER BY discovered_at DESC
        """,
        (hours,),
    )


def format_news_synthesis_message(row: dict) -> str:
    emoji = _DIRECTION_EMOJI.get(row["direction"], "❓")
    return (
        f"{emoji} {row['asset_id']}: ціна {float(row['price_pct_change']):+.2f}%, "
        f"новини {row['net_lean']:+d} ({row['cluster_count']} історій)\n"
        f"{row['summary']}"
    )


def format_market_synthesis_message(row: dict) -> str:
    label = _MARKET_DIRECTION_LABEL.get(row["direction"], row["direction"])
    return f"🌍 Стан ринку: {label} (упевненість {float(row['confidence']):.2f})\n{row['summary']}"


def format_surprise_message(row: dict) -> str:
    label = METRIC_LABELS.get(row["metric_id"], row["metric_id"])
    pct_suffix = f" ({row['surprise_pct']:+.1f}%)" if row["surprise_pct"] is not None else ""
    return (
        f"📈 {label} — {row['observed_at']}\n"
        f"Факт {float(row['actual_value']):.4g} vs очікування "
        f"{float(row['expected_value_parsed']):.4g} (прогноз: {row['expected_value_raw']})\n"
        f"Сюрприз: {float(row['surprise']):+.4g}{pct_suffix}"
    )


def format_candidate_message(row: dict) -> str:
    return f"🆕 {row['ticker']} — {row['company_name']}\n{row['reasoning']}"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
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
        news_rows = fetch_recent_news_synthesis(conn, args.hours)
        market_row = fetch_recent_market_synthesis(conn, args.hours)
        surprise_rows = fetch_recent_surprises(conn, args.hours)
        candidate_rows = fetch_recent_candidates(conn, args.hours)
    finally:
        conn.close()

    messages = []
    if market_row is not None:
        messages.append(format_market_synthesis_message(market_row))
    messages.extend(format_news_synthesis_message(r) for r in news_rows)
    messages.extend(format_surprise_message(r) for r in surprise_rows)
    messages.extend(format_candidate_message(r) for r in candidate_rows)

    if not messages:
        messages = ["Сьогодні суттєвих подій не було."]

    for text in messages:
        send_telegram_message(token, chat_id, text)

    logger.info("Надіслано в Telegram: %d повідомлень дайджесту", len(messages))


if __name__ == "__main__":
    main()
