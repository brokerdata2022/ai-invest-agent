#!/usr/bin/env python3
"""
Tier A скринінгу акцій — ліквідність (docs/screening-criteria.md).

Читає вже зібрані дані з raw_observations (через views v_current_values/
v_observations_latest_revision) — Twelve Data для ціни/обсягу, SEC
EDGAR для shares_outstanding (капіталізація). Не звертається до
жодного зовнішнього API напряму — CLAUDE.md, правило #1:
analysis/ тільки читає зі сховища data-ingestion/, ніколи не
дублює логіку збору.

Критерії (docs/screening-criteria.md, узгоджено 2026-09-20):
- ціна > $10
- ринкова капіталізація > $10 млрд (ціна × shares_outstanding)
- середній доларовий обсяг торгів (3 міс, ~63 торгових дні) > $10 млн/день

Передумова: обидва data-ingestion/collect_universe.py (Twelve Data) і
data-ingestion/collect_companies_universe.py (SEC EDGAR) мають бути
прогнані на весь S&P 500 заздалегідь — інакше тикери без
shares_outstanding просто пропускаються з попередженням, а не
падають (див. _run у логах).

Використання:
    python analysis/screening/tier_a.py
"""

import logging
import os
import sys
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data-ingestion"),
)
from common.db import get_connection  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MIN_PRICE = Decimal("10")
MIN_MARKET_CAP = Decimal("10000000000")      # $10 млрд
MIN_AVG_DOLLAR_VOLUME = Decimal("10000000")  # $10 млн/день
LOOKBACK_DAYS = 63  # ~3 торгових місяці (docs/screening-criteria.md)


@dataclass
class TierAResult:
    ticker: str
    price: Decimal
    market_cap: Decimal
    avg_dollar_volume: Decimal


def passes_tier_a(price: Decimal, market_cap: Decimal, avg_dollar_volume: Optional[Decimal]) -> bool:
    """Чиста функція без звернень до БД — критерії Tier A окремо від
    того, як дані добуті, щоб можна було протестувати без живої БД."""
    if avg_dollar_volume is None:
        return False
    return (
        price > MIN_PRICE
        and market_cap > MIN_MARKET_CAP
        and avg_dollar_volume > MIN_AVG_DOLLAR_VOLUME
    )


def _tickers_with_quotes(conn) -> list[str]:
    suffix = "_close"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT metric_id FROM v_current_values "
            "WHERE source = 'twelvedata' AND metric_id LIKE '%%' || %s",
            (suffix,),
        )
        return sorted(row[0][: -len(suffix)] for row in cur.fetchall())


def _latest_value(conn, source: str, metric_id: str) -> Optional[Decimal]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT value FROM v_current_values WHERE source = %s AND metric_id = %s",
            (source, metric_id),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _avg_dollar_volume(conn, ticker: str) -> Optional[Decimal]:
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH closes AS (
                SELECT observed_at, value AS close
                FROM v_observations_latest_revision
                WHERE source = 'twelvedata' AND metric_id = %s
                ORDER BY observed_at DESC LIMIT %s
            ),
            volumes AS (
                SELECT observed_at, value AS volume
                FROM v_observations_latest_revision
                WHERE source = 'twelvedata' AND metric_id = %s
                ORDER BY observed_at DESC LIMIT %s
            )
            SELECT AVG(c.close * v.volume)
            FROM closes c JOIN volumes v ON v.observed_at = c.observed_at
            """,
            (f"{ticker}_close", LOOKBACK_DAYS, f"{ticker}_volume", LOOKBACK_DAYS),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None


def run_tier_a() -> list[TierAResult]:
    conn = get_connection()
    try:
        tickers = _tickers_with_quotes(conn)
        logger.info("Тикерів з котируваннями (Twelve Data): %d", len(tickers))

        passed: list[TierAResult] = []
        skipped_no_shares = []
        for ticker in tickers:
            price = _latest_value(conn, "twelvedata", f"{ticker}_close")
            shares = _latest_value(conn, "sec_edgar", f"{ticker}_shares_outstanding")
            if price is None:
                continue
            if shares is None:
                skipped_no_shares.append(ticker)
                continue

            market_cap = price * shares
            avg_dollar_volume = _avg_dollar_volume(conn, ticker)

            if passes_tier_a(price, market_cap, avg_dollar_volume):
                passed.append(TierAResult(
                    ticker=ticker.upper(), price=price,
                    market_cap=market_cap, avg_dollar_volume=avg_dollar_volume,
                ))

        logger.info("Tier A пройшли: %d з %d", len(passed), len(tickers))
        if skipped_no_shares:
            preview = ", ".join(skipped_no_shares[:20])
            more = "..." if len(skipped_no_shares) > 20 else ""
            logger.warning(
                "Пропущено (немає shares_outstanding з SEC EDGAR): %d — %s%s. "
                "Прогнано collect_companies_universe.py?",
                len(skipped_no_shares), preview, more,
            )
        return passed
    finally:
        conn.close()


if __name__ == "__main__":
    results = run_tier_a()
    results.sort(key=lambda r: r.market_cap, reverse=True)

    print(f"\n{'Тикер':<8}{'Ціна':>12}{'Капіталізація':>20}{'Сер.$ обсяг/день':>22}")
    for r in results:
        print(f"{r.ticker:<8}{r.price:>12,.2f}{r.market_cap:>20,.0f}{r.avg_dollar_volume:>22,.0f}")
    print(f"\nВсього пройшли Tier A: {len(results)}")
