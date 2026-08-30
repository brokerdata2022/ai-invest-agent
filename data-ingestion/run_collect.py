#!/usr/bin/env python3
"""
Ручний запуск збору одного показника (для дебагу й для критерію
завершення Фази 0: "можна руками запустити збір і побачити результат у БД").

Використання:
    python run_collect.py --metric cpi
    python run_collect.py --metric fed_funds_rate --limit 10
    python run_collect.py --metric eurozone_hicp
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
from macro.ecb_adapter import EcbAdapter, METRICS as ECB_METRICS  # noqa: E402
from macro.fred_adapter import FredAdapter, METRICS as FRED_METRICS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Реєстр джерел даних. При додаванні нового адаптера (SEC EDGAR, GDELT, ...)
# додайте сюди запис — CLI, автовизначення --source за metric_id і список
# --metric у --help підхоплять його автоматично, без інших змін у файлі.
ADAPTERS = {
    "fred": {"class": FredAdapter, "metrics": FRED_METRICS, "needs_api_key": "FRED_API_KEY"},
    "ecb": {"class": EcbAdapter, "metrics": ECB_METRICS, "needs_api_key": None},
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
        "--metric", required=True, choices=_all_metric_ids(),
        help="внутрішній metric_id (див. docs/metrics-catalog.md)",
    )
    parser.add_argument(
        "--source", choices=sorted(ADAPTERS), default=None,
        help="джерело даних; за замовчуванням визначається автоматично за --metric",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="скільки останніх спостережень забрати (за замовчуванням 5)",
    )
    args = parser.parse_args()

    source = args.source or _resolve_source(args.metric)
    cfg = ADAPTERS[source]
    if args.metric not in cfg["metrics"]:
        sys.exit(f"metric_id {args.metric!r} не належить джерелу {source!r}.")

    if cfg["needs_api_key"]:
        api_key = os.environ.get(cfg["needs_api_key"])
        if not api_key:
            logger.error(
                "%s не задано. Додайте його в .env (див. .env.example).",
                cfg["needs_api_key"],
            )
            sys.exit(1)
        adapter = cfg["class"](api_key=api_key, metric_id=args.metric)
    else:
        adapter = cfg["class"](metric_id=args.metric)

    logger.info("Забираю %s (джерело %s)...", args.metric, source)
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
