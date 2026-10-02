"""
Зчитування цінового руху watchlist-активів за вікно — звичайний код,
без LLM (analysis/CLAUDE.md: "числові порівняння — звичайний код").
Вхід для synthesize.py (зіставлення новинного сигналу з фактичним
рухом ціни — docs/news-purpose.md, ціль 1).

is_anomalous_move() (2026-10-02, живий фідбек користувача): синтез не
повинен залежати ЛИШЕ від того, чи є новина — рух ціни сам по собі теж
привід проаналізувати актив, навіть БЕЗ жодної новини. "Аномальний" —
не довільний відсоток (крипта рутинно рухається на 5%, золото рідко),
а відносно власної історичної волатильності активу: |pct_change за
вікно| проти очікуваного розмаху за той самий період, вивченого з
останніх спостережень (daily stdev × √window_days, "квадратний корінь
часу" — стандартне масштабування волатильності). Відкинуто: єдиний
фіксований % для всіх активів — підійшов би БТС, але золото/EURUSD
рідко рухаються на кілька % навіть за тиждень, тому дав би або шум на
крипті, або глухоту на решті.
"""

import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from common.db import fetch_recent

# Скільки стандартних відхилень денного руху вважати "аномальним" за
# вікно — не підтверджено backtest'ом (це сповіщувальний порІг, не
# прогнозна модель — критерій "б'є naive" з analysis/CLAUDE.md
# стосується forecasting/, не цього), рішення користувача за живими
# даними. Було 2.0 (≈ верхні ~5% випадків при нормальному розподілі) —
# живо підтверджено 2026-10-02: за цим порогом xagusd (-6.95% при
# порозі 10.15%) і HII (+6.72% зі скринінгу) НЕ вважались аномальними,
# хоча користувач вважає такі рухи вартими аналізу. Знижено до 1.0
# (2026-10-02, рішення користувача) — помітно чутливіше (ловить і менш
# екстремальні рухи), ціна цього — більше LLM-викликів на прогін.
# Переглянути знову, коли накопичиться більше живих спрацювань.
ANOMALY_SIGMA_MULTIPLIER = 1.0

# Мінімум ДЕННИХ спостережень історії, щоб узагалі рахувати stdev —
# менше просто не дає статистичної опори (крипта зібрана лише з
# 2026-09-26, тиждень на момент цієї зміни — для неї поки чесно
# "недостатньо даних", не false positive/negative).
ANOMALY_MIN_HISTORY = 10

# Скільки останніх спостережень тягнути для розрахунку волатильності —
# запас понад ANOMALY_MIN_HISTORY, не точний ліміт.
ANOMALY_HISTORY_LOOKBACK = 90

