"""
metric_id -> source (назва джерела в raw_observations) — тонка обгортка
над monitoring/metric_sources.ADAPTER_BY_METRIC (адаптер несе .source),
спільна для backtest.py/forecast_metric.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "monitoring"))

from metric_sources import ADAPTER_BY_METRIC  # noqa: E402


def resolve_source(metric_id: str) -> str:
    entry = ADAPTER_BY_METRIC.get(metric_id)
    if entry is None:
        raise ValueError(
            f"Невідомий metric_id={metric_id!r} — немає в monitoring/metric_sources.py"
        )
    adapter_class, _ = entry
    return adapter_class.source
