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
from datetime import datetime, timedelta, timezone
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


def _crypto_derivatives_collect() -> None:
    """Щоденний bulk-знімок 3 бірж ф'ючерсів (обсяг/funding/OI, де
    доступно bulk) — для крипто-скринінгу лонг/шорт/спостереження
    (analysis/crypto_screening/, PLAN.md Фаза 4, крок 4.5). Той самий
    підхід, що _crypto_prices(): одна біржа не валить решту.

    Критично для самої скринінг-логіки (не просто "збір заради збору"):
    `screen_long`/`screen_short_or_watch` (crypto_screening/) рахують
    зміну OI/обсягу за кілька днів — без цієї джоби raw_observations
    ніколи не накопичить історію, скільки не чекай (docs/decisions.md,
    2026-09-27, "крок 4.5")."""
    sys.path.insert(0, str(REPO_ROOT / "data-ingestion"))
    from common.db import get_connection, insert_observations  # noqa: E402
    from crypto.binance_futures_adapter import BinanceFuturesAdapter  # noqa: E402
    from crypto.bybit_futures_adapter import BybitFuturesAdapter  # noqa: E402
    from crypto.okx_futures_adapter import OkxFuturesAdapter  # noqa: E402

    conn = get_connection()
    try:
        for adapter_class in (BinanceFuturesAdapter, BybitFuturesAdapter, OkxFuturesAdapter):
            try:
                records = adapter_class().collect()
                if records:
                    inserted = insert_observations(conn, records)
                    logger.info(
                        "%s: %d записів (%d нових/змінених)",
                        adapter_class.source, len(records), inserted,
                    )
            except Exception:
                logger.error("%s: провалилось", adapter_class.source, exc_info=True)
                conn.rollback()
    finally:
        conn.close()


# asset_id (Twelve Data джерело в ASSET_PRICE_SOURCES) → тикер, яким
# TwelveDataAdapter реально треба викликати (не сам metric_id —
# "xauusd_close" не відновити назад у "XAU/USD", слеш уже втрачено
# нормалізацією адаптера). eurusd/usdjpy додані 2026-10-02 — перейшли
# з FRED (DEXUSEU/DEXJPUS), де публікація зависла на 2026-09-25 попри
# заявлену щоденну частоту (docs/decisions.md 2026-10-02, живо
# підтверджено на fred.stlouisfed.org).
_TWELVEDATA_TICKER_BY_ASSET = {
    "xauusd": "XAU/USD",
    "eurusd": "EUR/USD",
    "usdjpy": "USD/JPY",
}

# Джерела в ASSET_PRICE_SOURCES, які ця джоба НЕ збирає сама — btc/eth/
# sol/xagusd (2026-10-02) уже збираються _crypto_prices()@щогодини.
_CRYPTO_OWNED_SOURCES = {"binance", "coingecko"}


