"""
Watchlist — активи поза акціями S&P 500 (docs/watchlist.md, закрито
2026-09-25): ОДНЕ джерело істини (таблиця watchlist_assets,
db/schema.sql), яке читають news/queries.py (GDELT query),
analysis/news_analysis/ (prices.py/consolidate.py/synthesize.py/
run_news_analysis.py — ціна↔новини, tracked_assets для DeepSeek),
orchestration/jobs.py (_watchlist_prices) і reporting/watchlist_notify.py
(докстрінг кожного з них посилається сюди).

Редагування через Telegram (orchestration/telegram_commands.py,
docs/decisions.md 2026-10-03) обмежено `DYNAMICALLY_ADDABLE_SOURCES` —
лише ті джерела, де тикер/символ — параметр адаптера (на зараз тільки
`quotes/twelvedata_adapter.py`), не фіксований словник METRICS
(fred/binance/coingecko) — новий актив у ЦИХ джерелах і далі вимагає
коду, Telegram-команда прямо каже про це, не вдає можливість, якої
немає.
"""

import logging
from typing import NamedTuple, Optional

from common.freshness import is_stale

logger = logging.getLogger(__name__)


class SourceCandidate(NamedTuple):
    source: str
    metric_id: str
    ticker: Optional[str] = None

DYNAMICALLY_ADDABLE_SOURCES = frozenset({"twelvedata"})

_COLUMNS = "asset_id, source, metric_id, ticker, label, search_term, enabled"


def fetch_watchlist(conn, enabled_only: bool = True) -> list[dict]:
    """Усі рядки watchlist_assets (чи лише enabled, дефолт) — той
    самий ефективний список, що раніше малося на увазі хардкодженими
    словниками (увесь попередній список був "enabled")."""
    query = f"SELECT {_COLUMNS} FROM watchlist_assets"
    if enabled_only:
        query += " WHERE enabled"
    query += " ORDER BY asset_id"
    with conn.cursor() as cur:
        cur.execute(query)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_asset_ids(conn, enabled_only: bool = True) -> list[str]:
    """Той самий перелік, що раніше news/queries.py:WATCHLIST_ASSET_IDS
    (список ключів) — тепер із БД, не з хардкодженого словника."""
    return [row["asset_id"] for row in fetch_watchlist(conn, enabled_only=enabled_only)]


def fetch_terms(conn, enabled_only: bool = True) -> dict[str, str]:
    """Той самий словник, що раніше news/queries.py:WATCHLIST_TERMS.
    Пропускає рядки з search_term=NULL (2026-10-04, живий кейс "BNB":
    актив, чий термін не пройшов live-перевірку GDELT при додаванні,
    бере участь у збиранні ЦІНИ, але НЕ в GDELT-запиті — один поганий
    OR-термін псував запит для ВСІХ watchlist-активів одразу)."""
    return {
        row["asset_id"]: row["search_term"]
        for row in fetch_watchlist(conn, enabled_only=enabled_only)
        if row["search_term"]
    }


def fetch_price_sources(conn, enabled_only: bool = True) -> dict[str, tuple[str, str]]:
    """Той самий словник, що раніше
    analysis/news_analysis/prices.py:ASSET_PRICE_SOURCES."""
    return {row["asset_id"]: (row["source"], row["metric_id"]) for row in fetch_watchlist(conn, enabled_only=enabled_only)}


