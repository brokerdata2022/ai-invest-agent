#!/usr/bin/env python3
"""
Ручний запуск збору новин (GDELT) для одного потоку. Наразі тільки
watchlist (докладніше news/queries.py, docs/decisions.md 2026-09-25).

Використання:
    python run_collect_news.py --stream watchlist
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
from news.queries import build_watchlist_query  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

QUERY_BUILDERS = {
    "watchlist": build_watchlist_query,
}


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=sorted(QUERY_BUILDERS), default="watchlist")
    parser.add_argument("--maxrecords", type=int, default=75)
    args = parser.parse_args()

    query = QUERY_BUILDERS[args.stream]()
    logger.info("GDELT query (%s): %s", args.stream, query)

    adapter = GdeltAdapter(stream=args.stream, query=query)
    records = adapter.collect(maxrecords=args.maxrecords)
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
