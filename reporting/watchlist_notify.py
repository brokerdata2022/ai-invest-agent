#!/usr/bin/env python3
"""
Сповіщення в Telegram про поточні ціни watchlist-активів (золото,
срібло, нафта WTI/Brent, кава, EUR/USD, USD/JPY, BTC, ETH, SOL —
docs/watchlist.md). Тільки форматування вже зібраних цін
(reporting/CLAUDE.md) — жодної аналітики.

Раніше для watchlist не було зведеного звіту — лише
telegram_notify.py --metric <id> по ОДНОМУ показнику за раз (9
окремих команд, щоб побачити весь список). Той самий формат виводу,
що вже є в screening_notify.py: актив, ціна, % зміна за 24г.

Дублює мапінг asset_id -> (source, metric_id) з
analysis/news_analysis/prices.py:ASSET_PRICE_SOURCES — свідомо, не
імпорт (reporting/ не імпортує з analysis/, reporting/CLAUDE.md
"Контейнерна незалежність" — той самий принцип, що METRIC_LABELS/
_METRIC_SOURCE у telegram_notify.py).

Без дедупу notified_at (на відміну від screening_notify.py) — це
ЗНІМОК поточного стану (як сам telegram_notify.py), не подія з
таблиці типу "щось нового з'явилось": показати ту саму ціну вдруге
при повторному ручному запуску — очікувана поведінка, не помилка.

Використання:
    python watchlist_notify.py
"""

import argparse
import logging
from decimal import Decimal

from dotenv import load_dotenv

# _common додає data-ingestion у sys.path (дефіс у назві теки —
# не валідне ім'я Python-пакета), тому імпортується ПЕРШИМ.
from _common import resolve_telegram_credentials  # noqa: E402
from common.db import fetch_recent, get_connection  # noqa: E402
from telegram_client import send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# (asset_id, source, metric_id, людська назва) — той самий порядок,
# що docs/watchlist.md.
WATCHLIST_ASSETS: list[tuple[str, str, str, str]] = [
    ("xauusd", "twelvedata", "xauusd_close", "Золото (XAU/USD)"),
    ("xagusd", "coingecko", "xagusd_close", "Срібло (XAG/USD)"),
    ("wti_crude", "fred", "wti_crude", "Нафта WTI"),
    ("brent_crude", "fred", "brent_crude", "Нафта Brent"),
    ("coffee", "fred", "coffee", "Кава"),
    ("eurusd", "twelvedata", "eurusd_close", "EUR/USD"),
    ("usdjpy", "twelvedata", "usdjpy_close", "USD/JPY"),
    ("btc", "binance", "btc_close", "BTC/USDT"),
    ("eth", "binance", "eth_close", "ETH/USDT"),
    ("sol", "binance", "sol_close", "SOL/USDT"),
]


def fetch_watchlist_snapshot(conn) -> list[dict]:
    """Остання ціна + %-зміна за 24г (попередня точка, найновіше
    перше — fetch_recent()) для кожного watchlist-активу. Актив без
    жодної точки просто пропускається (щойно підключене джерело чи
    тимчасовий збій збору) — не падає на весь список через один."""
    rows = []
    for asset_id, source, metric_id, label in WATCHLIST_ASSETS:
        series = fetch_recent(conn, source, metric_id, limit=2)
        if not series:
            continue
        latest = series[0]
        change_pct = None
        if len(series) >= 2 and series[1]["value"]:
            change_pct = (latest["value"] - series[1]["value"]) / series[1]["value"] * Decimal("100")
        rows.append(
            {
                "asset_id": asset_id,
                "label": label,
                "price": latest["value"],
                "observed_at": latest["observed_at"],
                "change_pct": change_pct,
            }
        )
    return rows


def _format_price(value: Decimal) -> str:
    """>=100 -- 2 знаки (BTC/золото/нафта), <100 -- 4 знаки (форекс-
    пари типу EUR/USD, де 2 знаки губили б увесь рух)."""
    value_f = float(value)
    decimals = 2 if abs(value_f) >= 100 else 4
    return f"{value_f:,.{decimals}f}"


def format_message(rows: list[dict]) -> str:
    if not rows:
        return "💰 Дані watchlist-активів ще не зібрані."

    dates = [row["observed_at"] for row in rows if row.get("observed_at")]
    date_str = f" (дані на {max(dates).isoformat()})" if dates else ""

    lines = [f"💰 Watchlist — поточні ціни{date_str}", ""]
    for row in rows:
        change = row.get("change_pct")
        change_str = f"{float(change):+.2f}%" if change is not None else "н/д"
        lines.append(f"{row['label']} — {_format_price(row['price'])} | 24г: {change_str}")
    return "\n".join(lines).rstrip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()  # лише для --help/валідації: скрипт без параметрів

    token, chat_id = resolve_telegram_credentials()

    conn = get_connection()
    try:
        rows = fetch_watchlist_snapshot(conn)
    finally:
        conn.close()

    if not rows:
        logger.info("Жодного watchlist-активу з даними — сповіщення не надсилається")
        return

    text = format_message(rows)
    send_telegram_message(token, chat_id, text)
    logger.info("Надіслано в Telegram: watchlist, %d активів", len(rows))


if __name__ == "__main__":
    main()
