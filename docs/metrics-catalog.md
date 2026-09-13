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
| USD/JPY (для carry trade разом з fed_funds_rate/japan_policy_rate) | `DEXJPUS` | щоденна | ✅ адаптер готовий (metric_id `usdjpy_fx_rate`; Fed H.10 release, не OECD MEI — та серія й далі оновлюється, на відміну від застарілих OECD-серій Японії, див. нижче) |

## Макро — єврозона (джерело: ECB Data Portal, адаптер уже є — `macro/ecb_adapter.py`)

| Показник | ECB flowRef.seriesKey | Частота | Статус |
|---|---|---|---|
| HICP (аналог CPI) | `HICP.M.U2.N.000000.4D0.ANR` | місячна | ✅ адаптер готовий (metric_id `eurozone_hicp`; датасет `ICP` закрито ECB 4 лют. 2026, замінено на `HICP`) |
| Deposit Facility Rate (аналог Fed Funds Rate) | `FM.D.U2.EUR.4F.KR.DFR.LEV` | щоденна | ✅ адаптер готовий (metric_id `eurozone_deposit_rate`) |
| Unemployment Rate | `LFSI.M.U2.S.UNEHRT.TOTAL0.15_74.T` | місячна | ✅ адаптер готовий (metric_id `eurozone_unemployment_rate`) |

## Макро — Японія (Китай/Індія свідомо не розглядаємо — рішення користувача 2026-08-30, немає офіційного API, див. `docs/decisions.md`)

| Показник | Джерело | Деталі доступу | Статус |
|---|---|---|---|
| Policy Rate (Uncollateralized O/N Call Rate) | Bank of Japan Time-Series Data Search API | Без ключа. `db=FM01`, код серії `STRDCLUCON`. `macro/boj_adapter.py`, metric_id `japan_policy_rate`. | ✅ адаптер готовий, **живий прогін підтверджено користувачем 2026-08-30** (5 записів у raw_observations) |
| CPI (інфляція) | e-Stat (政府統計の総合窓口) API v3.0, `getStatsData` | Потрібен `appId` (`ESTAT_APP_ID` в .env) — **користувач уже додав ключ**. Статистична таблиця: 2025年基準消費者物価指数 (база 2025=100, чинна з 21.08.2026), `statsDataId=0004052037`. `macro/estat_adapter.py`, metric_id `japan_cpi`. Коди area="全国"/cat01="総合" не хардкодяться — адаптер резолвить їх сам через метадані CLASS_INF при кожному запиті (двоетапний fetch: спершу метадані, тоді дані). | ✅ живий прогін пройшов (2026-09-13, після перезбирання Docker — початковий DNS-збій виявився транзієнтним); під час прогону знайдено і виправлено реальний баг зі змішуванням індексу й %-змін через нерезолвлений вимір `tab` (деталі, фікс і нові тести — `docs/decisions.md`) |
| USD/JPY (для carry trade) | FRED, `DEXJPUS` (Fed H.10, не OECD MEI) | Через уже наявний `macro/fred_adapter.py`. metric_id `usdjpy_fx_rate`. | ✅ адаптер готовий (свідомо через FRED, а не BOJ FM08 — щоб не тримати дві неперевірені структури відповіді одночасно) |

Carry trade Японія/США: `fed_funds_rate` (FRED) − `japan_policy_rate`
(BOJ) = диференціал ставок; `usdjpy_fx_rate` (FRED) — сам курс. Сам
диференціал — розрахунок, належить `analysis/` (Фаза 2), тут лише
збір трьох сирих компонентів.

**Наступний крок:** живий тест `japan_cpi` через Docker — якщо
структура відповіді e-Stat відрізняється від очікуваної
(`_resolve_area_and_cat01` кине ValueError з описом, що саме не
знайдено), надішліть повідомлення про помилку чи сирий JSON, і
`normalize()`/`_resolve_area_and_cat01()` буде виправлено за тим же
протоколом, що й для ECB/BOJ.

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
**Наступний крок (Фаза 1):** Макро — США (14, включно з USD/JPY),
єврозона (3) і Японія (Policy Rate + CPI, CPI чекає живого тесту)
покриті кодом. Після підтвердження `japan_cpi` — перший адаптер поза
макро: `companies/` (SEC EDGAR) чи `news/` (GDELT). Китай/Індія —
поза планом (рішення користувача 2026-08-30).