def _watchlist_prices() -> None:
    """Збирає ціни watchlist-товарів/форексу/золота (FredAdapter для
    fred-джерел, TwelveDataAdapter для xauusd/eurusd/usdjpy), ПОТІМ
    логує % зміни.

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
                elif source in _CRYPTO_OWNED_SOURCES:
                    # btc/eth/sol/xagusd (2026-10-02, prices.py:ASSET_PRICE_SOURCES) —
                    # уже збираються _crypto_prices()@щогодини, не тут;
                    # без цього кожен прогін цієї джоби логував би
                    # хибне "невідоме джерело" на ці чотири активи.
                    continue
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


LOG_RETENTION_DAYS = 14


def _prune_logs() -> None:
    """Видаляє файли logs/*.log, старші за LOG_RETENTION_DAYS.

    Кожен запуск джоби пише окремий файл (runner.py:_log_path) — за
    поточним розкладом це ~150 файлів на добу (лише check_releases —
    96), тобто десятки тисяч за місяць безперервної роботи на VPS.
    Логи — не джерело істини (rule 6 захищає сирі ДАНІ в БД, не
    раннтайм-вивід джоб; logs/ тому й у .gitignore), тож їх можна
    прибирати. 14 днів — достатньо, щоб розібрати будь-який провал
    постфактум, і достатньо мало, щоб диск не ріс нескінченно."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOG_RETENTION_DAYS)
    log_dir = REPO_ROOT / "logs"
    if not log_dir.is_dir():
        logger.info("logs/ ще не існує — нічого прибирати")
        return

    removed = 0
    for path in log_dir.glob("*.log"):
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            # Один нечитабельний файл не повинен валити прибирання решти.
            logger.warning("не вдалось прибрати %s", path, exc_info=True)

    logger.info(
        "Прибрано %d логів, старших за %d днів (лишилось %d)",
        removed, LOG_RETENTION_DAYS, len(list(log_dir.glob("*.log"))),
    )


def _prune_raw_news() -> None:
    """Видаляє raw_news, старші за RETENTION_HOURS (2026-09-28,
    рішення користувача — raw_news НЕ append-only-вічний, свідомий
    виняток із rule 6, common/news_db.py). Логіка/SQL — у
    data-ingestion/common/news_db.py (rule 1: orchestration лише
    викликає, нуль бізнес-логіки)."""
    sys.path.insert(0, str(REPO_ROOT / "data-ingestion"))
    from common.db import get_connection  # noqa: E402
    from common.news_db import prune_stale_news  # noqa: E402

    conn = get_connection()
    try:
        deleted = prune_stale_news(conn)
        logger.info("Видалено %d застарілих новин з raw_news", deleted)
    finally:
        conn.close()


JOBS = {
    "check_releases": {
        "subprocess": _py(str(REPO_ROOT / "monitoring" / "check_releases.py")),
    },
    "refresh_calendar": {
        "subprocess": _py(str(REPO_ROOT / "monitoring" / "refresh_calendar.py")),
    },
    "update_forecasts": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "forecasting" / "update_forecasts.py")),
    },
    "compare_expectations": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "expectations" / "compare_releases.py")),
    },
    "synthesize_expectations": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "expectations" / "synthesize.py")),
    },
    "notify_expectations": {
        "subprocess": _py(str(REPO_ROOT / "reporting" / "expectations_notify.py")),
    },
    "news_collect_watchlist": {
        # retries=3 (не дефолтний 1) — 2026-09-29, живо: двічі за добу
        # всі 4 внутрішні спроби адаптера (5с/10с/20с бекоф) + 1
        # дефолтний ретрай runner.py (~60с пізніше) НЕ покрили тривале
        # вікно GDELT 429 на спільному dev-IP. 3 ретраї — до 4 повних
        # циклів ~60с один від одного, ширше вікно на те, щоб ліміт
        # звільнився.
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_news.py"), "--stream", "watchlist"),
        "retries": 3,
    },
    "news_collect_general": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_news.py"), "--stream", "general"),
        "retries": 3,
    },
    "news_collect_rss": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "run_collect_rss.py")),
    },
    "news_collect_stock": {
        # той самий принцип, що news_collect_watchlist/general вище —
        # теж GDELT, той самий 429-ризик на спільному IP.
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "collect_stock_news.py")),
        "retries": 3,
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
    "news_consolidate_watchlist": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "consolidate.py"), "--stream", "watchlist"),
    },
    "news_consolidate_general": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "consolidate.py"), "--stream", "general"),
    },
    "news_consolidate_geopolitical": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "consolidate.py"), "--stream", "geopolitical"),
    },
    "news_merge_similar": {
        # Семантичне об'єднання дублів МІЖ прогонами consolidate.py
        # (2026-09-29, живий приклад — 3 незалежні переклади "золото
        # впало на 7-тижневий мінімум" пішли 3 окремими записами;
        # text-similarity підтверджено ненадійним, потрібен окремий
        # фокусований LLM-виклик). Без --stream — усі 3 потоки.
        "subprocess": _py(str(REPO_ROOT / "analysis" / "news_analysis" / "merge_similar.py")),
    },
    "news_notify": {
        # Без --stream — ОДНЕ сповіщення з усіх зібраних потоків разом
        # (watchlist+general+geopolitical), рішення користувача
        # 2026-09-28: "важливі новини мають бути не тільки з watchlist
        # а зі всіх зібраних новин".
        "subprocess": _py(str(REPO_ROOT / "reporting" / "news_notify.py")),
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
    "crypto_derivatives_collect": {
        "callable": _crypto_derivatives_collect,
    },
    "crypto_screening_daily": {
        # Живо виміряно 2026-09-27: ~3.5 хв на ~150 Tier A-виживших —
        # у межах дефолтного таймауту runner.py (30 хв), окремий не потрібен.
        "subprocess": _py(str(REPO_ROOT / "analysis" / "crypto_screening" / "run_screening.py")),
    },
    "crypto_candidates_monitor": {
        "subprocess": _py(str(REPO_ROOT / "analysis" / "crypto_screening" / "monitor_candidates.py")),
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
        # retries=0: другий повний ~26-хв прогін одразу після провалу
        # (runner.py, дефолт — 1 ретрай) лише вдруге вперся б у те саме
        # джерело без паузи, і зсунув би наступну щотижневу джобу —
        # append-only дедуп все одно робить наступний ЗАПЛАНОВАНИЙ
        # прогін безпечним надолуженням.
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_companies_universe.py")),
        "timeout": 3000,
        "retries": 0,
    },
    "quotes_universe_refresh": {
        # Весь S&P 500 (503 тикери), Twelve Data — ліміт 8 запитів/хв
        # робить це НАЙПОВІЛЬНІШОЮ джобою в конвеєрі: живо виміряно
        # 2026-09-27 — ~78 хв. Дефолтний runner.py timeout (30 хв) робив
        # цю ЩОДЕННУ джобу приречена на TimeoutExpired щоразу (живий
        # провал, знайдений під час розгортання з нуля) — 90 хв дає
        # реальний запас. retries=0 — той самий принцип, що вище: другий
        # ~78-хв прогін одразу після провалу лише вдруге вичерпав би той
        # самий добовий ліміт Twelve Data без користі.
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_universe.py")),
        "timeout": 5400,
        "retries": 0,
    },
    "safety_net_collect_all": {
        "subprocess": _py(str(REPO_ROOT / "data-ingestion" / "collect_all.py"), "--limit", "15"),
    },
    "prune_logs": {
        "callable": _prune_logs,
    },
    "prune_raw_news": {
        "callable": _prune_raw_news,
    },
}
