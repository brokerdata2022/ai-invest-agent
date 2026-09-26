"""
Адаптер CoinGecko — щоденні показники для watchlist-активів, яких не
дає одна біржа: market cap крипто (BTC/ETH/SOL) і, з 2026-09-26, ціна
срібла (XAG/USD) через токенізований проксі (нижче).
https://www.coingecko.com/en/api/documentation

Крипто (market cap): агрегатор (не одна біржа) — саме тому дає те,
чого не може дати crypto/binance_adapter.py (одна біржа знає тільки
свій власний обсяг торгів, не сумарну ринкову капіталізацію активу).
Market cap — крипто-аналог "фундаменталу" (docs/news-purpose.md, Ціль
2: для не-акційних активів фундаментальної звітності немає, тому
дивимось на попит/пропозицію/розмір ринку).

Срібло (xagusd): Twelve Data (quotes/twelvedata_adapter.py) вимагає
платний тариф для XAG/USD (docs/decisions.md, 2026-09-26, 404 "Grow or
Venture plan"). Рішення — `kinesis-silver` (символ KAG) на CoinGecko:
токен, забезпечений фізичним сріблом 1:1 (1 KAG = 1 тройська унція,
kinesis.money), тобто ціна токена — проксі, а не пряме джерело
LBMA/COMEX спот-ціни. Перевірено живими запитами 2026-09-26 (не
вгадано): gold:silver ratio на той самий момент — `pax-gold` (PAXG,
той самий підхід, uже підтверджений токен-проксі для золота) $4278.53
проти `kinesis-silver` $63.58 → ratio ≈ 67.3, у межах звичного
історичного діапазону (50-90) — правдоподібно, не помилка на порядок.
Свідома неточність (проксі, не пряме джерело) — задокументовано,
не приховано.

METRICS — фіксований словник (watchlist закритий, docs/watchlist.md):
metric_id → (coin_id, поле у відповіді market_chart, суфікс metric_id
на виході). Той самий підхід, що macro/boj_adapter.py (tuple-значення
в METRICS), бо різні активи тут мапляться на РІЗНІ поля відповіді
(market_caps для крипти, prices для срібла-проксі), а не тільки на
різні coin_id.

Ключ не потрібен — публічний ендпоінт без реєстрації.

Один нюанс формату: `/market_chart` повертає точки з кроком, що не
завжди рівно один на календарну дату (останній запис — "поточний",
частина ще не завершеної доби) — normalize() навмисно лишає ОДНЕ
значення на observed_at (останнє за часом у межах дати), інакше
common/db.py трактував би другу точку того самого дня як "нову
ревізію", хоча це просто субдобова гранулярність джерела, не
фактична ревізія показника.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests

from common.adapter import BaseAdapter, NormalizedRecord

logger = logging.getLogger(__name__)

COINGECKO_MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"

DEFAULT_DAYS = 30

# internal metric_id (== news/queries.py:WATCHLIST_ASSET_IDS) →
# (CoinGecko coin id, поле відповіді market_chart, суфікс вихідного metric_id)
METRICS: dict[str, tuple[str, str, str]] = {
    "btc": ("bitcoin", "market_caps", "market_cap"),
    "eth": ("ethereum", "market_caps", "market_cap"),
    "sol": ("solana", "market_caps", "market_cap"),
    "xagusd": ("kinesis-silver", "prices", "close"),
}


class CoinGeckoAdapter(BaseAdapter):
    source = "coingecko"

    def __init__(self, metric_id: str, session: Optional[requests.Session] = None):
        if metric_id not in METRICS:
            raise ValueError(
                f"Невідомий metric_id для CoinGecko: {metric_id!r}. "
                f"Доступні: {sorted(METRICS)}"
            )
        self.metric_id = metric_id
        self.coin_id, self.field_key, self.suffix = METRICS[metric_id]
        self.session = session or requests.Session()

    def fetch(self, limit: Optional[int] = None) -> Any:
        params: dict[str, Any] = {
            "vs_currency": "usd",
            "days": limit or DEFAULT_DAYS,
            "interval": "daily",
        }
        url = COINGECKO_MARKET_CHART_URL.format(coin_id=self.coin_id)
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def normalize(self, raw_response: Any) -> list[NormalizedRecord]:
        fetched_at = datetime.now(timezone.utc)

        points = raw_response.get(self.field_key) if isinstance(raw_response, dict) else None
        if not points:
            logger.warning(
                "Неочікувана відповідь CoinGecko для %s (%s) — немає %s: %r",
                self.metric_id, self.coin_id, self.field_key, str(raw_response)[:300],
            )
            return []

        # Дедуп по даті: якщо джерело дало кілька точок на ту саму
        # календарну дату (типово — остання, "поточна" точка), лишаємо
        # найпізнішу за часом (докладніше — docstring модуля).
        latest_by_date: dict[Any, tuple[int, Decimal]] = {}
        for point in points:
            try:
                timestamp_ms, raw_value = point[0], point[1]
            except (IndexError, TypeError):
                logger.warning(
                    "CoinGecko %s: неочікувана структура точки %s, пропущено: %r",
                    self.coin_id, self.field_key, point,
                )
                continue

            try:
                value = Decimal(str(raw_value))
            except InvalidOperation:
                logger.warning(
                    "CoinGecko %s: не вдалось розпарсити %s: %r",
                    self.coin_id, self.field_key, raw_value,
                )
                continue

            observed_at = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).date()
            existing = latest_by_date.get(observed_at)
            if existing is None or timestamp_ms > existing[0]:
                latest_by_date[observed_at] = (timestamp_ms, value)

        records = [
            NormalizedRecord(
                source=self.source,
                metric_id=f"{self.metric_id}_{self.suffix}",
                value=value,
                observed_at=observed_at,
                fetched_at=fetched_at,
                revision=None,  # визначається шаром збереження, common/db.py
                raw_payload={"timestamp_ms": timestamp_ms, self.field_key: str(value)},
            )
            for observed_at, (timestamp_ms, value) in latest_by_date.items()
        ]
        records.sort(key=lambda r: r.observed_at)
        return records
