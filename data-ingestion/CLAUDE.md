# data-ingestion — правила модуля

## Відповідальність
ТІЛЬКИ збір і нормалізація сирих даних із зовнішніх джерел. Жодної
аналітики, жодної інтерпретації "добре це чи погано". Якщо виникає
спокуса написати тут щось на кшталт "якщо інфляція > 3% — тривога" —
це belongs у analysis/, не сюди.

## Структура
```
macro/       — макроекономічні показники (інфляція, ставки, ВВП, FX)
companies/   — фундаментал компаній (SEC EDGAR)
quotes/      — ціни/обсяг акцій (Twelve Data)
commodities/ — товарні watchlist-активи БЕЗ щоденного API (нафта/кава/
               газ, tradingeconomics_adapter.py — скрапінг,
               2026-10-04, critical rule 7 CLAUDE.md)
crypto/      — крипта: спот (Binance, CoinGecko) + ф'ючерси для
               crypto_screening (Binance/Bybit/OKX Futures adapters) +
               факторні ряди (2026-10-20): он-чейн (CoinMetrics,
               звірка blockchain.info/Etherscan), потоки в ETF
               (Farside), TVL Solana (DefiLlama)
weather/     — прогноз погоди для товарів (Open-Meteo, звірка MET
               Norway); indices.py — ДЕ дивитись і як згорнути добові
               значення в індекс (HDD для газу, заморозки/опади для кави)
factor_sources.py / run_collect_factors.py — збір усіх ФАКТОРНИХ рядів
               (`config.FACTOR_SERIES`): специфічні дані активів разом
               із другими джерелами для звірки (джоба factor_series)
news/        — новинні стрічки (GDELT, RSS) + queries.py/rss_feeds.py
collect_watchlist.py — ціни списку обраних по `price_chain` КОЖНОГО
               активу + звірка + вибір активного джерела (2026-10-22, було
               в orchestration/jobs.py разом із хардкодом ланцюжків)
common/      — спільний інтерфейс адаптера (adapter.py/news_adapter.py);
               asset_profile.py + profile_lookup.py — ПРОФІЛЬ активу
               (клас, назва/CIK, терміни пошуку, ланцюжок джерел) для
               `/watchlist_add` і backfill_watchlist_profile.py (2026-10-22);
               і шар збереження (db.py/news_db.py/watchlist_db.py —
               таблиця watchlist_assets, єдине джерело істини для
               news/queries.py + analysis/news_analysis/prices.py +
               orchestration/_watchlist_prices + reporting/
               watchlist_notify.py, редагується через Telegram
               /watchlist_add/remove, docs/decisions.md 2026-10-03;
               manual_observation.py — ОСТАННІЙ резервний запис, коли
               для watchlist-активу НЕМАЄ взагалі жодного
               автоматизованого джерела, ні API, ні скрапінг-адаптера
               (source="web_crosscheck", critical rule 7 CLAUDE.md,
               2026-10-04) — НЕ адаптер (немає власного fetch() до
               API), значення приходить ЗЗОВНІ, звірене мінімум на 2
               сайтах, не на розкладі APScheduler (на відміну від
               commodities/tradingeconomics_adapter.py — реального
               автоматизованого скрапінгу); freshness.py —
               is_stale()/business_days_between() (БУДНІ дні, не
               календарні — вихідні не карають форекс/товари за
               закритий ринок), спільний поріг, який
               reporting/watchlist_notify.py ТА
               analysis/news_analysis/prices.py імпортують ОБИДВА;
               quality.py — has_volatile_recent_revisions() (2026-10-04,
               живий кейс xauusd: Twelve Data forex-OTC переписав ВЖЕ
               закритий день заднім числом на 2%, актив виглядав
               "свіжим", але був ненадійним) — на відміну від
               freshness.py (старе/нове), це "те саме минуле значення
               нещодавно саме переписалось" — рахується з уже наявних
               ревізій у raw_observations, без нового стовпця схеми)
```
`reports/` (офіційні звіти, текст 10-K/10-Q) — ще не існує, не почато
(PLAN.md, Крок 4 — єдина обіцянка опису агента, не виконана ніколи).

