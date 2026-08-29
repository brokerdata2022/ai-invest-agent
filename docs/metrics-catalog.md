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
| Housing Starts | `HOUST` | місячна | опційно |
| Mortgage Rates (30Y Fixed) | `MORTGAGE30US` | щотижнева | опційно |

## Макро — єврозона (джерело: ECB SDW, окремий адаптер — ще не написаний)

| Показник | Аналог до США |
|---|---|
| HICP | CPI |
| Deposit Facility Rate | Fed Funds Rate |
| Unemployment Rate | Unemployment Rate |

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
**Наступний крок (Фаза 1):** усі ключові макропоказники США з цього
списку (крім опційних Housing Starts / Mortgage Rates) вже в
`macro/fred_adapter.py:METRICS`. Далі природний наступний крок — перший
новий адаптер поза FRED: `companies/` (SEC EDGAR, звіти й фундаментал)
або `news/` (GDELT, новинний потік) — обидва потребують нової логіки
парсингу (не просто новий запис у словнику), тож це вже інша сесія.