def find_asset(conn, asset_id: str) -> Optional[dict]:
    """Рядок (включно з вимкненими) за asset_id, або None — для
    перевірки "вже є"/"взагалі існує" перед add/remove у
    telegram_commands.py."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT {_COLUMNS} FROM watchlist_assets WHERE asset_id = %s", (asset_id,))
        row = cur.fetchone()
        if row is None:
            return None
        columns = [d[0] for d in cur.description]
        return dict(zip(columns, row))


def add_asset(
    conn, asset_id: str, source: str, metric_id: str,
    ticker: Optional[str], label: str, search_term: Optional[str],
) -> None:
    """Викликач (telegram_commands.py) МАЄ перевірити find_asset() is
    None заздалегідь для зрозумілого повідомлення користувачу — тут
    просто INSERT, порушення PRIMARY KEY кидається як є.
    `search_term=None` — актив збирає ЦІНУ, але не бере участі в
    GDELT-запиті (2026-10-04, живий кейс "BNB" — fetch_terms() вище
    пропускає такі рядки)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO watchlist_assets (asset_id, source, metric_id, ticker, label, search_term, added_via)
            VALUES (%s, %s, %s, %s, %s, %s, 'telegram')
            """,
            (asset_id, source, metric_id, ticker, label, search_term),
        )
    conn.commit()
    logger.info("watchlist_assets: додано %s (%s/%s)", asset_id, source, metric_id)


def set_search_term(conn, asset_id: str, search_term: Optional[str]) -> bool:
    """Виправити/прибрати (None) GDELT-термін уже доданого активу —
    напр. якщо термін виявився проблемним ПІСЛЯ додавання (живий
    кейс "BNB", 2026-10-04) і потребує корекції без видалення й
    повторного додавання всього рядка. Повертає False, якщо asset_id
    не знайдено."""
    with conn.cursor() as cur:
        cur.execute("UPDATE watchlist_assets SET search_term = %s WHERE asset_id = %s", (search_term, asset_id))
        updated = cur.rowcount > 0
    conn.commit()
    if updated:
        logger.info("watchlist_assets: %s search_term=%r", asset_id, search_term)
    return updated


def set_source(
    conn, asset_id: str, source: str, metric_id: Optional[str] = None, ticker: Optional[str] = None,
) -> bool:
    """Перемкнути джерело вже доданого активу (2026-10-04, живий урок:
    попередні три міграції wti_crude/brent_crude/coffee/natgas на
    web_crosscheck редагувались через `db/schema.sql` UPDATE-рядки,
    що вимагало `apply_schema.py` — забутий ОДИН раз (natgas) дав
    "фікс", який насправді нічого не змінив у живій БД, користувач
    отримав ту саму застарілу ціну вдруге). Відтепер перемикання
    джерела — ЗВИЧАЙНА операція над даними (як set_enabled/
    set_search_term), не зміна схеми — нічого забути застосувати.
    `metric_id`/`ticker=None` (дефолт) лишає поточне значення
    незмінним, передайте явно лише те, що міняється. Повертає False,
    якщо asset_id не знайдено."""
    with conn.cursor() as cur:
        if metric_id is not None and ticker is not None:
            cur.execute(
                "UPDATE watchlist_assets SET source = %s, metric_id = %s, ticker = %s WHERE asset_id = %s",
                (source, metric_id, ticker, asset_id),
            )
        elif metric_id is not None:
            cur.execute(
                "UPDATE watchlist_assets SET source = %s, metric_id = %s WHERE asset_id = %s",
                (source, metric_id, asset_id),
            )
        elif ticker is not None:
            cur.execute(
                "UPDATE watchlist_assets SET source = %s, ticker = %s WHERE asset_id = %s",
                (source, ticker, asset_id),
            )
        else:
            cur.execute("UPDATE watchlist_assets SET source = %s WHERE asset_id = %s", (source, asset_id))
        updated = cur.rowcount > 0
    conn.commit()
    if updated:
        logger.info("watchlist_assets: %s source=%r (metric_id=%r, ticker=%r)", asset_id, source, metric_id, ticker)
    return updated


def choose_freshest_source(conn, asset_id: str, candidates: list[SourceCandidate]) -> SourceCandidate:
    """Автоматичний резерв (2026-10-04, живий фідбек користувача:
    "резервний варіант має вже працювати... коли основне джерело не
    отримує свіжі дані то використовувати резерв") — `candidates` у
    ПОРЯДКУ пріоритету (перший — бажаний, якщо свіжий); функція
    припускає, що викликач (orchestration/jobs.py:_watchlist_prices)
    ВЖЕ спробував зібрати дані з КОЖНОГО кандидата цим прогоном —
    тут лише ОБИРАЄМО, чиє значення читати далі, за свіжістю
    (common/freshness.py:is_stale(), БУДНІ дні — вихідні НЕ
    тригерять перемикання на резерв, ринок просто закритий).

    Побічний ефект: якщо обране джерело відрізняється від поточного
    `watchlist_assets.source` — перемикає (`set_source()`), щоб ВСІ
    подальші читачі (reporting/watchlist_notify.py,
    analysis/news_analysis/prices.py, synthesize.py) автоматично
    пішли на актуальне джерело, без ручного втручання чи
    `apply_schema.py`.

    Якщо ЖОДЕН кандидат не свіжий (усі застарілі) — повертає перший
    (статус-кво, не змінює джерело): немає кращого варіанту просто
    зараз, але `common/freshness.py:is_stale()`-позначка в звіті
    однаково покаже застарілість — чесно, не вдає свіжість, якої
    немає."""
    chosen = candidates[0]
    for candidate in candidates:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(observed_at) FROM raw_observations WHERE source = %s AND metric_id = %s",
                (candidate.source, candidate.metric_id),
            )
            (latest,) = cur.fetchone()
        if latest is not None and not is_stale(latest):
            chosen = candidate
            break

    current = find_asset(conn, asset_id)
    if current is not None and (current["source"], current["metric_id"]) != (chosen.source, chosen.metric_id):
        logger.info(
            "watchlist_assets: %s автоматично перемкнуто %s -> %s (резерв свіжіший)",
            asset_id, current["source"], chosen.source,
        )
        set_source(conn, asset_id, chosen.source, metric_id=chosen.metric_id, ticker=chosen.ticker)
    return chosen


def set_enabled(conn, asset_id: str, enabled: bool) -> bool:
    """Повертає False, якщо asset_id взагалі не знайдено (немає що
    вимикати/включати) — викликач вирішує, що відповісти користувачу."""
    with conn.cursor() as cur:
        cur.execute("UPDATE watchlist_assets SET enabled = %s WHERE asset_id = %s", (enabled, asset_id))
        updated = cur.rowcount > 0
    conn.commit()
    if updated:
        logger.info("watchlist_assets: %s enabled=%s", asset_id, enabled)
    return updated
