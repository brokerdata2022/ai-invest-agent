# Каталог показників

Робочий список того, що плануємо збирати для повного аналізу. Це
карта на кілька фаз наперед, не чекліст "усе одразу" — беремо
показники частинами під час Фази 1, звужуючи чи розширюючи список
за потреби.

**Принцип (не міняється фазами):** тут зберігаються тільки сирі
факти — числа як є від джерела, без інтерпретації. Розрахунки типу
MoM/YoY % зміни, порівняння факт/консенсус, тренди — це відповідальність
`analysis/`, не `data-ingestion/`. Див. `docs/decisions.md` запис
"revision обчислює шар збереження" — та сама логіка розділення
застосовується і тут: `data-ingestion/` збирає, `analysis/` рахує.

## Макро — США (джерело: FRED, адаптер уже є — `macro/fred_adapter.py`)

| Показник | FRED series_id | Частота | Статус |
|---|---|---|---|
| CPI (інфляція) | `CPIAUCSL` | місячна | ✅ зібрано (Фаза 0) |
| Core CPI (без їжі/енергії) | `CPILFESL` | місячна | ✅ адаптер готовий (metric_id `core_cpi`) |
| PCE Price Index (орієнтир ФРС) | `PCEPI` | місячна | ✅ адаптер готовий (metric_id `pce_price_index`) |
| Fed Funds Rate | `DFF` | щоденна | ✅ адаптер готовий (metric_id `fed_funds_rate`) |
| 10Y Treasury Yield | `DGS10` | щоденна | ✅ адаптер готовий (metric_id `treasury_10y`) |
| 2Y Treasury Yield | `DGS2` | щоденна | ✅ адаптер готовий (metric_id `treasury_2y`, разом з 10Y — спред 10Y-2Y, індикатор рецесії) |
| Unemployment Rate | `UNRATE` | місячна | ✅ адаптер готовий (metric_id `unemployment_rate`) |
| Non-Farm Payrolls | `PAYEMS` | місячна | ✅ адаптер готовий (metric_id `nonfarm_payrolls`) |
| Initial Jobless Claims | `ICSA` | щотижнева | ✅ адаптер готовий (metric_id `initial_jobless_claims`) |
| Real GDP | `GDPC1` | квартальна | ✅ адаптер готовий (metric_id `real_gdp`) |
| Retail Sales | `RSAFS` | місячна | ✅ адаптер готовий (metric_id `retail_sales`) |
| Housing Starts | `HOUST` | місячна | ✅ адаптер готовий (metric_id `housing_starts`) |
| Mortgage Rates (30Y Fixed) | `MORTGAGE30US` | щотижнева | ✅ адаптер готовий (metric_id `mortgage_rate_30y`) |

## Макро — єврозона (джерело: ECB Data Portal, адаптер уже є — `macro/ecb_adapter.py`)

| Показник | ECB flowRef.seriesKey | Частота | Статус |
|---|---|---|---|
| HICP (аналог CPI) | `HICP.M.U2.N.000000.4D0.ANR` | місячна | ✅ адаптер готовий (metric_id `eurozone_hicp`; датасет `ICP` закрито ECB 4 лют. 2026, замінено на `HICP`) |
| Deposit Facility Rate (аналог Fed Funds Rate) | `FM.D.U2.EUR.4F.KR.DFR.LEV` | щоденна | ✅ адаптер готовий (metric_id `eurozone_deposit_rate`) |
| Unemployment Rate | `LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T` | місячна | ✅ адаптер готовий (metric_id `eurozone_unemployment_rate`) |

## Макро — Азія (джерело — TBD, окремий адаптер, у плані)

Другий за важливістю регіон після США й єврозони. Точні джерела ще
не досліджені (на відміну від FRED/ECB, єдиного офіційного порталу з
SDMX/REST API для всієї Азії немає — імовірно, окремо по країнах).
Орієнтир для наступної сесії:

| Показник | Країна | Ймовірне джерело | Статус |
|---|---|---|---|
| CPI (інфляція) | Японія | e-Stat (Statistics Japan) або BOJ | у плані |
| Policy Rate | Японія | Bank of Japan (BOJ) Time-Series Data Search | у плані |
| CPI (інфляція) | Китай | NBS (National Bureau of Statistics) | у плані |
| Policy Rate (LPR) | Китай | PBOC (People's Bank of China) | у плані |
| CPI (інфляція) | Індія | MOSPI / RBI | у плані |
| Policy Rate (Repo Rate) | Індія | RBI (Reserve Bank of India) | у плані |

Перед написанням адаптера — окрема сесія на дослідження API кожної
країни (формат відповіді, потреба в ключі, ліміти), за тим самим
принципом, що й для ECB: `web_search` для series_id/API перед кодом.

## Випереджаючі індикатори (джерело — TBD, не в FRED напряму)

- ISM Manufacturing PMI
- ISM Services PMI

## Компанії (джерело: SEC EDGAR + Finnhub — адаптер ще не написаний)

- Earnings: EPS факт vs. консенсус, Revenue факт vs. консенсус, guidance
- Insider trading (Form 4, SEC EDGAR)
- Аналітичні рейтинги / price targets (Finnhub, безкоштовний тір з лімітами)

## Ринок загалом

- S&P 500, Nasdaq — індекси як бенчмарк
- VIX — індекс волатильності ("індикатор страху")
- Крива дохідності — вже покрито вище (DGS10/DGS2)

## Крипто (джерело: CoinGecko / Binance — адаптер ще не написаний)

- Ціна/об'єм топ-активів
- Funding rates, on-chain метрики — опційно, пізніше і складніше

## Новини / сентимент (джерело: GDELT + офіційні RSS)

- Окремий потік, фільтрація за релевантністю — деталі в Фазі 1 плану

## Календар релізів

Коли виходять наступні дані по кожному показнику вище. Критично для
Фази 3 (моніторинг), але структуру варто продумати вже під час Фази 1,
бо вона впливає на схему `release_log` (вже є заготовка в `db/schema.sql`).

---
**Наступний крок (Фаза 1):** Макро — США і Макро — єврозона повністю
закрито (13 + 3 показники, `macro/fred_adapter.py` +
`macro/ecb_adapter.py`). Далі — Макро — Азія (потребує дослідження
джерел по кожній країні окремо, на відміну від FRED/ECB) або перший
адаптер поза макро: `companies/` (SEC EDGAR) чи `news/` (GDELT).
