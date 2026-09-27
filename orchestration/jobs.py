"""
Реєстр ЩО виконати для кожної джоби, названої в schedule.py. Тільки
виклик існуючих скриптів/функцій — жодної бізнес-логіки тут (critical
rule 1 кореневого CLAUDE.md, orchestration/CLAUDE.md).

Два типи джоб:
- "subprocess": [sys.executable, "<шлях скрипта>", ...args] — той самий
  скрипт, що можна запустити руками через
  `docker compose exec app python <шлях> ...`.
- "callable": пряма Python-функція (для коду без CLI, напр. prices.py)
  — виконується в тому самому процесі/образі/.env, що scheduler.
"""

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


def _py(*args: str) -> list:
    return [sys.executable, *args]


def _crypto_prices() -> None:
    """Best-effort перебір Binance+CoinGecko метрик (BTC/ETH/SOL +
    xagusd) — той самий підхід, що data-ingestion/collect_all.py: одна
    метрика не валить решту."""
    sys.path.insert(0, str(REPO_ROOT / "data-ingestion"))
    from common.db import get_connection, insert_observations  # noqa: E402
    from crypto.binance_adapter import BinanceAdapter, METRICS as BINANCE_METRICS  # noqa: E402
    from crypto.coingecko_adapter import CoinGeckoAdapter, METRICS as COINGECKO_METRICS  # noqa: E402

    conn = get_connection()
    try:
        for adapter_class, metrics in (
            (BinanceAdapter, BINANCE_METRICS),
            (CoinGeckoAdapter, COINGECKO_METRICS),
        ):
            for metric_id in sorted(metrics):
                try:
                    records = adapter_class(metric_id=metric_id).collect(limit=5)
                    if records:
                        inserted = insert_observations(conn, records)
                        logger.info("%s: %d записів (%d нових/змінених)", metric_id, len(records), inserted)
                except Exception:
                    logger.error("%s: провалилось", metric_id, exc_info=True)
                    conn.rollback()
    finally:
        conn.close()


# asset_id (Twelve Data джерело в ASSET_PRICE_SOURCES) → тикер, яким
# TwelveDataAdapter реально треба викликати (не сам metric_id —
# "xauusd_close" не відновити назад у "XAU/USD", слеш уже втрачено
# нормалізацією адаптера). Лише один запис — xauusd єдиний
# twelvedata-актив у ASSET_PRICE_SOURCES.
_TWELVEDATA_TICKER_BY_ASSET = {"xauusd": "XAU/USD"}


def _watchlist_prices() -> None:
    """Збирає ціни watchlist-товарів/форексу/золота (FredAdapter для
    fred-джерел, TwelveDataAdapter для xauusd), ПОТІМ логує % зміни.

    Живо виявлено 2026-09-27 (перевірка "з нуля" на новому Docker
    Engine): ця функція раніше лише ЧИТАЛА fetch_all_price_changes(),
    жодного разу нічого не збираючи — попри щоденний розклад і
    докстрінг, що обіцяв збір. Єдиним (побічним, раз на місяць) шляхом
    ці дані взагалі потрапляли в БД був safety_net_collect_all
    (docs/decisions.md, 2026-09-27)."""
    sys.path.insert(0, str(REPO_ROOT / "analysis"))
    sys.path.insert(0, str(REPO_ROOT / "data-ingestion"))
    from common.db import get_connection, insert_observations  # noqa: E402
    from macro.fred_adapter import FredAdapter  # noqa: E402
    from quotes.twelvedata_adapter import TwelveDataAdapter  # noqa: E402
    from news_analysis.prices import ASSET_PRICE_SOURCES, fetch_all_price_changes  # noqa: E402

    fred_key = os.environ.get("FRED_API_KEY")
    twelvedata_key = os.environ.get("TWELVEDATA_API_KEY")

    conn = get_connection()
    try:
        for asset_id, (source, metric_id) in ASSET_PRICE_SOURCES.items():
            try:
                if source == "fred":
                    if not fred_key:
                        logger.error("%s: FRED_API_KEY не задано — пропущено", asset_id)
                        continue
                    records = FredAdapter(api_key=fred_key, metric_id=metric_id).collect(limit=10)
                elif source == "twelvedata":
                    if not twelvedata_key:
                        logger.error("%s: TWELVEDATA_API_KEY не задано — пропущено", asset_id)
                        continue
                    ticker = _TWELVEDATA_TICKER_BY_ASSET[asset_id]
                    records = TwelveDataAdapter(api_key=twelvedata_key, ticker=ticker).collect(limit=10)
                else:
                    logger.warning("%s: невідоме джерело %r — пропущено", asset_id, source)
                    continue

                if records:
                    inserted = insert_observations(conn, records)
                    logger.info("%s: %d записів (%d нових/змінених)", asset_id, len(records), inserted)
            except Exception:
                logger.error("%s: збір провалився", asset_id, exc_info=True)
                conn.rollback()

        changes = fetch_all_price_changes(conn, list(ASSET_PRICE_SOURCES))
        for asset_id, change in changes.items():
            logger.info("%s: %.2f%% (%s -> %s)", asset_id, change.pct_change, change.start_date, change.end_date)
    finally:
        conn.close()


