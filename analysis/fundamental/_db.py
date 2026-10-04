"""
Тонкий SQL-шар фундаментального аналізу — той самий принцип, що
`trading_list/_db.py` і `expectations/_db.py`: SQL без інтерпретації,
промпт і розбір відповіді лишаються в `fundamental_llm.py`.
"""

import json
from typing import Optional


def fetch_top_stocks(conn, limit: int) -> list[dict]:
    """Топ акцій останнього прогону скринінгу за composite-скором.

    Обмеження `limit` — головний контроль вартості: скринінг пропускає
    ~215 тикерів, а дані SEC EDGAR змінюються раз на КВАРТАЛ, тож
    щоденні 215 LLM-викликів були б витратою заради незмінних чисел
    (`config.TOP_N_STOCKS`)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ticker, company_name, score, pe, revenue_growth, eps_growth
            FROM screening_results
            WHERE run_at = (SELECT MAX(run_at) FROM screening_results)
            ORDER BY score DESC
            LIMIT %s
            """,
            (limit,),
        )
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_fundamental_series(conn, ticker: str, suffix: str, quarters: int) -> list[dict]:
    """Квартальний ряд одного показника в ХРОНОЛОГІЧНОМУ порядку.

    Читає `v_observations_latest_revision`, не `raw_observations`: SEC
    EDGAR перевидає ті самі періоди (ревізії звітності), і без цього в
    ряд потрапляли б і старі, уже виправлені значення."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT observed_at, value
            FROM v_observations_latest_revision
            WHERE source = 'sec_edgar' AND metric_id = %s
            ORDER BY observed_at DESC
            LIMIT %s
            """,
            (f"{ticker.lower()}_{suffix}", quarters),
        )
        rows = [{"observed_at": str(r[0]), "value": r[1]} for r in cur.fetchall()]
    return list(reversed(rows))


def save_fundamental_analysis(
    conn,
    ticker: str,
    company_name: Optional[str],
    result,
    inputs: dict,
    llm_call_id: Optional[int],
) -> int:
    """UPSERT на (ticker, день). `notified_at = NULL` при оновленні —
    той самий фікс і причина, що `news_analysis/_db.py:save_synthesis`
    (2026-09-29): інакше оновлений того ж дня висновок назавжди
    лишався б невидимим для notify-скрипта."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO fundamental_analysis
                (ticker, company_name, direction, confidence, summary,
                 reasoning, strengths, risks, inputs, llm_call_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, ((created_at AT TIME ZONE 'UTC')::date)) DO UPDATE SET
                company_name = EXCLUDED.company_name,
                direction = EXCLUDED.direction,
                confidence = EXCLUDED.confidence,
                summary = EXCLUDED.summary,
                reasoning = EXCLUDED.reasoning,
                strengths = EXCLUDED.strengths,
                risks = EXCLUDED.risks,
                inputs = EXCLUDED.inputs,
                llm_call_id = EXCLUDED.llm_call_id,
                created_at = now(),
                notified_at = NULL
            RETURNING id
            """,
            (
                ticker, company_name, result.direction, result.confidence,
                result.summary, result.reasoning,
                json.dumps(result.strengths, ensure_ascii=False),
                json.dumps(result.risks, ensure_ascii=False),
                json.dumps(inputs, ensure_ascii=False, default=str),
                llm_call_id,
            ),
        )
        analysis_id = cur.fetchone()[0]
    conn.commit()
    return analysis_id