# asset_id (той самий, що news/queries.py:WATCHLIST_ASSET_IDS) →
# (source, metric_id) у raw_observations. Метал/товар/форекс ціни
# додані 2026-09-26 (docs/decisions.md).
#
# eurusd/usdjpy — Twelve Data (2026-10-02), НЕ FRED (DEXUSEU/DEXJPUS,
# стара серія usdjpy_fx_rate лишається в raw_observations НАЗАВЖДИ,
# rule 6 CLAUDE.md, просто більше не поточне джерело для цих
# asset_id): живо підтверджено на fred.stlouisfed.org — попри
# заявлену частоту "Daily", останнє спостереження ОБОХ серій
# застрягло на 2026-09-25, а "Next Release Date" на сторінці самого
# FRED — 2026-10-05 (10 днів розриву) — це затримка публікації на боці
# Fed H.10 release, не наш збір. Twelve Data вже підтверджено живо для
# форекс-символу зі слешем (xauusd нижче), EUR/USD і USD/JPY —
# мейнстрім-пари, мають бути як мінімум не гірше покриті.
#
# coffee — FRED (PCOFFOTMUSDM, IMF) ЗАЛИШЕНО як є: живо підтверджено на
# fred.stlouisfed.org — серія genuinely МІСЯЧНА ("Monthly", останнє
# спостереження липень 2026, "Next Release Date: Not Available"), липень
# -- не застаріла колекція, а справді найновіша доступна точка. Вікно
# синтезу 7 днів (`synthesize.py --max-age-days`) структурно ніколи не
# покриє місячний ряд — відома, свідома прогалина, не виправляється
# зміною джерела (кращого безкоштовного ЩОДЕННОГО джерела кави не
# шукали — поза обсягом цієї зміни).
#
# btc/eth/sol — crypto/binance_adapter.py (metric_id=f"{id}_close",
# source="binance"), той самий ключ, що WATCHLIST_ASSET_IDS
# (news/queries.py). xagusd — Twelve Data XAG/USD вимагає платний план
# (docs/decisions.md 2026-09-26), тому НЕ twelvedata: ціна йде через
# crypto/coingecko_adapter.py (kinesis-silver, токен-проксі 1:1 до
# фізичного срібла, metric_id="xagusd_close", source="coingecko") —
# той самий адаптер, що й market cap крипти нижче.
#
# btc/eth/sol/xagusd додані 2026-10-02: до цього _resolve_price_source()
# для них помилково гадав twelvedata-конвенцію (fallback нижче), де
# даних для жодного з них ніколи не було, тому fetch_price_change()
# завжди повертав None — синтез (synthesize.py) ЦІЛКОМ пропускав усі
# чотири активи watchlist, хоча ціна насправді вже збиралась.
ASSET_PRICE_SOURCES: dict[str, tuple[str, str]] = {
    "xauusd": ("twelvedata", "xauusd_close"),
    "xagusd": ("coingecko", "xagusd_close"),
    "wti_crude": ("fred", "wti_crude"),
    "brent_crude": ("fred", "brent_crude"),
    "eurusd": ("twelvedata", "eurusd_close"),
    "coffee": ("fred", "coffee"),
    "usdjpy": ("twelvedata", "usdjpy_close"),
    "btc": ("binance", "btc_close"),
    "eth": ("binance", "eth_close"),
    "sol": ("binance", "sol_close"),
}


def _resolve_price_source(asset_id: str) -> tuple[str, str]:
    """Для watchlist-товарів/форексу — явний мапінг вище. Для БУДЬ-ЯКОГО
    іншого asset_id (тикери акцій зі скринінгу, docs/news-purpose.md
    "Ціль 2") — здогад за конвенцією, якою quotes/twelvedata_adapter.py
    сам будує metric_id (`f"{ticker.lower()}_close"`). Безпечно: якщо
    здогад хибний (актив насправді з іншого джерела, напр. крипта) —
    просто не знайдеться жодного спостереження, fetch_price_change()
    поверне None, як і раніше."""
    mapping = ASSET_PRICE_SOURCES.get(asset_id)
    if mapping is not None:
        return mapping
    return ("twelvedata", f"{asset_id.lower()}_close")


@dataclass
class PriceChange:
    asset_id: str
    start_value: Decimal
    end_value: Decimal
    start_date: str
    end_date: str
    pct_change: Decimal


def compute_pct_change(
    asset_id: str, start_value: Decimal, start_date: str, end_value: Decimal, end_date: str
) -> PriceChange:
    """Чиста функція — з готових значень рахує % зміни. Розрахунок
    відокремлено від SQL (fetch_price_change нижче), щоб тестувалось
    без БД, той самий принцип, що й passes_tier_*/decide_revision в
    інших модулях проєкту."""
    pct_change = ((end_value - start_value) / start_value) * Decimal("100") if start_value != 0 else Decimal("0")
    return PriceChange(
        asset_id=asset_id,
        start_value=start_value,
        end_value=end_value,
        start_date=start_date,
        end_date=end_date,
        pct_change=pct_change,
    )


