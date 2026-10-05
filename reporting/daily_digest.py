#!/usr/bin/env python3
"""
Щоденний дайджест (docs/decisions.md, "Ціль 5"): кілька СПРАВДІ
важливих подій за останні --hours, не список усього релевантного.
Жодного нового LLM-виклику — усі "важливі події" вже пораховані
попередніми кроками (news_synthesis/market_synthesis/
expectation_comparisons/candidate_assets), тут лише форматування
готового (reporting/CLAUDE.md).

Обмеження Telegram (4096 символів на повідомлення) — рішення
користувача: не різати один довгий текст на частини, кожна подія з
топ-списку йде ОКРЕМИМ повідомленням (природно короткі за
конструкцією, ліміт ніколи не досягається).

Дедуп (2026-09-28, критичний фікс, той самий принцип що
news_notify.py/market_notify.py/synthesis_notify.py/candidates_notify.py):
`notified_at IS NULL` на всіх 4 джерелах + `mark_notified()` після
відправки. Раніше вікно `--hours` бралось СЛІПО за `created_at`, тому
цей дайджест дублював один в один усе, що окремі notify_*-джоби вже
надіслали протягом дня (напр. notify_synthesis@6:45,
notify_market_synthesis@18:45) — живий фідбек користувача 2026-09-28,
той самий рядок news_synthesis/market_synthesis приходив у Telegram
двічі символ-в-символ.

Використання:
    python daily_digest.py
    python daily_digest.py --hours 12
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import (  # noqa: E402
    DIRECTION_EMOJI,
    MARKET_DIRECTION_LABEL,
    bold,
    escape_html,
    fetch_dicts,
    fetch_one_dict,
    mark_notified,
    resolve_telegram_credentials,
)
from common.db import get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402
from telegram_notify import METRIC_LABELS  # noqa: E402

# Той самий виняток контейнерної незалежності, що expectations_notify.py
# (reporting/CLAUDE.md) — expectation_comparisons позначається нотифікованим
# через власний mark_notified() з analysis/expectations/_db.py, не через
# спільний _common.py (той обмежений білим списком таблиць news_*/market_*/
# candidate_assets).
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis")
)
from expectations._db import mark_notified as mark_expectations_notified  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_recent_news_synthesis(conn, hours: int) -> list[dict]:
    """Лише ще НЕ надіслані (notified_at IS NULL) — окремі notify_synthesis
    (нижче за розкладом) уже надсилає свіжі рядки протягом дня, дайджест
    підбирає тільки те, що вони не встигли/не покрили."""
    return fetch_dicts(
        conn,
        """
        SELECT id, asset_id, cluster_count, net_lean, price_pct_change,
               price_start_date, price_end_date, direction, confidence,
               summary, confirmation_factors
        FROM news_synthesis
        WHERE created_at >= now() - (%s || ' hours')::interval
          AND notified_at IS NULL
        ORDER BY created_at DESC
        """,
        (hours,),
    )


def fetch_recent_market_synthesis(conn, hours: int) -> dict | None:
    """Лише ще НЕ надісланий (notified_at IS NULL) — той самий принцип,
    що fetch_recent_news_synthesis()."""
    return fetch_one_dict(
        conn,
        """
        SELECT id, cluster_count, direction, confidence, summary
        FROM market_synthesis
        WHERE created_at >= now() - (%s || ' hours')::interval
          AND notified_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (hours,),
    )


def fetch_recent_surprises(conn, hours: int) -> list[dict]:
    """Тільки impact_level high/medium — той самий фільтр, що вже в
    expectations_notify.py. `notified_at IS NULL` — той самий принцип,
    що fetch_recent_news_synthesis()."""
    return fetch_dicts(
        conn,
        """
        SELECT ec.id, ec.metric_id, ec.observed_at, ec.actual_value, ec.expected_value_raw,
               ec.expected_value_parsed, ec.surprise, ec.surprise_pct
        FROM expectation_comparisons ec
        JOIN release_log rl ON rl.id = ec.release_log_id
        WHERE ec.created_at >= now() - (%s || ' hours')::interval
          AND rl.impact_level IN ('high', 'medium')
          AND ec.notified_at IS NULL
        ORDER BY ec.created_at DESC
        """,
        (hours,),
    )


