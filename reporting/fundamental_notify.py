#!/usr/bin/env python3
"""
Надсилає в Telegram фундаментальний LLM-аналіз акцій
(`fundamental_analysis` — `analysis/fundamental/`).

Не дублює `screening_notify.py`: там детермінований результат воронки
Tier A/B/C (тикер/назва/зміна ціни), тут — ІНТЕРПРЕТАЦІЯ звітності
(що кажуть цифри про стан бізнесу, сильні сторони й ризики).

Тільки форматування вже готового результату, жодної аналітики
(reporting/CLAUDE.md). Формулювання описові, без "купити/продати"
(analysis/CLAUDE.md).

Використання (після analysis/fundamental/run_analysis.py):
    python fundamental_notify.py
"""

import argparse
import logging

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path, тому імпортується ПЕРШИМ.
from _common import (  # noqa: E402
    DIRECTION_EMOJI,
    bold,
    escape_html,
    fetch_dicts,
    mark_notified,
    resolve_telegram_credentials,
)
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DIRECTION_WORD = {
    "up": "картина покращується",
    "down": "картина погіршується",
    "neutral": "картина стабільна",
    "unclear": "картина неоднозначна",
}


def fetch_unnotified(conn, limit: int = 10) -> list[dict]:
    return fetch_dicts(
        conn,
        """
        SELECT id, ticker, company_name, direction, confidence, summary,
               strengths, risks
        FROM fundamental_analysis
        WHERE notified_at IS NULL
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def format_message(rows: list[dict]) -> str:
    lines = [bold(f"📑 Фундаментальний аналіз — {len(rows)}"), ""]

    for row in rows:
        name = row.get("company_name") or row["ticker"]
        emoji = DIRECTION_EMOJI.get(row["direction"], "❓")
        word = DIRECTION_WORD.get(row["direction"], row["direction"])

        lines.append(f"{emoji} {bold(name)} ({escape_html(row['ticker'])}) — {word}")
        lines.append(escape_html(row["summary"]))

        for point in row.get("strengths") or []:
            lines.append(f"   ✅ {escape_html(point)}")
        for point in row.get("risks") or []:
            lines.append(f"   ⚠️ {escape_html(point)}")
        lines.append("")

    lines.append("<i>ℹ️ Опис стану бізнесу за звітністю, не вказівка діяти.</i>")
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_unnotified(conn, limit=args.limit)
        if not rows:
            logger.info("Нових фундаментальних аналізів немає — не надсилаємо")
            return

        send_telegram_message(token, chat_id, format_message(rows), parse_mode="HTML")
        mark_notified(conn, "fundamental_analysis", [row["id"] for row in rows])
        logger.info("Надіслано в Telegram: %d аналізів", len(rows))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
