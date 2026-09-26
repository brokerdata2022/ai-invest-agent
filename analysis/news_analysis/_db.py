"""
Тонкий SQL-шар для news-аналізу — той самий принцип, що й
analysis/screening/_batch_db.py: SQL без жодної інтерпретації значень,
логіка (виклик DeepSeek, парсинг) лишається в relevance_filter.py.
"""

from typing import Optional

from news_analysis.relevance_filter import NewsAnalysisResult


def fetch_unanalyzed(conn, stream: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Статті з raw_news, для яких ще немає рядка в news_analysis
    (LEFT JOIN ... IS NULL — не викликаємо DeepSeek на ту саму статтю
    двічі)."""
    query = """
        SELECT n.id, n.source, n.stream, n.title, n.url, n.published_at,
               n.raw_payload
        FROM raw_news n
        LEFT JOIN news_analysis a ON a.raw_news_id = n.id
        WHERE a.id IS NULL
    """
    params: list = []
    if stream is not None:
        query += " AND n.stream = %s"
        params.append(stream)
    query += " ORDER BY n.published_at DESC LIMIT %s"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_relevant_for_aggregation(
    conn, stream: Optional[str] = None, max_age_days: int = 7
) -> list[dict]:
    """Релевантні статті за останні max_age_days — вхід для
    aggregate.py (кластеризація дублікатів + зведення по активу).
    Фільтр за n.published_at (коли стаття ВИЙШЛА), не a.created_at
    (коли ми її проаналізували) — той самий принцип свіжості, що й
    reporting/news_notify.py:fetch_recent_relevant() (docs/decisions.md,
    2026-09-26)."""
    query = """
        SELECT n.id AS raw_news_id, n.stream, n.title, n.url, n.published_at,
               a.asset_id, a.direction, a.confidence, a.summary
        FROM news_analysis a
        JOIN raw_news n ON n.id = a.raw_news_id
        WHERE a.is_relevant = true
          AND n.published_at >= now() - (%s || ' days')::interval
    """
    params: list = [max_age_days]
    if stream is not None:
        query += " AND n.stream = %s"
        params.append(stream)
    query += " ORDER BY n.published_at DESC"

    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def log_llm_call(
    conn, provider: str, purpose: str, prompt: str, response: str, source_ref: Optional[str]
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO llm_call_log (provider, purpose, prompt, response, source_ref)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (provider, purpose, prompt, response, source_ref),
        )
        llm_call_id = cur.fetchone()[0]
    conn.commit()
    return llm_call_id


def save_analysis(
    conn, raw_news_id: int, result: NewsAnalysisResult, llm_call_id: int
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO news_analysis
                (raw_news_id, asset_id, is_relevant, summary, direction,
                 confidence, reasoning, llm_call_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                raw_news_id,
                result.asset_id,
                result.is_relevant,
                result.summary,
                result.direction,
                result.confidence,
                result.reasoning,
                llm_call_id,
            ),
        )
    conn.commit()
