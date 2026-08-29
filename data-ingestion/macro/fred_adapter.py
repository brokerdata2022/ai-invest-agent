"""
Адаптер FRED (Federal Reserve Economic Data) — офіційне першоджерело
для макропоказників США. https://fred.stlouisfed.org/docs/api/fred/

Перший наскрізний адаптер проєкту (Фаза 0). Вимагає безкоштовний
FRED_API_KEY (реєстрація на https://fred.stlouisfed.org/docs/api/api_key.html).
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests

from common.adapter import BaseAdapter, NormalizedRecord

logger = logging.getLogger(__name__)

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"

# Внутрішній metric_id → FRED series_id. Тримаємо явним словником
# (не даємо кому завгодно передати довільний series_id), щоб metric_id
# лишався стабільним внутрішнім ідентифікатором незалежно від того,
# як показник називається в FRED.
METRICS: dict[str, str] = {
    "cpi": "CPIAUCSL",                 # CPI, усі товари, US city average, SA
    "fed_funds_rate": "DFF",           # Effective Federal Funds Rate, щоденна
    "unemployment_rate": "UNRATE",     # Рівень безробіття, US, SA
    "core_cpi": "CPILFESL",            # CPI без їжі й енергії, US city average, SA
    "pce_price_index": "PCEPI",        # PCE Price Index — орієнтир інфляції ФРС
    "nonfarm_payrolls": "PAYEMS",      # Non-Farm Payrolls — найбільш ринково-чутливий звіт США
    "treasury_10y": "DGS10",           # 10-Year Treasury Constant Maturity Rate, щоденна
    "treasury_2y": "DGS2",             # 2-Year Treasury Constant Maturity Rate, щоденна
    "initial_jobless_claims": "ICSA",  # Initial Jobless Claims, щотижнева, SA
    "real_gdp": "GDPC1",               # Real GDP, квартальна, SAAR
    "retail_sales": "RSAFS",           # Advance Retail Sales, місячна, SA
}

# FRED позначає відсутнє значення символом "." — не 0 і не null.
_MISSING_VALUE = "."


class FredAdapter(BaseAdapter):
    source = "fred"

    def __init__(self, api_key: str, metric_id: str, session: Optional[requests.Session] = None):
        if metric_id not in METRICS:
            raise ValueError(
                f"Невідомий metric_id для FRED: {metric_id!r}. "
                f"Доступні: {sorted(METRICS)}"
            )
        self.api_key = api_key
        self.metric_id = metric_id
        self.series_id = METRICS[metric_id]
        self.session = session or requests.Session()

    def fetch(
        self,
        limit: Optional[int] = None,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
    ) -> Any:
        params = {
            "series_id": self.series_id,
            "api_key": self.api_key,
            "file_type": "json",
        }
        if limit:
            params["limit"] = limit
            params["sort_order"] = "desc"
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end

        response = self.session.get(FRED_OBSERVATIONS_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw_response: Any) -> list[NormalizedRecord]:
        fetched_at = datetime.now(timezone.utc)
        records: list[NormalizedRecord] = []

        for obs in raw_response.get("observations", []):
            raw_value = obs.get("value")
            if raw_value in (None, "", _MISSING_VALUE):
                logger.debug(
                    "Пропускаємо відсутнє значення %s за %s", self.series_id, obs.get("date")
                )
                continue

            try:
                value = Decimal(raw_value)
            except InvalidOperation:
                logger.warning(
                    "Не вдалось розпарсити значення FRED %s за %s: %r",
                    self.series_id, obs.get("date"), raw_value,
                )
                continue

            try:
                observed_at = date.fromisoformat(obs["date"])
            except (KeyError, ValueError):
                logger.warning("Пропущено запис без коректної дати: %r", obs)
                continue

            records.append(
                NormalizedRecord(
                    source=self.source,
                    metric_id=self.metric_id,
                    value=value,
                    observed_at=observed_at,
                    fetched_at=fetched_at,
                    revision=None,  # визначається шаром збереження, див. common/db.py
                    raw_payload=obs,
                )
            )

        return records
