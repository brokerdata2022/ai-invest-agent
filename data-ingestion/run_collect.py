#!/usr/bin/env python3
"""
Ручний запуск збору одного показника (для дебагу й для критерію
завершення Фази 0: "можна руками запустити збір і побачити результат у БД").

Використання:
    python run_collect.py --metric cpi
    python run_collect.py --metric fed_funds_rate --limit 10
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
from macro.fred_adapter import FredAdapter, METRICS  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metric", required=True, choices=sorted(METRICS),
        help="внутрішній metric_id (див. macro/fred_adapter.py:METRICS)",
    )
    parser.add_argument(
        "--limit", type=int, default=5,
        help="скільки останніх спостережень забрати (за замовчуванням 5)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        logger.error("FRED_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    adapter = FredAdapter(api_key=api_key, metric_id=args.metric)

    logger.info("Забираю %s (FRED series %s)...", args.metric, adapter.series_id)
    records = adapter.collect(limit=args.limit)
    logger.info("Отримано %d нормалізованих записів", len(records))

    if not records:
        logger.warning("Немає записів для збереження — перевірте API-ключ і series_id")
        sys.exit(0)

    conn = get_connection()
    try:
        inserted = insert_observations(conn, records)
    finally:
        conn.close()

    logger.info("Готово: %d нових/змінених значень записано в raw_observations", inserted)


if __name__ == "__main__":
    main()
