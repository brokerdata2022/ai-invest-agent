#!/usr/bin/env python3
"""
Надсилає в Telegram список активів, які варто РОЗГЛЯДАТИ для торгівлі
(`trading_list` — `analysis/trading_list/`, дизайн
`docs/trading-list.md`).

Не дублює `screening_notify.py` (фундаментальний скринінг акцій),
`crypto_screening_notify.py` (крипто-сетапи) чи `watchlist_notify.py`
(ціни обраних активів): ті показують СВОЇ зрізи, цей — результат
фільтра за каталізатором поверх усіх трьох.

Тільки форматування вже готового результату, жодної аналітики
(reporting/CLAUDE.md). Зокрема НЕ пере-ранжує й не відсікає: поріг і
топ уже застосовані в `analysis/trading_list/scoring.py:select_final`.

Формулювання свідомо ОПИСОВІ — напрямок сигналу й причина, без
"купити/продати" (analysis/CLAUDE.md, "Заборонені формулювання").

Використання (після analysis/trading_list/run_trading_list.py):
    python trading_list_notify.py
"""

import argparse
import logging

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import (  # noqa: E402
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

HORIZON = "medium"

# Напрямок сигналу → емодзі. Власний словник, а не
# `_common.DIRECTION_EMOJI`: торговий список має ДОДАТКОВЕ значення
# `conflicting` (компоненти вказують у різні боки), якого немає в
# решти проєкту — і воно не те саме, що `unclear` (сигналу немає).
DIRECTION_LABEL = {
    "up": "🟢 вгору",
    "down": "🔴 вниз",
    "neutral": "⚪ без напрямку",
    "unclear": "❓ незрозуміло",
    "conflicting": "⚠️ суперечливо",
}

KIND_LABEL = {
    "stock": "акція",
    "crypto": "крипта",
    "fx": "форекс",
    "commodity": "товар",
}


def fetch_unnotified(conn, horizon: str = HORIZON) -> list[dict]:
    """Рядки ПОСЛІДНЬОГО прогону цього горизонту, ще не надіслані.

    Фільтр за `run_at = MAX(run_at)` критичний: без нього повторний
    прогін (новий знімок) надсилав би ще й старі ненадіслані рядки
    попереднього — а вони вже неактуальні."""
    return fetch_dicts(
        conn,
        """
        SELECT id, asset_id, kind, direction, score, catalyst_score,
               trend_score, quality_score, catalyst_summary, source
        FROM trading_list
        WHERE horizon = %s
          AND notified_at IS NULL
          AND run_at = (SELECT MAX(run_at) FROM trading_list WHERE horizon = %s)
        ORDER BY score DESC
        """,
        (horizon, horizon),
    )


def format_message(rows: list[dict]) -> str:
    lines = [
        bold(f"🎯 Активи для розгляду ({len(rows)})"),
        "Середньостроковий горизонт — дні-тижні.",
        "",
    ]

    for i, row in enumerate(rows, start=1):
        label = DIRECTION_LABEL.get(row["direction"], row["direction"])
        kind = KIND_LABEL.get(row["kind"], row["kind"])

        lines.append(
            f"{i}. {bold(row['asset_id'].upper())} · {escape_html(kind)} · {label}"
        )
        lines.append(
            f"   скор {float(row['score']):.2f} "
            f"(каталізатор {float(row['catalyst_score'] or 0):.2f} · "
            f"тренд {float(row['trend_score'] or 0):.2f} · "
            f"якість {float(row['quality_score'] or 0):.2f})"
        )
        if row.get("catalyst_summary"):
            # Обрізаємо: причин може бути 5-10, у повідомленні потрібен
            # привід подивитись, не весь аудит (повний — у БД).
            summary = row["catalyst_summary"]
            if len(summary) > 220:
                summary = summary[:217] + "…"
            lines.append(f"   {escape_html(summary)}")
        lines.append("")

    lines.append(
        "ℹ️ Це перелік для РОЗГЛЯДУ з напрямком сигналу, не вказівка діяти."
    )
    return "\n".join(lines)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon", default=HORIZON)
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_unnotified(conn, horizon=args.horizon)
        if not rows:
            logger.info("Нових активів у торговому списку немає — не надсилаємо")
            return

        send_telegram_message(token, chat_id, format_message(rows), parse_mode="HTML")
        mark_notified(conn, "trading_list", [row["id"] for row in rows])
        logger.info("Надіслано в Telegram: %d активів", len(rows))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