JOBS = {
    "check_releases": {
        "subprocess": _py(str(REPO_ROOT / "monitoring" / "check_releases.py")),
    },
    "refresh_calendar": {
        "subprocess": _py(str(REPO_ROOT / "monitoring" / "refresh_calendar.py")),
    },
    "compare_expectations": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "expectations" / "compare_releases.py")),
    },
    "notify_expectations": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "expectations_notify.py")),
    },
    "news_collect_watchlist": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_news.py"), "--stream", "watchlist"),
    },
    "news_collect_general": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_news.py"), "--stream", "general"),
    },
    "news_collect_rss": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_rss.py")),
    },
    "news_collect_stock": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "collect_stock_news.py")),
    },
    "news_analysis_watchlist": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "run_news_analysis.py"), "--stream", "watchlist"),
    },
    "news_analysis_geopolitical": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "run_news_analysis.py"), "--stream", "geopolitical"),
    },
    "news_analysis_general": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "run_news_analysis.py"), "--stream", "general"),
    },
    "news_notify_watchlist": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "news_notify.py"), "--stream", "watchlist", "--limit", "5"),
    },
    "news_synthesis": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "synthesize.py")),
    },
    "notify_synthesis": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "synthesis_notify.py")),
    },
    "market_synthesis": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "synthesize_market.py")),
    },
    "notify_market_synthesis": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "market_notify.py")),
    },
    "discover_candidates": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "discover_candidates.py")),
    },
    "notify_candidates": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "candidates_notify.py")),
    },
    "daily_digest": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "daily_digest.py")),
    },
    "crypto_prices": {
        "callable": _crypto_prices,
    },
    "watchlist_prices": {
        "callable": _watchlist_prices,
    },
    "screening_composite_score": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "screening" / "composite_score.py"), "--top", "10"),
    },
    "companies_universe_refresh": {
        # Весь S&P 500 (503 тикери), SEC EDGAR — живо виміряно
        # 2026-09-27: ~26 хв, дефолтний runner.py timeout (30 хв) лишає
        # замало запасу на природний розкид латентності API. 50 хв.
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_companies_universe.py")),
        "timeout": 3000,
    },
    "quotes_universe_refresh": {
        # Весь S&P 500 (503 тикери), Twelve Data — ліміт 8 запитів/хв
        # робить це НАЙПОВІЛЬНІШОЮ джобою в конвеєрі: живо виміряно
        # 2026-09-27 — ~78 хв. Дефолтний runner.py timeout (30 хв) робив
        # цю ЩОДЕННУ джобу приречена на TimeoutExpired щоразу (живий
        # провал, знайдений під час розгортання з нуля) — 90 хв дає
        # реальний запас.
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_universe.py")),
        "timeout": 5400,
    },
    "safety_net_collect_all": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_all.py"), "--limit", "15"),
    },
}
