#!/usr/bin/env python3
"""
Ручний запуск збору новин (GDELT) для одного потоку — watchlist
(docs/watchlist.md, не-акційна частина) або general (докладніше
news/queries.py, docs/decisions.md 2026-09-25/26). Акції зі скринінгу —
окремий скрипт, analysis/news_analysis/collect_stock_news.py.

geopolitical-стрім більше НЕ збирається через GDELT тут — замінено на
широкі RSS-фіди (news/rss_feeds.py, run_collect_rss.py),
docs/decisions.md 2026-09-27.

Використання:
    python run_collect_news.py --stream watchlist
    python run_collect_news.py --stream general
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.db import get_connection  # noqa: E402
from common.news_db import insert_news_batch  # noqa: E402
from news.gdelt_adapter import GdeltAdapter, GdeltError  # noqa: E402
from news.queries import (  # noqa: E402
    build_general_queries,
    build_watchlist_query,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Кожен білдер повертає list[str] — один чи кілька окремих GDELT-запитів
# для того самого стріму (general — два, через ліміт довжини GDELT,
# news/queries.py). watchlist лишається одним, обгорнутим у список для
# однакової обробки нижче.
QUERY_BUILDERS = {
    "watchlist": lambda: [build_watchlist_query()],
    "general": build_general_queries,
}


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=sorted(QUERY_BUILDERS), default="watchlist")
    parser.add_argument("--maxrecords", type=int, default=75)
    parser.add_argument(
        "--timespan", default="1d",
        help="скільки часу назад шукати (GDELT-формат, напр. 1d/3d) — "
             "без обмеження GDELT віддає найновіші maxrecords збігів "
             "БЕЗ огляду на давність, це можуть бути місяці старі статті",
    )
    args = parser.parse_args()

    queries = QUERY_BUILDERS[args.stream]()

    all_records = []
    any_query_failed = False
    for query in queries:
        logger.info("GDELT query (%s, timespan=%s): %s", args.stream, args.timespan, query)
        adapter = GdeltAdapter(stream=args.stream, query=query)
        try:
            records = adapter.collect(maxrecords=args.maxrecords, timespan=args.timespan)
        except (requests.exceptions.RequestException, GdeltError):
            # Транзієнтний збій GDELT (429 понад retry-бюджет адаптера,
            # мережевий тайм-аут) — той самий підхід, що
            # collect_stock_news.py/run_collect_rss.py: лог без
            # трасування, ОДИН провалений query не повинен зупиняти
            # решту (general тепер два незалежні запити).
            logger.exception("Пропущено query (мережева помилка GDELT): %s", query)
            any_query_failed = True
            continue
        logger.info("Отримано %d статей", len(records))
        all_records.extend(records)

    if not all_records:
        if any_query_failed:
            # Усі запити впали (network/429) — справжній провал, не
            # "просто нема свіжих новин". runner.py має його ретраїти
            # й сповістити, якщо ретрай теж не допоможе — інакше
            # мережевий збій тихо виглядав би як "0 статей", exit(0).
            logger.error("Усі GDELT-запити (%s) провалились", args.stream)
            sys.exit(1)
        logger.warning("Немає статей — перевірте query(і) чи доступність GDELT")
        sys.exit(0)

    conn = get_connection()
    try:
        inserted = insert_news_batch(conn, all_records)
    finally:
        conn.close()

    logger.info("Готово: %d нових статей записано в raw_news", inserted)


if __name__ == "__main__":
    main()