## Обов'язковий інтерфейс адаптера
Кожне джерело даних — окремий файл/клас з ОДНАКОВОЮ структурою виходу,
незалежно від того, звідки дані прийшли. Мінімум полів у нормалізованому
записі:
- `source` — назва джерела
- `metric_id` — уніфікований ідентифікатор показника (не той, що дає API
  джерела — свій внутрішній, стабільний)
- `value`
- `observed_at` — коли значення відноситься (не коли ми його забрали)
- `fetched_at` — коли ми фактично зібрали (важливо: може відрізнятись від
  observed_at на дні/тижні через затримку публікації)
- `revision` — чи це перше значення, чи ревізія попереднього (макро-дані
  часто ревізуються заднім числом — це критично не втрачати)

## Чому саме такий інтерфейс
`observed_at` vs `fetched_at` — найчастіша помилка новачків у фінансових
даних: плутанина, коли дані стали ВІДОМІ, проти того, до якого періоду
вони відносяться. Це ламає весь подальший аналіз "очікування vs факт",
якщо переплутати.

## Другий інтерфейс — новини (текст, не число)
`news/` (GDELT, RSS) не лягає в інтерфейс вище — `NormalizedRecord.value`
розрахований на числові показники, новина текстова. Паралельний
інтерфейс — `common/news_adapter.py` (`NewsRecord`/`BaseNewsAdapter`),
той самий принцип `fetch()`/`normalize()` і те саме розділення
"коли опубліковано" (`published_at`) проти "коли забрали"
(`fetched_at`). Адаптер новин так само НІЧОГО не інтерпретує — стрім
(`watchlist`/`general`/`geopolitical`) визначає лише яким query
звузити джерело, не оцінку важливості. Чи новина релевантна —
вирішує `analysis/news_analysis/` (DeepSeek), докладніше `docs/decisions.md`,
2026-09-25.

## Типова помилка, якої уникати
Не пишіть парсинг конкретного API прямо в коді, що викликає цей парсинг.
Кожен адаптер — самодостатній модуль, який можна протестувати окремо,
подавши йому фейкову відповідь API.

## Команди
```bash
# усе виконується всередині контейнера app (docker compose up -d --build),
# venv на хості не потрібен

docker compose exec app python data-ingestion/apply_schema.py
docker compose exec app python data-ingestion/run_collect.py --metric cpi
docker compose exec app python data-ingestion/run_collect.py --metric fed_funds_rate --limit 10

# тести адаптерів (на фікстурах, без реальних запитів до API)
docker compose exec app pytest
```

## Секрети
Усі API-ключі — тільки через змінні середовища (.env), ніколи не
хардкодити. Список потрібних змінних веди в .env.example (без значень).

## Джерела даних проєкту (фактичний стан)

Таблиця нижче — те, що РЕАЛЬНО в коді. Раніше тут був план "на старт"
(yfinance для цін, Finnhub як резерв, ECB reference rates для форексу) —
жодне з трьох не реалізовано: ціни акцій пішли через Twelve Data
(yfinance/Stooq/Alpaca розглядались і відкинуті — docs/decisions.md
2026-09-14/20), форекс і товари покрились FRED-серіями.

