#!/usr/bin/env python3
"""
Ручний запуск збору новин (GDELT) для одного потоку — watchlist
(docs/watchlist.md, не-акційна частина), geopolitical або general
(докладніше news/queries.py, docs/decisions.md 2026-09-25/26). Акції
зі скринінгу — окремий скрипт, analysis/news_analysis/collect_stock_news.py.

Використання:
    python run_collect_news.py --stream watchlist
    python run_collect_news.py --stream geopolitical
    python run_collect_news.py --stream general
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_connection  # noqa: E402
from common.news_db import insert_news_batch  # noqa: E402
from news.gdelt_adapter import GdeltAdapter  # noqa: E402
from news.queries import (  # noqa: E402
    build_general_query,
    build_geopolitical_query,
    build_watchlist_query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QUERY_BUILDERS = {
    "watchlist": build_watchlist_query,
    "geopolitical": build_geopolitical_query,
    "general": build_general_query,
}


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=sorted(QUERY_BUILDERS), default="watchlist")
    parser.add_argument("--maxrecords", type=int, default=75)
    parser.add_argument(
        "--timespan", default="3d",
        help="скільки часу назад шукати (GDELT-формат, напр. 3d/1w) — "
             "без обмеження GDELT віддає найновіші maxrecords збігів "
             "БЕЗ огляду на давність, це можуть бути місяці старі статті",
    )
    args = parser.parse_args()

    query = QUERY_BUILDERS[args.stream]()
    logger.info("GDELT query (%s, timespan=%s): %s", args.stream, args.timespan, query)

    adapter = GdeltAdapter(stream=args.stream, query=query)
    records = adapter.collect(maxrecords=args.maxrecords, timespan=args.timespan)
    logger.info("Отримано %d статей", len(records))

    if not records:
        logger.warning("Немає статей — перевірте query чи доступність GDELT")
        sys.exit(0)

    conn = get_connection()
    try:
        inserted = insert_news_batch(conn, records)
    finally:
        conn.close()

    logger.info("Готово: %d нових статей записано в raw_news", inserted)


if __name__ == "__main__":
    main()
