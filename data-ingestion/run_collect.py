#!/usr/bin/env python3
"""
Ручний запуск збору одного показника (для дебагу й для критерію
завершення Фази 0: "можна руками запустити збір і побачити результат у БД").

Використання:
    python run_collect.py --metric cpi
    python run_collect.py --metric fed_funds_rate --limit 10
    python run_collect.py --metric eurozone_hicp
    python run_collect.py --source twelvedata --ticker AAPL
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# Дозволяє імпортувати "common" і "macro" як пакети незалежно від того,
# звідки скрипт запущено (тека data-ingestion/ не є валідним іменем
# Python-пакета через дефіс, тож імпортуємо напряму з її вмісту).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_connection, insert_observations  # noqa: E402
from macro.boj_adapter import BojAdapter, METRICS as BOJ_METRICS  # noqa: E402
from macro.ecb_adapter import EcbAdapter, METRICS as ECB_METRICS  # noqa: E402
from macro.estat_adapter import EstatAdapter, METRICS as ESTAT_METRICS  # noqa: E402
from macro.fred_adapter import FredAdapter, METRICS as FRED_METRICS  # noqa: E402
from companies.sec_edgar_adapter import SecEdgarAdapter  # noqa: E402
from quotes.twelvedata_adapter import TwelveDataAdapter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Реєстр джерел даних. При додаванні нового адаптера (SEC EDGAR, GDELT, ...)
# додайте сюди запис — CLI, автовизначення --source за metric_id і список
# --metric у --help підхоплять його автоматично, без інших змін у файлі.
#
# "id_kwarg" — назва kwarg конструктора адаптера, яким передається
# ідентифікатор того, що забирати. Для macro/*-адаптерів це завжди
# "metric_id" (фіксований METRICS-словник — див. docs/decisions.md,
# 2026-09-14, "companies/ — спершу скринінг"). Для quotes/twelvedata_adapter.py
# (і майбутнього companies/ SEC EDGAR) — "ticker": тикер довільний,
# не з фіксованого списку, тому "metrics" тут порожній dict, і такі
# джерела викликаються через --ticker, не --metric (див. main() нижче).
ADAPTERS = {
    "fred": {"class": FredAdapter, "metrics": FRED_METRICS, "needs_api_key": "FRED_API_KEY", "id_kwarg": "metric_id"},
    "ecb": {"class": EcbAdapter, "metrics": ECB_METRICS, "needs_api_key": None, "id_kwarg": "metric_id"},
    "boj": {"class": BojAdapter, "metrics": BOJ_METRICS, "needs_api_key": None, "id_kwarg": "metric_id"},
    "estat": {"class": EstatAdapter, "metrics": ESTAT_METRICS, "needs_api_key": "ESTAT_APP_ID", "id_kwarg": "metric_id"},
    "twelvedata": {"class": TwelveDataAdapter, "metrics": {}, "needs_api_key": "TWELVEDATA_API_KEY", "id_kwarg": "ticker"},
    "sec_edgar": {"class": SecEdgarAdapter, "metrics": {}, "needs_api_key": "SEC_EDGAR_USER_AGENT", "id_kwarg": "ticker"},
}


def _all_metric_ids() -> list[str]:
    return sorted({m for cfg in ADAPTERS.values() for m in cfg["metrics"]})


def _resolve_source(metric_id: str) -> str:
    matches = [name for name, cfg in ADAPTERS.items() if metric_id in cfg["metrics"]]
    if not matches:
        sys.exit(f"Невідомий metric_id: {metric_id!r}. Доступні: {_all_metric_ids()}")
    if len(matches) > 1:
        sys.exit(f"metric_id {metric_id!r} присутній у кількох джерелах {matches} — вкажіть --source явно.")
    return matches[0]


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metric", choices=_all_metric_ids(), default=None,
        help="внутрішній metric_id для джерел з фіксованим списком показників "
             "(див. docs/metrics-catalog.md); взаємовиключно з --ticker",
    )
    parser.add_argument(
        "--ticker", default=None,
        help="тикер для джерел з динамічним metric_id (напр. --source twelvedata "
             "--ticker AAPL); взаємовиключно з --metric, вимагає явного --source",
    )
    parser.add_argument(
        "--source", choices=sorted(ADAPTERS), default=None,
        help="джерело даних; для --metric визначається автоматично, "
             "для --ticker треба вказати явно",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="скільки останніх спостережень забрати (за замовчуванням 5; "
             "для twelvedata передається як outputsize)",
    )
    args = parser.parse_args()

    if args.metric and args.ticker:
        sys.exit("Вкажіть або --metric, або --ticker, не обидва.")
    if not args.metric and not args.ticker:
        sys.exit("Потрібен --metric або --ticker.")

    if args.ticker:
        if not args.source:
            sys.exit(
                "Для --ticker потрібно явно вказати --source "
                f"(один із {sorted(ADAPTERS)})."
            )
        source = args.source
        cfg = ADAPTERS[source]
        identifier = args.ticker
    else:
        source = args.source or _resolve_source(args.metric)
        cfg = ADAPTERS[source]
        if args.metric not in cfg["metrics"]:
            sys.exit(f"metric_id {args.metric!r} не належить джерелу {source!r}.")
        identifier = args.metric

    id_kwargs = {cfg["id_kwarg"]: identifier}

    if cfg["needs_api_key"]:
        api_key = os.environ.get(cfg["needs_api_key"])
        if not api_key:
            logger.error(
                "%s не задано. Додайте його в .env (див. .env.example).",
                cfg["needs_api_key"],
            )
            sys.exit(1)
        adapter = cfg["class"](api_key=api_key, **id_kwargs)
    else:
        adapter = cfg["class"](**id_kwargs)

    logger.info("Забираю %s (джерело %s)...", identifier, source)
    records = adapter.collect(limit=args.limit)
    logger.info("Отримано %d нормалізованих записів", len(records))

    if not records:
        logger.warning("Немає записів для збереження — перевірте API-ключ і series_id/series_key")
        sys.exit(0)

    conn = get_connection()
    try:
        inserted = insert_observations(conn, records)
    finally:
        conn.close()

    logger.info("Готово: %d нових/змінених значень записано в raw_observations", inserted)


if __name__ == "__main__":
    main()