| Категорія | Джерело | Тип | Адаптер | Застереження |
|---|---|---|---|---|
| Макро (США) | FRED | офіційне першоджерело | `macro/fred_adapter.py` | без практичних лімітів; покриває й FX (EUR/USD, USD/JPY) |
| Товари watchlist (нафта WTI/Brent, кава, природний газ) | TradingEconomics (скрапінг) | неофіційне | `commodities/tradingeconomics_adapter.py` | FRED-серії цих товарів або місячні, або живо застрягли на кілька днів (docs/decisions.md 2026-10-04) — ціна+дата з `<meta name="description">`, без ключа, без JS/бот-захисту (на відміну від Stooq, відкинутого 2026-09-20) |
| Макро (єврозона) | ECB Data Portal | офіційне першоджерело | `macro/ecb_adapter.py` | закриває старі датасети без помилки в запиті (міграція ICP→HICP, docs/decisions.md) |
| Макро (Японія) | BOJ + e-Stat | офіційні першоджерела | `macro/boj_adapter.py`, `macro/estat_adapter.py` | e-Stat: коди area/cat01 резолвляться в рантаймі, `ESTAT_APP_ID` |
| Календар релізів | FRED `/release/dates` + ForexFactory-фід | офіційні дати + неофіційний фід | `monitoring/release_calendar.py`, `monitoring/economic_calendar.py` | ForexFactory неофіційний, але єдине джерело часу/impact/forecast; для EUR/JPY — єдине джерело й самої дати |
| Акції (фундаментал) | SEC EDGAR | офіційне першоджерело | `companies/sec_edgar_adapter.py` | обов'язковий контактний User-Agent, інакше 403 |
| Акції (ціни/обсяг) | Twelve Data | агрегатор, офіційний API | `quotes/twelvedata_adapter.py` | free tier ~8 запитів/хв, 800/добу — найвужче місце конвеєра |
| Крипта (спот, ціна/обсяг) | Binance public API | першоджерело (біржа) | `crypto/binance_adapter.py` | без ключа |
| Крипта (market cap) + срібло | CoinGecko | агрегатор | `crypto/coingecko_adapter.py` | без ключа; срібло — проксі через kinesis-silver |
| Крипта (ф'ючерси — universe/funding/OI/обсяг, для crypto_screening) | Binance + Bybit + OKX Futures | першоджерела (біржі) | `crypto/binance_futures_adapter.py`, `crypto/bybit_futures_adapter.py`, `crypto/okx_futures_adapter.py` | без ключа; одиниці різняться між біржами (OKX volCcy24h/oiCcy — у базовій валюті, не USDT) — 2 живі баги знайдено й виправлено, docs/decisions.md 2026-09-27 |
| Новини (широкий потік) | GDELT DOC 2.0 | агрегатор | `news/gdelt_adapter.py` | **найненадійніше джерело проєкту.** Регулярні 429 на спільному IP + МʼЯКИЙ троттл (HTTP 200 з тілом `{}`, який до 2026-10-05 читався як "немає новин" і тихо вбивав потік `general` на тижні). Тепер: глобальний міжпроцесний ліміт 1 запит/6с (`common/rate_limit.py`), довгі бекофи, мʼякий троттл піднімає помилку. Єдине джерело, що вміє ЦІЛЬОВИЙ запит ("лише про золото"), але з 2026-10-12 **демотоване з опори на доповнення**: провалило всі 4 прогони за добу (потік `watchlist` — 0 статей), тож `exit(1)` знято, а резервом став ПОШУК у власному RSS-корпусі (`watchlist_assets.news_patterns`). ⚠️ На новому IP (VPS) перевірити, чи бан діє — він за IP, не за ключем |
| Новини (офіційні + редакційні) | RSS: Fed/ECB/BOJ + BBC/Al Jazeera/Guardian/NPR/Sky News/DW | першоджерела + агрегатори | `news/rss_adapter.py`, `news/rss_feeds.py` | найнадійніше; широкі фіди замінили курований GDELT-запит для geopolitical (docs/decisions.md 2026-09-27) |
| Новини (ринок/бізнес, потік `general`) | RSS: CNBC/MarketWatch/Investing.com/BBC Business/Guardian Business/NPR Business/FT | агрегатори | `news/rss_adapter.py`, `news/rss_feeds.py` | **резерв потоку `general`, якого до 2026-10-05 не було взагалі** — потік стояв на одному GDELT і помер разом із ним (docs/decisions.md). ~140 статей/прогін, без лімітів запитів. Nasdaq перевірку пройшов, але в прогонах таймаутив — не включений. Yahoo Finance видалено 2026-10-11 (404 щопрогону; робоча альтернатива віддає рекламний клікбейт) |
| Запаси нафти/газу США (факторні ряди) | EIA API v2 | офіційне першоджерело | `commodities/eia_adapter.py` | `EIA_API_KEY` обовʼязковий (DEMO_KEY вичерпується за кілька запитів). Звірка — тижнева ЗМІНА з TradingEconomics (`TradingEconomicsIndicatorAdapter`), не рівень: живо −8 557 проти −8.56 млн |
| Золото в GLD | SPDR (архів емітента, xlsx) | першоджерело | `commodities/spdr_gld_adapter.py` | одне джерело (власна книга емітента); xlsx читається stdlib, Excel-шум float чиститься через `repr(float)` |
| Потоки в спотові BTC/ETH-ETF | Farside (скрапінг) | неофіційне | `crypto/farside_adapter.py` | одне джерело; останній рядок із "-" там, де напередодні було число, — день не закритий, пропускається |
| Он-чейн BTC/ETH (транзакції за добу) | CoinMetrics Community | агрегатор | `crypto/coinmetrics_adapter.py` | без ключа; для SOL мережевих метрик безкоштовно НЕМАЄ. Звірка: blockchain.info (BTC, лаг ~6 днів, розкид ≤1.8%), Etherscan CSV (ETH, точний збіг) |
| TVL Solana | DefiLlama | агрегатор | `crypto/defillama_adapter.py` | одне джерело; поточна (незакрита) доба відкидається |
| Погода для газу й кави | Open-Meteo + MET Norway | агрегатор + офіційна метеослужба | `weather/open_meteo_adapter.py`, `weather/met_norway_adapter.py` | MET вимагає User-Agent із контактом; розкид моделей — невизначеність прогнозу, тривоги немає (`alert=False`) |
| Видобуток OPEC/Сауд. Аравії, газ і СПГ США | EIA STEO (той самий API) | офіційне першоджерело | `commodities/eia_adapter.py` | лише історичні місяці — прогноз STEO відкидається; Сауд. Аравія звіряється з TE (`TradingEconomicsPeriodAdapter`, розрив методик 3-5%); одна повторна спроба на зависання api.eia.gov (~1 з 5 запитів) |
| Сертифіковані запаси кави | ICE (xls BIFF) | першоджерело (біржа) | `commodities/ice_coffee_adapter.py` | потрібен `xlrd`; у неторговий день 404 — адаптер іде назад по датах |
| Оцінки врожаю кави | USDA FAS PSD (архів zip) | офіційне першоджерело | `commodities/usda_psd_adapter.py` | без ключа (REST API вимагає ключ USDA); переглядається двічі на рік — подієвий ряд |
| Золото в IAU | iShares (сторінка емітента) | першоджерело | `commodities/ishares_iau_adapter.py` | JSON в атрибутах HTML, екранований; перевірка тонни ↔ унції |
| Золоті резерви ЦБ (Китай, Польща) | TradingEconomics | агрегатор (WGC/МВФ) | `commodities/tradingeconomics_adapter.py` (`TradingEconomicsPeriodAdapter`) | щокварталу; зі сторінки дві точки (поточна й попередня) |
| Інтервенції Японії | Мінфін Японії (CSV) | офіційне першоджерело | `macro/mof_japan_adapter.py` | CP932; рік у рядках кварталу переноситься; подієвий ряд, денні дані із запізненням до 3 міс. |
| Стейкінг ETH | консенсусний шар Ethereum (Lighthouse, publicnode) | дані блокчейну | `crypto/beacon_staking_adapter.py` | Lighthouse-ендпоінт `validator_inclusion/{epoch}/global`; один вузол |
| Транзакції Solana | 2 RPC-вузли (publicnode + офіційний) | дані блокчейну | `crypto/solana_rpc_adapter.py` | фіксоване вікно 240 зразків — інакше вузли не співставні (живо 12%) |

**Правило:** для будь-якого джерела, позначеного "неофіційне"/"агрегатор",
адаптер повинен явно обробляти й логувати помилки парсингу/зміни формату
— не падати мовчки. Якщо неофіційне джерело недоступне кілька днів
поспіль — це достатня підстава підняти пріоритет переходу на платний
аналог, а не намагатись нескінченно латати парсинг.

**Свідомо не покривається:** Китай та Індія (рішення користувача,
docs/decisions.md 2026-08-30); форекс/товари поза watchlist-парами
(користувач розширює список сам, 2026-09-26).
