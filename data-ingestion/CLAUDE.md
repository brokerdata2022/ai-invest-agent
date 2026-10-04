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
               crypto_screening (Binance/Bybit/OKX Futures adapters)
news/        — новинні стрічки (GDELT, RSS) + queries.py/rss_feeds.py
common/      — спільний інтерфейс адаптера (adapter.py/news_adapter.py)
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
(PLAN.md Фаза 2).

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
| Новини (широкий потік) | GDELT DOC 2.0 | агрегатор | `news/gdelt_adapter.py` | регулярні 429 на спільному IP — є retry з backoff |
| Новини (офіційні + редакційні) | RSS: Fed/ECB/BOJ + BBC/Al Jazeera/Guardian/NPR/Sky News/DW | першоджерела + агрегатори | `news/rss_adapter.py`, `news/rss_feeds.py` | найнадійніше; широкі фіди замінили курований GDELT-запит для geopolitical (docs/decisions.md 2026-09-27) |

**Правило:** для будь-якого джерела, позначеного "неофіційне"/"агрегатор",
адаптер повинен явно обробляти й логувати помилки парсингу/зміни формату
— не падати мовчки. Якщо неофіційне джерело недоступне кілька днів
поспіль — це достатня підстава підняти пріоритет переходу на платний
аналог, а не намагатись нескінченно латати парсинг.

**Свідомо не покривається:** Китай та Індія (рішення користувача,
docs/decisions.md 2026-08-30); форекс/товари поза watchlist-парами
(користувач розширює список сам, 2026-09-26).
