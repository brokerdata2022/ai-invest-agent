"""
Адаптер Twelve Data — щоденні ціна/обсяг для довільного тикера.
https://twelvedata.com/docs

Третій кандидат на джерело котирувань у цьому проєкті (docs/decisions.md,
2026-09-14/20): Alpaca Markets відкинуто (недоступна з мережі
користувача), Stooq відкинуто (з ~вересня 2026 ставить JS-based
бот-перевірку на CSV-ендпоінт — недоступна для requests, обхід
означав би headless-браузер, крихка залежність для регулярного
збору). Twelve Data — перше з трьох, що підтверджено ЖИВИМ запитом
користувача (200, реальні дані AAPL) до того, як писався код, а не
після.

Безкоштовна реєстрація email+пароль (без капчі), ключ одразу в
кабінеті. Ліміти free tier: ~8 запитів/хв (після підтвердження
email), 800/добу — суттєво для прогону скринера на весь S&P 500
(~500 тикерів): по 1 запиту (1 credit) на тикер, тобто прогін
займає ~500/8 ≈ 63 хв, вкладається в добову квоту з запасом.

Архітектурна відмінність від macro/*-адаптерів (FRED/ECB/BOJ/e-Stat):
там METRICS — фіксований словник конкретних показників країни. Тут
тикер — необмежена множина (universe скринінгу — S&P 500, див.
docs/screening-criteria.md), тож METRICS-у стилі macro/ не буде:
тикер — параметр конструктора, а не хардкод. FIELDS нижче — це
фіксований (малий) набір **полів одного бару**, не показників.
metric_id збирається динамічно як "{ticker}_{field}", напр.
"aapl_close", "aapl_volume" — той самий підхід, що вже задокументовано
для companies/ (SEC EDGAR) у docs/decisions.md.
"""

import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests

from common.adapter import BaseAdapter, NormalizedRecord

logger = logging.getLogger(__name__)

TWELVEDATA_URL = "https://api.twelvedata.com/time_series"

# metric_id-суфікс → ключ у JSON "values"-записі Twelve Data. Для
# скринінгу (docs/screening-criteria.md) потрібні тільки ці два поля —
# open/high/low навмисно не тягнемо, поки для них немає використання.
FIELDS: dict[str, str] = {
    "close": "close",
    "volume": "volume",
}


class TwelveDataAdapter(BaseAdapter):
    source = "twelvedata"

    def __init__(self, api_key: str, ticker: str, session: Optional[requests.Session] = None):
        if not api_key:
            raise ValueError(
                "TWELVEDATA_API_KEY не задано. Безкоштовна реєстрація: "
                "https://twelvedata.com/ (див. .env.example)."
            )
        if not ticker or not ticker.strip():
            raise ValueError(f"Некоректний тикер для Twelve Data: {ticker!r}")
        self.api_key = api_key
        self.ticker = ticker.strip().upper()
        self.session = session or requests.Session()

    def fetch(
        self,
        limit: Optional[int] = None,
        observation_start: Optional[str] = None,
        observation_end: Optional[str] = None,
    ) -> Any:
        params: dict[str, Any] = {
            "symbol": self.ticker,
            "interval": "1day",
            "apikey": self.api_key,
        }
        if limit:
            params["outputsize"] = limit
        if observation_start:
            params["start_date"] = observation_start
        if observation_end:
            params["end_date"] = observation_end

        response = self.session.get(TWELVEDATA_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw_response: Any) -> list[NormalizedRecord]:
        fetched_at = datetime.now(timezone.utc)
        records: list[NormalizedRecord] = []

        # Twelve Data повертає помилки зі status=200 (не HTTP-кодом
        # помилки) — {"code": 400/401/429/..., "status": "error",
        # "message": "..."} — тому raise_for_status() у fetch() цього
        # не ловить, перевіряємо явно тут.
        if isinstance(raw_response, dict) and raw_response.get("status") == "error":
            raise ValueError(
                f"Twelve Data повернув помилку для {self.ticker}: "
                f"код {raw_response.get('code')}, {raw_response.get('message')!r}"
            )

        values = raw_response.get("values") if isinstance(raw_response, dict) else None
        if not values:
            raise ValueError(
                f"Неочікувана відповідь Twelve Data для {self.ticker} — "
                f"немає values: {raw_response!r}"[:300]
            )

        for row in values:
            raw_date = row.get("datetime")
            if not raw_date:
                continue
            try:
                observed_at = date.fromisoformat(raw_date)
            except ValueError:
                logger.warning(
                    "Twelve Data %s: не вдалось розпарсити дату %r, рядок пропущено",
                    self.ticker, raw_date,
                )
                continue

            for suffix, key in FIELDS.items():
                raw_value = row.get(key)
                if raw_value in (None, ""):
                    logger.debug(
                        "Twelve Data %s: відсутнє значення %s за %s",
                        self.ticker, key, raw_date,
                    )
                    continue
                try:
                    value = Decimal(raw_value)
                except InvalidOperation:
                    logger.warning(
                        "Twelve Data %s: не вдалось розпарсити %s за %s: %r",
                        self.ticker, key, raw_date, raw_value,
                    )
                    continue

                records.append(
                    NormalizedRecord(
                        source=self.source,
                        metric_id=f"{self.ticker.lower()}_{suffix}",
                        value=value,
                        observed_at=observed_at,
                        fetched_at=fetched_at,
                        revision=None,  # визначається шаром збереження, див. common/db.py
                        raw_payload=dict(row),
                    )
                )

        return records
