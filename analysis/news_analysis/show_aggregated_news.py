#!/usr/bin/env python3
"""
Показує агреговані новини (кластери дублікатів + зведення по активу)
за останні --max-age-days. Тимчасовий інструмент перегляду результату
aggregate.py, доки не побудований крок 4 (щоденний дайджест) —
docs/news-purpose.md.

Використання:
    python show_aggregated_news.py
    python show_aggregated_news.py --stream watchlist --max-age-days 3
"""

import argparse
import os
import sys

from dotenv import load_dotenv

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ANALYSIS_DIR)
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))

from common.db import get_connection  # noqa: E402
from news_analysis._db import fetch_relevant_for_aggregation  # noqa: E402
from news_analysis.aggregate import aggregate_by_asset, cluster_articles  # noqa: E402


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stream", choices=["watchlist", "general", "geopolitical"], default=None)
    parser.add_argument("--max-age-days", type=int, default=7)
    args = parser.parse_args()

    conn = get_connection()
    try:
        articles = fetch_relevant_for_aggregation(
            conn, stream=args.stream, max_age_days=args.max_age_days
        )
    finally:
        conn.close()

    print(f"Релевантних статей за {args.max_age_days} днів: {len(articles)}")
    clusters = cluster_articles(articles)
    print(f"Після кластеризації дублікатів: {len(clusters)} унікальних історій\n")

    print("=== Кластери (найновіші перші) ===")
    for c in clusters:
        assets = ", ".join(c.asset_ids) if c.asset_ids else "—"
        print(
            f"[{c.source_count} джерел] {c.latest_published_at.strftime('%Y-%m-%d %H:%M')} "
            f"| актив: {assets} | напрямок: {c.dominant_direction}"
        )
        print(f"  {c.representative_title}")
        if c.summaries:
            print(f"  → {c.summaries[0]}")
        print()

    signals = aggregate_by_asset(clusters)
    if signals:
        print("=== Зведення по активу ===")
        for asset_id, s in sorted(signals.items(), key=lambda kv: -kv[1].cluster_count):
            print(
                f"{asset_id:12} кластерів={s.cluster_count:3} "
                f"up={s.direction_counts['up']} down={s.direction_counts['down']} "
                f"neutral={s.direction_counts['neutral']} unclear={s.direction_counts['unclear']} "
                f"net_lean={s.net_lean:+d}"
            )


if __name__ == "__main__":
    main()