def fetch_recent_candidates(conn, hours: int) -> list[dict]:
    """НОВІ рядки candidate_assets за вікно — не весь поточний список,
    тільки те, що з'явилось за --hours (docs/decisions.md, "Ціль 3").
    `notified_at IS NULL` — той самий принцип, що fetch_recent_news_synthesis()."""
    return fetch_dicts(
        conn,
        """
        SELECT id, ticker, company_name, reasoning
        FROM candidate_assets
        WHERE discovered_at >= now() - (%s || ' hours')::interval
          AND notified_at IS NULL
        ORDER BY discovered_at DESC
        """,
        (hours,),
    )


def format_news_synthesis_message(row: dict) -> str:
    """2026-10-02, живий фідбек користувача: без періоду й
    confirmation_factors повідомлення було нерозбірливим "ціна -5%,
    новини +4" без жодного пояснення. Дати й гіпотеза-що-перевірити
    вже рахувались (price_start_date/end_date, confirmation_factors —
    LLM-поле поруч із summary), просто не доходили до самого
    повідомлення."""
    emoji = DIRECTION_EMOJI.get(row["direction"], "❓")
    lines = [
        bold(
            f"{emoji} {row['asset_id']}: ціна {float(row['price_pct_change']):+.2f}% "
            f"({row['price_start_date']} → {row['price_end_date']}), "
            f"новини {row['net_lean']:+d} ({row['cluster_count']} історій)"
        ),
        escape_html(row["summary"]),
    ]
    if row.get("confirmation_factors"):
        lines.append(f"🔎 Перевірити: {escape_html(row['confirmation_factors'])}")
    return "\n".join(lines)


def format_market_synthesis_message(row: dict) -> str:
    label = MARKET_DIRECTION_LABEL.get(row["direction"], row["direction"])
    confidence = float(row["confidence"])
    header = f"🌍 Стан ринку: {label} (упевненість {confidence:.2f})"
    return f"{bold(header)}\n{escape_html(row['summary'])}"


def format_surprise_message(row: dict) -> str:
    label = METRIC_LABELS.get(row["metric_id"], row["metric_id"])
    pct_suffix = f" ({row['surprise_pct']:+.1f}%)" if row["surprise_pct"] is not None else ""
    header = f"📈 {label} — {row['observed_at']}"
    actual = f"{float(row['actual_value']):.4g}"
    return (
        f"{bold(header)}\n"
        f"Факт {bold(actual)} vs очікування "
        f"{float(row['expected_value_parsed']):.4g} (прогноз: {escape_html(row['expected_value_raw'])})\n"
        f"Сюрприз: {float(row['surprise']):+.4g}{pct_suffix}"
    )


def format_candidate_message(row: dict) -> str:
    header = f"🆕 {row['ticker']} — {row['company_name']}"
    return f"{bold(header)}\n{escape_html(row['reasoning'])}"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        news_rows = fetch_recent_news_synthesis(conn, args.hours)
        market_row = fetch_recent_market_synthesis(conn, args.hours)
        surprise_rows = fetch_recent_surprises(conn, args.hours)
        candidate_rows = fetch_recent_candidates(conn, args.hours)

        # (текст, callback позначення notified_at) — маркуємо ОДРАЗУ після
        # успішної відправки КОЖНОГО повідомлення (не одним батчем
        # наприкінці), щоб мережевий збій на половині списку не змусив
        # наступний прогін надіслати вже надіслані рядки вдруге.
        items = []
        if market_row is not None:
            items.append((
                format_market_synthesis_message(market_row),
                lambda r=market_row: mark_notified(conn, "market_synthesis", [r["id"]]),
            ))
        items.extend(
            (format_news_synthesis_message(r), lambda r=r: mark_notified(conn, "news_synthesis", [r["id"]]))
            for r in news_rows
        )
        items.extend(
            (format_surprise_message(r), lambda r=r: mark_expectations_notified(conn, [r["id"]]))
            for r in surprise_rows
        )
        items.extend(
            (format_candidate_message(r), lambda r=r: mark_notified(conn, "candidate_assets", [r["id"]]))
            for r in candidate_rows
        )

        if not items:
            send_telegram_message(token, chat_id, "Сьогодні суттєвих подій не було.")
            logger.info("Надіслано в Telegram: контрольне повідомлення (нового немає)")
            return

        for text, mark_fn in items:
            send_telegram_message(token, chat_id, text, parse_mode="HTML")
            mark_fn()

        logger.info("Надіслано в Telegram: %d повідомлень дайджесту", len(items))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
