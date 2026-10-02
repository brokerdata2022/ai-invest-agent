# Статус проєкту

Одна сторінка "де ми зараз". Оновлюється після кожної завершеної сесії.

- Що потрібно для продакшену, пріоритезовано — **`docs/production-readiness.md`**
- Фази й чекбокси — `PLAN.md`
- Чому кожне рішення таке — `docs/decisions.md`
- Повний покроковий журнал сесій (як усе дійшло до цього стану) —
  `docs/archive/status-journal-2026-09-27.md`, `docs/archive/plan-journal-2026-08-09.md`

**Останній аудит:** 2026-09-28 — живий фідбек користувача виявив, що
частина вже "готової" звітності реально НЕ доносить результат (розділ
"Звітність" нижче) + злито `docs/draft-todo.md` у
`docs/production-readiness.md`, документація приведена в синхронність з
кодом (виправлено застарілі твердження в CLAUDE.md/README.md/
screening-criteria.md, прибрано дублювання структури репозиторію
README.md↔CLAUDE.md). 2026-09-27: оптимізація коду (−480 рядків
дублювання, `analysis/llm_common.py` + `reporting/_common.py`), ротація
`logs/`, прив'язка порту БД до 127.0.0.1. Деталі — `docs/decisions.md`,
прогалини — `docs/production-readiness.md`.

---

## Збір даних (`data-ingestion/`) — 13 адаптерів, усі живо підтверджені

| Джерело | Адаптер | Що збирає |
|---|---|---|
| FRED | `macro/fred_adapter.py` | CPI, Core CPI, PCE, Fed Funds, 10Y/2Y Treasury, Jobless Claims, GDP, Retail Sales, Housing Starts, Mortgage 30Y, NFP, Unemployment, EUR/USD, USD/JPY, WTI/Brent, кава (США) |
| ECB Data Portal | `macro/ecb_adapter.py` | HICP, Deposit Rate, Unemployment (єврозона) |
| BOJ | `macro/boj_adapter.py` | Policy Rate (Японія) |
| e-Stat | `macro/estat_adapter.py` | CPI (Японія) |
| SEC EDGAR | `companies/sec_edgar_adapter.py` | revenue/EPS/shares/assets/liabilities, 500/503 компаній S&P 500 |
| Twelve Data | `quotes/twelvedata_adapter.py` | ціна/обсяг акцій, золото (XAU/USD) |
| Binance (спот) | `crypto/binance_adapter.py` | ціна/обсяг BTC/ETH/SOL |
| CoinGecko | `crypto/coingecko_adapter.py` | market cap BTC/ETH/SOL + срібло (проксі kinesis-silver, ⚠️ без живого прогону) |
| Binance/Bybit/OKX Futures | `crypto/{binance,bybit,okx}_futures_adapter.py` | universe + funding/OI/обсяг для `crypto_screening/`, ✅ живо (527/439/477 контрактів) |
| GDELT | `news/gdelt_adapter.py` | новини, потоки watchlist/general |
| RSS (9 фідів) | `news/rss_adapter.py` | Fed/ECB/BOJ + BBC/Al Jazeera/Guardian/NPR/Sky News/DW, потік geopolitical |

Watchlist активів — `docs/watchlist.md`, каталог metric_id —
`docs/metrics-catalog.md`.

## Аналіз (`analysis/`)

| Напрям | Модулі | Стан |
|---|---|---|
| Скринінг акцій | `screening/` — Tier A→B→C + composite score, `screening_results` | ✅ живо: 411 → 35 → 16 тикерів (цифри рухаються з ринком) |
| Новини: класифікація | `news_analysis/relevance_filter.py` | ✅ живо, усі 3 потоки |
| Новини: агрегація | `news_analysis/aggregate.py` — кластери дублікатів, зведення по активу | ✅ живо |
| LLM-синтез ціна↔новини (Цілі 1, 2) | `news_analysis/synthesize.py` | ✅ живо |
| LLM-синтез стану ринку (Ціль 4) | `news_analysis/synthesize_market.py` | ✅ живо, risk-off 0.55 |
| LLM-відбір нових активів (Ціль 3) | `news_analysis/discover_candidates.py` | ⚠️ код готовий, реального кандидата ще не знайдено (IPO-шум у `GENERAL_TERMS`) |
| Факт vs очікування | `expectations/` — 5 методів, `expectation_comparisons` | ✅ живо, справжній реліз (NFP/Unemployment, 2026-10-02) |
| LLM-синтез сюрпризу + міжактивний вплив | `expectations/synthesize.py` | ✅ на справжньому релізі; 2026-10-02 додано `impacts` — вплив на ставку/економіку/валюту/акції/крипту/золото/інший актив (лише зачеплені категорії, без "не впливає"-заповнювачів). Подача — ДВА окремі Telegram-звіти (нижче, "Звітність"): короткий сюрприз і окремий широкий розбір впливу. |
| **Прогнозування** | `forecasting/` — лінійна регресія + backtest | 🔴 **1 показник із 15, перевага над naive 0.7% (шум), назовні не виходить** — головна незакрита задача, `docs/production-readiness.md` |
| Крипто-скринінг (LONG/SHORT/WATCH) | `crypto_screening/` — Binance+Bybit+OKX → Tier A → RSI/OI/funding | ✅ живо на реальних пампах (QNTUSDT/SOONUSDT); LONG/SHORT ще чекає на 3-8 днів OI-історії; Telegram-сповіщення досі немає (PLAN.md, Крок 5) |