def fetch_price_change(conn, asset_id: str, days: int = 7) -> Optional[PriceChange]:
    """Перше й останнє значення (v_observations_latest_revision) за
    останні `days` днів для asset_id — None, якщо немає даних у вікні
    (для watchlist-товарів/форексу — ASSET_PRICE_SOURCES; для інших
    asset_id, напр. тикерів акцій — здогад _resolve_price_source(),
    теж природно дає None за відсутності даних)."""
    source, metric_id = _resolve_price_source(asset_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT observed_at, value
            FROM v_observations_latest_revision
            WHERE source = %s AND metric_id = %s
              AND observed_at >= now() - (%s || ' days')::interval
            ORDER BY observed_at ASC
            """,
            (source, metric_id, days),
        )
        rows = cur.fetchall()

    if len(rows) < 2:
        return None

    (start_date, start_value), (end_date, end_value) = rows[0], rows[-1]
    return compute_pct_change(
        asset_id, Decimal(start_value), str(start_date), Decimal(end_value), str(end_date)
    )


def fetch_all_price_changes(
    conn, asset_ids: list[str], days: int = 7
) -> dict[str, PriceChange]:
    """Те саме для списку активів одразу — пропускає ті, для яких
    немає джерела чи даних (не помилка, просто немає числового
    контексту для цього активу поки що)."""
    result = {}
    for asset_id in asset_ids:
        change = fetch_price_change(conn, asset_id, days=days)
        if change is not None:
            result[asset_id] = change
    return result


def fetch_latest_observed_at(conn, asset_id: str):
    """Дата НАЙСВІЖІШОГО спостереження для asset_id, БЕЗ обмеження
    вікном `days` (на відміну від fetch_price_change) — або None, якщо
    для цього джерела взагалі ще ніколи нічого не збирали.

    Призначення (2026-09-29, живий фідбек користувача): коли
    fetch_price_change() повертає None, це раніше означало ОДНЕ й те
    саме "немає джерела/даних" і для "збір ніколи не запускався", і для
    "збір є, але завис/відстає" (напр. FRED-серія тижневої давності)
    — ці два випадки принципово різні для діагностики, тому
    synthesize.py викликає цю функцію окремо, щоб сказати чесно, ЯКИЙ
    це випадок."""
    source, metric_id = _resolve_price_source(asset_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MAX(observed_at)
            FROM v_observations_latest_revision
            WHERE source = %s AND metric_id = %s
            """,
            (source, metric_id),
        )
        (latest,) = cur.fetchone()
    return latest


def fetch_price_history(conn, asset_id: str, limit: int = ANOMALY_HISTORY_LOOKBACK) -> list[Decimal]:
    """Останні `limit` значень asset_id у ХРОНОЛОГІЧНОМУ порядку
    (найстаріше перше) — вхід для is_anomalous_move(). Перевикористовує
    common.db.fetch_recent() (той самий запит, що forecasting/backtest.py
    вже використовує для показників) замість власного SQL тут."""
    source, metric_id = _resolve_price_source(asset_id)
    rows = fetch_recent(conn, source, metric_id, limit=limit)  # найновіше перше
    return [Decimal(r["value"]) for r in reversed(rows)]


def is_anomalous_move(
    pct_change: Decimal,
    history: list[Decimal],
    window_days: int,
    min_history: int = ANOMALY_MIN_HISTORY,
    sigma_multiplier: float = ANOMALY_SIGMA_MULTIPLIER,
) -> bool:
    """Чи є |pct_change| за `window_days` незвичним для ЦЬОГО активу,
    судячи з його власної історії `history` (fetch_price_history(),
    хронологічний порядок). Деталі підходу — докстрінг модуля вище.

    `False` (не аномально), якщо історії замало (min_history) ЧИ
    волатильність нульова (stdev=0, напр. усі значення однакові) —
    чесний дефолт "немає статистичної опори судити", не false positive."""
    daily_returns = [
        float((history[i] - history[i - 1]) / history[i - 1]) * 100
        for i in range(1, len(history))
        if history[i - 1] != 0
    ]
    if len(daily_returns) < min_history:
        return False

    daily_sigma = statistics.stdev(daily_returns)
    if daily_sigma == 0:
        return False

    expected_sigma_over_window = daily_sigma * (window_days ** 0.5)
    return abs(float(pct_change)) >= sigma_multiplier * expected_sigma_over_window
