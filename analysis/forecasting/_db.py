"""
Тонкий SQL-шар для metric_forecasts — той самий принцип, що
expectations/_db.py: SQL без інтерпретації значень, уся логіка
(модель/екстраполяція) лишається в trend.py.
"""


def save_forecast(
    conn,
    source: str,
    metric_id: str,
    method: str,
    based_on_observed_at,
    periods_ahead: int,
    forecast_value: float,
) -> int:
    """UPSERT — один рядок на (source, metric_id, method,
    based_on_observed_at): повторний прогін на тих самих вхідних даних
    (той самий останній спостережений період) оновлює рядок, не
    дублює (db/schema.sql:idx_metric_forecasts_unique)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO metric_forecasts
                (source, metric_id, method, based_on_observed_at, periods_ahead, forecast_value)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, metric_id, method, based_on_observed_at) DO UPDATE SET
                periods_ahead = EXCLUDED.periods_ahead,
                forecast_value = EXCLUDED.forecast_value,
                created_at = now()
            RETURNING id
            """,
            (source, metric_id, method, based_on_observed_at, periods_ahead, forecast_value),
        )
        forecast_id = cur.fetchone()[0]
    conn.commit()
    return forecast_id
