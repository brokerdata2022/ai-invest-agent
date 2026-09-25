"""
Шар роботи з БД для новин — паралельний до common/db.py (raw_news
має інакшу структуру дедуплікації: (source, external_id), без
revision, докладніше docs/decisions.md, 2026-09-25).
"""

import json
import logging

from common.news_adapter import NewsRecord

logger = logging.getLogger(__name__)


def insert_news(conn, record: NewsRecord) -> bool:
    """Append-only запис однієї новини. Ідемпотентно: повторний збір
    тієї самої статті (той самий source+external_id) нічого не змінює.

    Повертає True, якщо запис фактично вставлено (нова стаття).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw_news
                (source, external_id, stream, title, url, published_at, fetched_at, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, external_id) DO NOTHING
            """,
            (
                record.source,
                record.external_id,
                record.stream,
                record.title,
                record.url,
                record.published_at,
                record.fetched_at,
                json.dumps(record.raw_payload, default=str) if record.raw_payload else None,
            ),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


def insert_news_batch(conn, records: list[NewsRecord]) -> int:
    """Записує список новин, повертає кількість фактично нових статей."""
    return sum(1 for record in records if insert_news(conn, record))
