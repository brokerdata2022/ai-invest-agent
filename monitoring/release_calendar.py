"""
Календар релізів US-показників — офіційний графік публікацій (FRED
release API, дзеркалить BLS/BEA/Fed) + власний fallback-список рівня
впливу.

**Live-факт, що вплинув на дизайн:** `nonfarm_payrolls` (PAYEMS) і
`unemployment_rate` (UNRATE) належать ОДНОМУ release_id (50,
"Employment Situation") — той самий звіт BLS, тому той самий графік.

**Навмисно НЕ всі FRED-метрики тут.** Тільки ті, що виходять як
дискретний періодичний звіт (CPI, NFP, GDP, ...). Неперервні щоденні
ринкові ряди (fed_funds_rate, treasury_10y/2y, usdjpy_fx_rate,
wti_crude/brent_crude/eurusd/coffee) — виключено, немає окремої "події
релізу". Єврозона/Японія — окремий шлях, `economic_calendar.py`
(FRED release API покриває тільки US).

Impact-рівні — стандартна ринкова класифікація, стартова точка,
підлягає калібруванню. **Fallback-роль:** `economic_calendar.py` дає
точніший impact і точний час, коли знаходить збіг за назвою —
`IMPACT_LEVELS`/`DEFAULT_RELEASE_TIME_ET` тут — лише коли збігу нема.
Деталі й живі перевірки — `docs/decisions.md`.
"""

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

FRED_RELEASE_DATES_URL = "https://api.stlouisfed.org/fred/release/dates"

# internal metric_id → FRED release_id (перевірено живим /fred/series/release)
RELEASE_IDS: dict[str, int] = {
    "cpi": 10,
    "core_cpi": 10,
    "pce_price_index": 54,
    "nonfarm_payrolls": 50,
    "unemployment_rate": 50,
    "initial_jobless_claims": 180,
    "real_gdp": 53,
    "retail_sales": 9,
    "housing_starts": 27,
    "mortgage_rate_30y": 190,
}

# Стартова класифікація впливу (high/medium/low) — не з офіційного API
# (немає такого), ручна, підлягає калібруванню.
IMPACT_LEVELS: dict[str, str] = {
    "cpi": "high",
    "core_cpi": "high",
    "pce_price_index": "high",
    "nonfarm_payrolls": "high",
    "unemployment_rate": "high",
    "real_gdp": "high",
    "initial_jobless_claims": "medium",
    "retail_sales": "medium",
    "housing_starts": "medium",
    "mortgage_rate_30y": "low",
}


def fetch_release_dates(
    metric_id: str,
    api_key: str,
    limit: int = 40,
    session: Optional[requests.Session] = None,
) -> Any:
    """Сирий виклик FRED release/dates для release_id, що відповідає
    metric_id. `include_release_dates_with_no_data=true` — щоб бачити
    вже заплановані майбутні дати (без цього прапорця FRED інколи
    ховає дати, для яких дані ще не опубліковані).

    limit=40 — запас, щоб охопити і минулі, і майбутні дати в одному
    запиті (перевірено живо 2026-09-26: щотижневі релізи мають ~11+
    вже запланованих майбутніх дат наперед, тому малий limit ризикує
    не захопити потрібну; 40 — з запасом, не точний мінімум)."""
    if metric_id not in RELEASE_IDS:
        raise ValueError(
            f"Немає календаря релізів для metric_id {metric_id!r}. "
            f"Доступні: {sorted(RELEASE_IDS)}"
        )
    params = {
        "release_id": RELEASE_IDS[metric_id],
        "api_key": api_key,
        "file_type": "json",
        "include_release_dates_with_no_data": "true",
        "sort_order": "desc",
        "limit": limit,
    }
    sess = session or requests.Session()
    response = sess.get(FRED_RELEASE_DATES_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_release_dates(raw_response: Any) -> list[date]:
    """Сира відповідь → відсортований (зростання) список дат релізу.
    Чиста функція — без мережі, тестується на фікстурах."""
    entries = raw_response.get("release_dates") if isinstance(raw_response, dict) else None
    if not entries:
        logger.warning(
            "Неочікувана відповідь FRED release/dates — немає release_dates: %r",
            str(raw_response)[:300],
        )
        return []

    dates: list[date] = []
    for entry in entries:
        raw_date = entry.get("date")
        if not raw_date:
            continue
        try:
            dates.append(date.fromisoformat(raw_date))
        except ValueError:
            logger.warning("Не вдалось розпарсити дату релізу: %r", raw_date)
            continue

    dates.sort()
    return dates


def next_scheduled_release(
    dates: list[date],
    today: Optional[date] = None,
    horizon_days: int = 7,
) -> Optional[date]:
    """Найближча ще НЕ минула дата релізу (>= today), АЛЕ лише в межах
    горизонту (за замовчуванням 7 днів — тижнева seed-періодичність,
    синхронізована з вікном economic_calendar.py, яке покриває лише
    поточний тиждень — без горизонту seed ішов би на fallback для
    будь-якого місячного релізу, що ще за 3-4 тижні наперед).

    Повертає None, якщо в межах горизонту немає жодної дати — НОРМАЛЬНО
    (не помилка): `refresh_calendar.py` спробує знову наступного
    тижня, коли дата наблизиться."""
    today = today or datetime.now(timezone.utc).date()
    horizon = today + timedelta(days=horizon_days)
    upcoming = [d for d in dates if today <= d <= horizon]
    return min(upcoming) if upcoming else None


# Типовий час публікації BLS/BEA — 8:30 ET для всіх наших 10
# показників (загальновідомо: CPI/NFP/Unemployment Rate/Jobless
# Claims/GDP/Retail Sales/Housing Starts/PCE — усі о 8:30 ET;
# mortgage_rate_30y, Freddie Mac survey, теж публікується вранці
# четверга). US/Eastern через zoneinfo (не хардкод -04:00/-05:00) —
# коректно враховує перехід EST/EDT.
DEFAULT_RELEASE_TIME_ET = time(8, 30)
_EASTERN = ZoneInfo("America/New_York")


def default_scheduled_datetime(due_date: date) -> datetime:
    """Fallback, коли economic_calendar.find_event() не знайшов збігу
    за назвою — типовий час замість повної відсутності часу (дата з
    півночі, як було до 2026-09-26)."""
    return datetime.combine(due_date, DEFAULT_RELEASE_TIME_ET, tzinfo=_EASTERN)