Спільна LLM-проводка (провайдер, розбір відповіді, аудит-лог) —
`analysis/llm_common.py`. Провайдер перемикається однією змінною
`SYNTHESIS_LLM_PROVIDER`; зараз DeepSeek, Anthropic — свідомо пізніше.

## Моніторинг (`monitoring/`) — календар релізів, 15 показників

Двофазно: `refresh_calendar.py` (тижнево, заводить `pending` наперед)
→ `check_releases.py` (кожні 15 хв, активно тригерить збір після
настання часу + буфер). Джерело дати: FRED `/release/dates` для 10
US-показників, ForexFactory-фід для 5 EUR/JPY (для US — збагачення
точним часом/impact/forecast).

- ✅ `refresh_calendar` — живо, повний 15-показниковий прогін.
- ✅ `check_releases` — живо підтверджено 2026-10-02: NFP/Unemployment
  (США) підхоплено й пройшло повний цикл до Telegram-сповіщення.
  2026-10-02 (живий фідбек користувача): увесь ланцюжок
  check_releases→update_forecasts→compare_expectations→
  synthesize_expectations→notify_expectations тепер щохвилини (було
  раз/15хв + 30-хв буфер) — порядок у межах хвилини тримається на
  "second" (0/10/15/20/50), детекція+сповіщення тепер за ~1-2 хв від
  scheduled_at замість до ~44 хв (docs/decisions.md). ⚠️ Побічний
  ефект: ~15x більше файлів у logs/ на добу для цього ланцюжка —
  prune_logs (14 днів) чистить, але не оптимізовано.

Неперервні щоденні ряди (ставки/дохідності/FX/commodity) навмисно не
покриті — у них немає "події релізу".

## Звітність (`reporting/`)

12 Telegram-сценаріїв: останнє значення показника, релевантні новини,
синтез ціна/новини, стан ринку, кандидати-новачки, сюрприз
факт/очікування, комплексний розбір впливу релізу (`release_impact_notify.py`,
новий 2026-10-02 — окремо від сюрпризу, рішення користувача), скринінг
S&P 500 (`screening_notify.py`, новий 2026-10-02, джоба
`notify_screening`@5:10, 1х/добу, усі дні — другий щоденний прогін
того самого дня відкотили: ціни оновлюються лише 1х/добу (Twelve Data
лімітом), другий прогін рахував би те саме), повідомлення —
тикер/назва/зміна за 24г, без сирих компонентів score. Крипто-скринінг
SHORT/WATCH (`crypto_screening_notify.py`, новий 2026-10-02, джоба
`notify_crypto_screening`@0:32/6:32/12:32/18:32, 4х/добу), крипто-скринінг
LONG (`crypto_long_notify.py`, новий 2026-10-02, джоба
`notify_crypto_long`@0:37/6:37/12:37/18:37, 4х/добу — раніше LONG лише
логувався, ніколи не йшов у БД/Telegram), поточні ціни watchlist-активів
(`watchlist_notify.py`, новий 2026-10-02, джоба `notify_watchlist`@5:20/17:20,
2х/добу — знімок без дедупу notified_at, на відміну від решти). Каденція
(акції 1х, watchlist 2х, крипто 4х) — рішення користувача 2026-10-02,
деталі `docs/decisions.md`. Щоденний дайджест (`daily_digest.py`, без
нового LLM-виклику). Спільний бойлерплейт — `reporting/_common.py`.

🔴 **Підтверджено живим використанням 2026-09-28 (`docs/production-readiness.md`,
розділ 3а) — код "працює", але не доносить обіцяне:**
- ✅ **Виправлено 2026-10-02:** скринінг S&P 500 (`screening_results`)
  тепер надсилається в Telegram — `reporting/screening_notify.py`
  (топ-N за composite score, дедуп `notified_at`), джоба
  `notify_screening` 1х/добу. Крипто-скринінг SHORT/WATCH
  (`crypto_screening_candidates`) — теж ✅, `reporting/crypto_screening_notify.py`
  + скидання `notified_at` при зміні статусу (`_candidates_db.py:
  update_candidate()`). Крипто-скринінг LONG — теж ✅ (закрито
  одразу за SHORT/WATCH): нова таблиця `crypto_long_candidates`
  (append-only знімок, `run_screening.py:save_long_run()`) +
  `reporting/crypto_long_notify.py`, обидва 4х/добу; раніше LONG
  лише логувався, ніколи не йшов у БД.
