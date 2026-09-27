"""
Тонкий SQL-шар для expectation_comparisons — той самий принцип, що
analysis/news_analysis/_db.py: SQL без інтерпретації значень, уся
логіка обчислення (методи/парсинг) лишається в comparison_methods.py/
parse_expected.py.
"""


def save_comparison(conn, result) -> int:
    """result — compare_releases.ComparisonResult."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO expectation_comparisons
                (release_log_id, source, metric_id, observed_at, actual_value,
                 expected_value_raw, expected_value_parsed, surprise, surprise_pct,
                 comparison_method)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                result.release_log_id,
                result.source,
                result.metric_id,
                result.observed_at,
                result.actual_value,
                result.expected_value_raw,
                result.expected_value_parsed,
                result.surprise,
                result.surprise_pct,
                result.comparison_method,
            ),
        )
        comparison_id = cur.fetchone()[0]
    conn.commit()
    return comparison_id
