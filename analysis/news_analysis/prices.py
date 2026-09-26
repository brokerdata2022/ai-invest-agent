"""
Зчитування цінового руху watchlist-активів за вікно — звичайний код,
без LLM (analysis/CLAUDE.md: "числові порівняння — звичайний код").
Вхід для synthesize.py (зіставлення новинного сигналу з фактичним
рухом ціни — docs/news-purpose.md, ціль 1).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# asset_id (той самий, що news/queries.py:WATCHLIST_ASSET_IDS) →
# (source, metric_id) у raw_observations. Метал/товар/форекс ціни
# додані 2026-09-26 (docs/decisions.md) — metric_id тут навмисно
# НЕ завжди дорівнює asset_id: usdjpy_fx_rate — стара, вже жива FRED-
# серія (до цієї сесії), перейменування зламало б історію (рішення
# користувача, docs/decisions.md 2026-09-26) — мапиться тут явно.
# xagusd відсутній свідомо: Twelve Data XAG/USD вимагає платний план
# (підтверджено живим запитом, docs/decisions.md 2026-09-26). btc/eth/
# sol відсутні: адаптер ще не написано (docs/watchlist.md, план).
ASSET_PRICE_SOURCES: dict[str, tuple[str, str]] = {
    "xauusd": ("twelvedata", "xauusd_close"),
    "wti_crude": ("fred", "wti_crude"),
    "brent_crude": ("fred", "brent_crude"),
    "eurusd": ("fred", "eurusd"),
    "coffee": ("fred", "coffee"),
    "usdjpy": ("fred", "usdjpy_fx_rate"),
}


@dataclass
class PriceChange:
    asset_id: str
    start_value: Decimal
    end_value: Decimal
    start_date: str
    end_date: str
    pct_change: Decimal


def compute_pct_change(
    asset_id: str, start_value: Decimal, start_date: str, end_value: Decimal, end_date: str
) -> PriceChange:
    """Чиста функція — з готових значень рахує % зміни. Розрахунок
    відокремлено від SQL (fetch_price_change нижче), щоб тестувалось
    без БД, той самий принцип, що й passes_tier_*/decide_revision в
    інших модулях проєкту."""
    pct_change = ((end_value - start_value) / start_value) * Decimal("100") if start_value != 0 else Decimal("0")
    return PriceChange(
        asset_id=asset_id,
        start_value=start_value,
        end_value=end_value,
        start_date=start_date,
        end_date=end_date,
        pct_change=pct_change,
    )


def fetch_price_change(conn, asset_id: str, days: int = 7) -> Optional[PriceChange]:
    """Перше й останнє значення (v_observations_latest_revision) за
    останні `days` днів для asset_id — None, якщо asset_id не має
    цінового джерела (ASSET_PRICE_SOURCES) або немає даних у вікні."""
    mapping = ASSET_PRICE_SOURCES.get(asset_id)
    if mapping is None:
        return None
    source, metric_id = mapping

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT observed_at, value
            FROM v_observations_latest_revision
            WHERE source = %s AND metric_id = %s
              AND observed_at >= now() - (%s || ' days')::interval
            ORDER BY observed_at ASC
            """,
            (source, metric_id, days),
        )
        rows = cur.fetchall()

    if len(rows) < 2:
        return None

    (start_date, start_value), (end_date, end_value) = rows[0], rows[-1]
    return compute_pct_change(
        asset_id, Decimal(start_value), str(start_date), Decimal(end_value), str(end_date)
    )


def fetch_all_price_changes(
    conn, asset_ids: list[str], days: int = 7
) -> dict[str, PriceChange]:
    """Те саме для списку активів одразу — пропускає ті, для яких
    немає джерела чи даних (не помилка, просто немає числового
    контексту для цього активу поки що)."""
    result = {}
    for asset_id in asset_ids:
        change = fetch_price_change(conn, asset_id, days=days)
        if change is not None:
            result[asset_id] = change
    return result