- `synthesize_market.py:top_clusters()` підписує вивід як "найбільш
  підтверджені історії", хоча найчастіше жодна не підтверджена другим
  джерелом (усі `source_count=1`) — реально це просто найсвіжіші.
  (не виправлено)
- Заголовки не англійською мовою йдуть у Telegram неперекладеними.
  (не виправлено)
- Тижневого огляду календаря релізів не існує взагалі (лише
  `daily_digest.py`, і той — тільки вже минуле вікно, не наперед).
  (не виправлено, тепер частина ширшого нового спеку — PLAN.md "Фаза 5")

✅ **Виправлено того самого дня:** `news_notify.py` більше не дублює
ранкове/вечірнє (дедуп `notified_at`) і не шле "останні N регардлесс
якості" (фільтр за `confidence`); той самий дедуп додано в
`synthesis_notify`/`market_notify`/`candidates_notify`
(`docs/decisions.md`, live-підтвердження в реальному чаті — попереду).

📋 **Новий повний спек вимог від користувача (2026-09-28)** — сесійна
звітність (3× на добу за відкриттям бірж), Telegram-команди людською
мовою, тижневий/щоденний календар з об'єднаним аналізом одночасних
релізів, 14:00 фундаментальний аналіз, LLM-прогнозування замість
Python — `docs/decisions.md`, розбивка PLAN.md "Фаза 5".

## Оркестрація (`orchestration/`)

APScheduler у сервісі `scheduler` (docker compose, `restart:
unless-stopped`), часовий пояс Europe/Kyiv. Розклад —
`orchestration/schedule.py` (єдиний файл для зміни періодичності),
реєстр "що виконати" — `jobs.py`. Провал джоби (ненульовий exit,
timeout, виняток) → повторна спроба (дефолт: 1 ретрай, 60с пауза,
`runner.py`, 2026-09-28) → Telegram-алерт лише після вичерпання спроб;
успіх (одразу чи на ретраї) → лише файл у `logs/`. Логи прибираються
джобою `prune_logs` (14 днів).

✅ **Heartbeat планувальника — перший крок, 2026-10-02** (живий випадок:
реліз о 15:30 опрацьовано аж о 17:57 через непомічену ~11-год простою
контейнера): `scheduler_heartbeat` (нова джоба, кожні 5 хв) + перевірка
розриву при старті процесу (`main.py:check_startup_gap`) → один
Telegram-алерт, якщо простій був ненормально довгим. **Не закриває
повністю** P0 №4 — не зовнішній watchdog і не real-time алерт під час
самого crash-loop, деталі й межа рішення — `docs/production-readiness.md`.

## Тести

452 проходять — усі на фікстурах/monkeypatch, без мережі й без реальної
БД:

```bash
docker compose exec app pytest -q
```

Тести перевіряють **код**, не наявність даних: на свіжій БД вони
проходять, а скринінг/синтез/дайджест нічого не покажуть, доки не
виконано bootstrap (`README.md`, "Перший запуск з чистими даними").

## Відкриті другорядні питання (не блокують)

- `shares_outstanding` відсутній для ~110/501 компаній S&P 500 (SEC
  віддає порожній `units.shares` — ймовірно компанії з кількома класами
  акцій). 365/491 — робочий результат.
- GDELT віддає 429 при інтенсивному використанні (спільний вихідний IP);
  адаптер має retry з backoff, дедуп робить повтор безпечним.
- Ціни нових тикерів зі скринінгу накопичуються природно — для % зміни
  одразу потрібен був би backfill при появі тикера в `screening_results`.

## Наступний змістовний крок

**Три критичні фікси (ретрай джоб, дедуп сповіщень, фільтр важливості
новин) закрито 2026-09-28, `screening_notify.py` закрито 2026-10-02** —
деталі `docs/decisions.md`. Далі:

1. **Бекап БД** — джоба `pg_dump` (P0, суперечність із критичним
   правилом №6).
2. **Heartbeat планувальника** (P0).
3. **Прогнозування ЗМІНИЛО напрямок (2026-09-28): LLM, не Python-модель**
   — PLAN.md "Фаза 5", скасовує попередній план "backtest 14
   показників лінійною регресією".
4. Новий великий спек (сесійна звітність, Telegram-команди, тижневий
   календар, 14:00 фундаментальний аналіз) — PLAN.md "Фаза 5",
   потребує окремих сесій.
5. Живий прогін ланки реліз → порівняння → синтез → сповіщення на
   справжньому релізі 30.09–02.10.

Повний пріоритезований список — `docs/production-readiness.md`.
