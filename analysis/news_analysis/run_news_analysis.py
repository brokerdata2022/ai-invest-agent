#!/usr/bin/env python3
"""
Ручний запуск DeepSeek-аналізу новин, зібраних у raw_news (news/
gdelt_adapter.py) і ще не проаналізованих.

Для стріму watchlist --tracked-assets за замовчуванням береться з
news/queries.py:WATCHLIST_ASSET_IDS (те саме джерело істини, що й
query для GDELT-збору) — явний --tracked-assets перекриває це.

Використання:
    python run_news_analysis.py --stream watchlist --limit 20
    python run_news_analysis.py --tracked-assets AAPL,NVDA
"""

import argparse
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv
import requests

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection  # noqa: E402
from news.queries import WATCHLIST_ASSET_IDS  # noqa: E402
from news_analysis._db import fetch_unanalyzed, log_llm_call, save_analysis  # noqa: E402
from news_analysis.relevance_filter import analyze_article, DeepSeekResponseError  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Дефолтні tracked_assets per stream, коли --tracked-assets не задано
# явно. Тільки watchlist має фіксований список активів; для
# general/geopolitical дефолту нема (None — build_prompt() просто не
# додає рядок "Відстежувані активи").
_DEFAULT_TRACKED_ASSETS: dict[str, list[str]] = {
    "watchlist": WATCHLIST_ASSET_IDS,
}


def resolve_tracked_assets(
    article_stream: str, explicit: Optional[list[str]]
) -> Optional[list[str]]:
    """Чиста функція вибору tracked_assets для однієї статті — явний
    --tracked-assets завжди виграє, інакше дефолт per stream (лише
    watchlist його має)."""
    return explicit or _DEFAULT_TRACKED_ASSETS.get(article_stream)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=["watchlist", "general", "geopolitical"], default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument(
        "--tracked-assets", default=None,
        help="список через кому (напр. AAPL,NVDA) — перекриває дефолт per stream "
             "(watchlist: news/queries.py:WATCHLIST_ASSET_IDS)",
    )
    args = parser.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY не задано. Додайте його в .env (див. .env.example).")
        sys.exit(1)

    explicit_tracked_assets = args.tracked_assets.split(",") if args.tracked_assets else None

    conn = get_connection()
    try:
        articles = fetch_unanalyzed(conn, stream=args.stream, limit=args.limit)
        logger.info("Знайдено %d непроаналізованих статей", len(articles))

        analyzed = 0
        for article in articles:
            tracked_assets = resolve_tracked_assets(article["stream"], explicit_tracked_assets)
            try:
                result, prompt, raw_content = analyze_article(
                    article, article["stream"], api_key, tracked_assets=tracked_assets
                )
            except DeepSeekResponseError:
                logger.exception("Пропускаю статтю %s: некоректна відповідь DeepSeek", article["url"])
                continue
            except requests.exceptions.RequestException:
                # Тимчасовий мережевий збій (DNS/timeout/5xx) на ОДНІЙ
                # статті не повинен губити решту вже готового пакету —
                # решта articles обробляються далі, цю можна повторити
                # наступним запуском (fetch_unanalyzed() підбере знову,
                # бо для неї ще нема рядка в news_analysis).
                logger.exception(
                    "Пропускаю статтю %s: мережева помилка виклику DeepSeek", article["url"]
                )
                continue

            llm_call_id = log_llm_call(
                conn,
                provider="deepseek",
                purpose="news_relevance_filter",
                prompt=prompt,
                response=raw_content,
                source_ref=article["url"],
            )
            save_analysis(conn, article["id"], result, llm_call_id)
            analyzed += 1
            logger.info(
                "%s → relevant=%s asset_id=%s direction=%s",
                article["url"], result.is_relevant, result.asset_id, result.direction,
            )
    finally:
        conn.close()

    logger.info("Готово: %d статей проаналізовано", analyzed)


if __name__ == "__main__":
    main()
