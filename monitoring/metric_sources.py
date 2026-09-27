"""
Реєстр "який адаптер даних відповідає metric_id" — спільний для
`refresh_calendar.py` (потрібен лише `.source`, для release_log) і
`check_releases.py` (потрібен клас адаптера + чи потрібен api_key, для
реального забору даних після настання часу релізу).

FRED-метрики беруться з `release_calendar.RELEASE_IDS` (одне джерело
істини, не дублюємо перелік удруге). Eurozone/Japan — без FRED-якоря
(докладніше `economic_calendar.py`), тому `CALENDAR_ONLY_METRICS`:
для них economic_calendar.py — ЄДИНЕ джерело дати релізу, не тільки
збагачення.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-ingestion"))

from macro.boj_adapter import BojAdapter  # noqa: E402
from macro.ecb_adapter import EcbAdapter  # noqa: E402
from macro.estat_adapter import EstatAdapter  # noqa: E402
from macro.fred_adapter import FredAdapter  # noqa: E402

from release_calendar import RELEASE_IDS  # noqa: E402

# metric_id → (клас адаптера, назва env-змінної з ключем, або None
# якщо ключ не потрібен).
ADAPTER_BY_METRIC: dict[str, tuple[type, str | None]] = {
    metric_id: (FredAdapter, "FRED_API_KEY") for metric_id in RELEASE_IDS
}
ADAPTER_BY_METRIC.update({
    "eurozone_hicp": (EcbAdapter, None),
    "eurozone_deposit_rate": (EcbAdapter, None),
    "eurozone_unemployment_rate": (EcbAdapter, None),
    "japan_policy_rate": (BojAdapter, None),
    "japan_cpi": (EstatAdapter, "ESTAT_APP_ID"),
})

# Показники без FRED release-календаря — economic_calendar.py дає
# дату напряму (find_upcoming_event()), не тільки збагачує вже відому
# FRED-дату (find_event()).
CALENDAR_ONLY_METRICS: list[str] = [
    "eurozone_hicp",
    "eurozone_deposit_rate",
    "eurozone_unemployment_rate",
    "japan_policy_rate",
    "japan_cpi",
]
