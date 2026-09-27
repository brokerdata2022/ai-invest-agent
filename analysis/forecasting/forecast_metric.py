#!/usr/bin/env python3
"""
Рахує й зберігає прогноз наступного значення одного показника
(trend.py:linear_trend_forecast) — наскрізний шлях "модель →
збереження" (PLAN.md, Фаза 2: "базовий механізм прогнозування").

Не путати з analysis/expectations/: там факт порівнюється з РИНКОВИМ
очікуванням (ForexFactory), тут — наш ВЛАСНИЙ прогноз з тренду власної
історії показника, окреме джерело сигналу.

Використання:
    python forecast_metric.py --metric cpi
"""

import argparse
import logging
import os
import sys
from typing import Optional

from dotenv import load_dotenv

_ANALYSIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ANALYSIS_DIR, "..", "data-ingestion"))
sys.path.insert(0, _ANALYSIS_DIR)

from common.db import get_connection, fetch_recent  # noqa: E402

from forecasting._metric_source import resolve_source  # noqa: E402
from forecasting.trend import linear_trend_forecast  # noqa: E402
from forecasting._db import save_forecast  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

METHOD = "linear_trend"

# Показники з підтвердженим backtest (docs/decisions.md, 2026-09-27) —
# лінійний тренд поки перевірений живо лише на cpi. Розширення на решту
# 14 показників календаря — окрема задача (PLAN.md, Фаза 2:
# "Прогнозування — довести до робочого стану"), не мовчазний побічний
# ефект автотригера (forecasting/update_forecasts.py).
FORECASTABLE_METRICS = {"cpi"}


def run_forecast(conn, metric_id: str, periods_ahead: int = 1, limit: int = 24) -> Optional[int]:
    """Рахує й зберігає прогноз для одного показника. Спільна логіка
    між CLI (main(), ручний прогін) і update_forecasts.py (автотригер
    одразу після того, як monitoring задетектував новий реліз)."""
    source = resolve_source(metric_id)

    observations = fetch_recent(conn, source, metric_id, limit=limit)
    if len(observations) < 2:
        logger.warning("%s: замало історії (%d) для прогнозу", metric_id, len(observations))
        return None

    chronological = list(reversed(observations))
    values = [float(o["value"]) for o in chronological]
    based_on_observed_at = chronological[-1]["observed_at"]

    forecast_value = linear_trend_forecast(values, periods_ahead=periods_ahead)
    if forecast_value is None:
        logger.warning("%s: не вдалось порахувати прогноз", metric_id)
        return None

    forecast_id = save_forecast(
        conn,
        source=source,
        metric_id=metric_id,
        method=METHOD,
        based_on_observed_at=based_on_observed_at,
        periods_ahead=periods_ahead,
        forecast_value=forecast_value,
    )
    logger.info(
        "%s: прогноз на %d період(и) вперед від %s = %.4g (id=%d)",
        metric_id, periods_ahead, based_on_observed_at, forecast_value, forecast_id,
    )
    return forecast_id


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--periods-ahead", type=int, default=1)
    parser.add_argument("--limit", type=int, default=24, help="скільки останніх спостережень брати для тренду")
    args = parser.parse_args()

    conn = get_connection()
    try:
        try:
            forecast_id = run_forecast(
                conn, args.metric, periods_ahead=args.periods_ahead, limit=args.limit
            )
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

        if forecast_id is None:
            sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
