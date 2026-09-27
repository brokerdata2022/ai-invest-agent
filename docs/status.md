# Статус проєкту

Одна сторінка "де ми зараз" — заміняє розкидані по PLAN.md/decisions.md
записи "наступна сесія починає звідси". Оновлюється після кожної
завершеної сесії. Детальний план по фазах — `PLAN.md`, обґрунтування
рішень — `docs/decisions.md`, повний журнал сесій — `docs/archive/`.

## Що працює живо (підтверджено реальними прогонами)

### Збір даних (data-ingestion/)
| Джерело | Адаптер | Що збирає | Статус |
|---|---|---|---|
| FRED | `macro/fred_adapter.py` | CPI, Core CPI, PCE, Fed Funds Rate, 10Y/2Y Treasury, Jobless Claims, GDP, Retail Sales, USD/JPY, і ін. (США) | ✅ живо |
| ECB Data Portal | `macro/ecb_adapter.py` | HICP, Deposit Rate, Unemployment (єврозона) | ✅ живо |
| BOJ | `macro/boj_adapter.py` | Policy Rate (Японія) | ✅ живо |
| e-Stat | `macro/estat_adapter.py` | CPI (Японія) | ✅ живо |
| SEC EDGAR | `companies/sec_edgar_adapter.py` | revenue/EPS/shares/assets/liabilities, S&P 500 (500/503 компаній) | ✅ живо |
| Twelve Data | `quotes/twelvedata_adapter.py` | ціна/обсяг акцій | ✅ живо |
| Binance | `crypto/binance_adapter.py` | ціна/обсяг BTC/ETH/SOL (klines) | ✅ живо (2026-09-26) |
| CoinGecko | `crypto/coingecko_adapter.py` | market cap BTC/ETH/SOL + срібло (xagusd, проксі kinesis-silver) | ✅ живо, крипто-частина; xagusd — код+тести готові, live-прогін користувача ще не підтверджено (2026-09-26) |

### Скринінг акцій (analysis/screening/) — воронка Tier A → B → C → ранжування
Критерії — `docs/screening-criteria.md`. Universe — S&P 500 (constituents.csv).

| Крок | Що фільтрує | Живий результат |
|---|---|---|
| Tier A | ліквідність (ціна >$10, капіталізація >$10 млрд, $ обсяг >$10 млн/день) | 411 / 491 пройшли (2026-09-25, актуальні ціни — цифра рухається з ринком, не константа) |
| Tier B | фундаментал (прибутковість, revenue/EPS YoY, дилюція, L/A) | 35 / 411 пройшли |
| Tier C | valuation (P/E, P/S, PEG) | 16 / 35 пройшли |
| Composite score | ранжування пройшли-Tier-C за формулою (не фільтр) | 16 ранжованих, топ-10 показано |

**Продуктивність (виправлено 2026-09-25):** до фіксу N+1-запитів сам
Tier A займав ~9.5 хв на 491 тикер. Після фіксу — весь ланцюжок
Tier A→B→C→ранжування виконується за ~7 секунд (підтверджено живим
прогоном користувача, `composite_score.py --top 10`, числа збіглися:
411/35/16 — фікс не змінив результат, тільки швидкість). Причина й
деталі фіксу — `docs/decisions.md`, 2026-09-25.

**Топ-10 кандидатів (живий прогін 2026-09-25):** FANG, COP, HPE, IVZ,
UBER, BX, STLD, HAL, MDT, CASY (score/деталі — вивід
`composite_score.py --top 10`, не зберігається в БД, тільки друкується).

Тести: 225/225 живо підтверджено (`docker compose exec app pytest -q`,
2026-09-26) — включно з +4 на `avg_dollar_volume_from_series` і новими
тестами crypto-адаптерів (test_binance_adapter.py/
test_coingecko_adapter.py).

### Новини (news/, GDELT + RSS + DeepSeek) — усі джерела живо підтверджені
Обсяг — `docs/decisions.md` 2026-09-25 "news/ — обсяг, межа шарів і
схема БД". Усі 3 потоки (watchlist/geopolitical/general) і обидва
механізми збору (GDELT-query + офіційний RSS) реалізовані й
підтверджені живо. news/ з початкового плану — повністю готовий.

| Крок | Модуль | Статус |
|---|---|---|
| Збір (GDELT, watchlist.md) | `data-ingestion/run_collect_news.py --stream watchlist` | ✅ живо, 75 статей у `raw_news` (2026-09-25) |
| Збір (GDELT, тикери зі скринінгу) | `analysis/news_analysis/collect_stock_news.py` | ✅ живо, 150 статей у `raw_news` (2026-09-25) — query ділиться на групи (`batch_ticker_names`, GDELT відхиляє і занадто довгий, і окремі "надто загальновживані" слова типу "Uber" — `STOCK_NAME_OVERRIDES`) |
| Збір (GDELT, geopolitical) | `data-ingestion/run_collect_news.py --stream geopolitical` | ✅ живо, 72 статті у `raw_news` (2026-09-26) |
| Збір (GDELT, general) | `data-ingestion/run_collect_news.py --stream general` | ✅ живо, 74 статті у `raw_news` (2026-09-26) |
| Збір (RSS, Fed+ECB+BOJ) | `data-ingestion/run_collect_rss.py` | ✅ живо, 20+15+46 записів (2026-09-26) — `.content` замість `.text` (UTF-8 BOM у Fed без charset у заголовку ламав `.text`) |
| Аналіз (DeepSeek) | `analysis/news_analysis/` (deepseek_client/relevance_filter/_db) | ✅ живо: watchlist 25/25 (`asset_id` коректно заповнюється), geopolitical 72+35/107 (GDELT+RSS), general 74/74 (`asset_id=None` за задумом для geopolitical/general) — багатомовні джерела без проблем |
| Сповіщення (Telegram) | `reporting/news_notify.py` | ✅ живо, 4 релевантні з 5 надіслано в Telegram (2026-09-25) |
| Ціни watchlist-активів | `macro/fred_adapter.py` (WTI/Brent/EUR-USD/кава) + `quotes/twelvedata_adapter.py` (золото) + `crypto/coingecko_adapter.py` (срібло, проксі kinesis-silver) | ✅ 6/6, срібло-проксі — live-прогін ще не підтверджено (2026-09-26) |
| Агрегація | `analysis/news_analysis/aggregate.py` — кластеризація дублікатів + зведення по активу | ✅ живо |

**Збір даних по news/ — закрито (рішення користувача, 2026-09-26).**
Синтез (Anthropic API) і щоденний дайджест — відкладені до Фази 2.

**Якість (виправлено 2026-09-26, за фідбеком користувача):**
GDELT-запити не обмежувались за часом — місяцями старі статті
потрапляли в аналіз як "актуальні" (виявлено: липнева стаття про
ставку в результатах у вересні). Виправлено: `timespan=3d` у
`GdeltAdapter`, `news_notify.py` сортує/фільтрує за `published_at`
статті (не за часом аналізу), критерій релевантності в DeepSeek
звужено до 3 конкретних категорій (економічний показник/геополітична
подія з ринковим наслідком/конкретний вплив на ціну), опис статті
(RSS) тепер передається в промпт, не тільки заголовок. Живо
підтверджено (2026-09-26): повторний збір `general` після фіксу — 0
нових (усе за останні 3 дні вже було), без "too short/too long"/429.

**Відкрите (не блокує):** GDELT — спільний вихідний IP dev-мережі
часто впирається в `429` (задокументований ліміт GDELT — 1 запит/5с,
але на практиці стійкіше) — адаптер має retry-with-backoff, але при
дуже інтенсивному використанні сесії окремі групи запитів можуть
провалюватись і вимагати повторного запуску (дедуп по `source+
external_id` робить повтор безпечним, нічого не дублюється).

**5 цілей news/ поставлено користувачем 2026-09-26** —
`docs/news-purpose.md` (точки входу для пар / фундаментал watchlist /
нові активи / глобальний контекст / щоденний дайджест), з чесним
розбором що вже є й що блокує кожну.

**Крок 1 із запропонованого плану — агрегація (2026-09-26):**
`analysis/news_analysis/aggregate.py` — кластеризація дублікатів (та
сама історія з різних видань) + зведення сигналів по активу за вікно
(`net_lean = up - down` серед кластерів). Живо підтверджено на 108
релевантних статтях: AP wire-дублікат згруповано в 6 джерел; знайдено
й виправлено живий баг — `normalize_title()` спочатку губила
нелатинський текст (гінді/китайська/арабська — більшість наших живих
даних), через що дві різні історії хибно об'єднувались.

**Крок 2 — LLM-синтез ціна↔новини, Ціль 1 (2026-09-27):**
`analysis/news_analysis/synthesize.py` — зводить `AssetSignal`
(агрегація) з `PriceChange` (`prices.py`, код був готовий, ще ніким не
викликався) в причинний висновок (тренд/шум) через DeepSeek. Нова
таблиця `news_synthesis` + `reporting/synthesis_notify.py` (Telegram) +
оркестрація (`news_synthesis`@6:40, `notify_synthesis`@6:45, раз на
добу — ціна оновлюється раз на добу, частіший синтез коштував би LLM
без нової інформації). Обсяг — тільки 6 watchlist-активів з ціною
(xauusd/wti_crude/brent_crude/eurusd/coffee/usdjpy); xagusd/btc/eth/sol
і тикери зі скринінгу без цінового джерела в `ASSET_PRICE_SOURCES` —
пропускаються з логом, не синтезуються. Провайдер — DeepSeek
(`SYNTHESIS_LLM_PROVIDER`, докладніше `docs/decisions.md`), Anthropic
— свідомо відкладено (клієнт не написаний). **Live-прогін підтверджено
(2026-09-27):** 5 активів із сигналом, 3 синтезовано (xauusd/
brent_crude/wti_crude — останній з другої спроби, перша впала через
тимчасовий DNS-збій контейнера, per-item обробка помилок відпрацювала
як задумано), 2 пропущено без цінового джерела (usdjpy/btc);
Telegram-сповіщення надіслано. Тести — на фікстурах/monkeypatch
(`analysis/tests/test_synthesize.py`, `reporting/tests/test_synthesis_notify.py`).

**Крок 3 — LLM-синтез глобального контексту, Ціль 4 (2026-09-27):**
`analysis/news_analysis/synthesize_market.py` — geopolitical/general
новини не прив'язані до активу (`asset_id` завжди NULL), тому замість
`aggregate_by_asset()` новий `aggregate.py:top_clusters()` (топ-N
найбільш підтверджених історій за `source_count`). Зводить їх з
макро-контекстом (10Y/2Y Treasury, Fed Funds Rate, EUR/USD, USD/JPY,
ECB Deposit Rate, BOJ Policy Rate — `fetch_recent()`, останнє й
попереднє значення) в risk-on/risk-off висновок. Нова таблиця
`market_synthesis` (окрема форма від `news_synthesis` — `macro_context`
JSONB замість `asset_id`/`price_*`) + `reporting/market_notify.py` +
оркестрація раз на добу ввечері (`market_synthesis`@18:40,
`notify_market_synthesis`@18:45 — після вечірнього циклу geopolitical/
general@18:20). Код (SynthesisResult/parse_response/call_llm) навмисно
дубльований із `synthesize.py`, не спільний модуль — той самий
принцип, що вже є між `relevance_filter.py`/`synthesize.py`. Тести —
`analysis/tests/test_aggregate.py` (`top_clusters`),
`analysis/tests/test_synthesize_market.py`,
`reporting/tests/test_market_notify.py`. Live-прогін користувач
підтверджує сам. Цілі 2/3/5 (`docs/news-purpose.md`) синтезом ще не
покриті.

### monitoring/ — календар релізів, двофазний цикл, US+EUR+JPY (2026-09-26/27)

Redesign 2026-09-26 (перший варіант — заднім-числом орієнтований —
замінено після фідбоку користувача, живого прогону), розширено
2026-09-27 на єврозону/Японію (користувач: торгуємо EUR/USD, USD/JPY —
watchlist). Деталі й компроміси — `docs/decisions.md`.

| Модуль | Що робить | Статус |
|---|---|---|
| `release_calendar.py` | графік релізів FRED (`/fred/release/dates`, авторитетна ДАТА) — 10 US-показників + fallback-класифікація high/medium/low + типовий час 8:30 ET (`zoneinfo`) | ✅ код+тести на живій фікстурі |
| `economic_calendar.py` | ForexFactory-фід (`ff_calendar_thisweek.json`, неофіційний, живо перевірений, покриває USD/EUR/JPY) — точний час/impact/forecast (збагачення для US, ЄДИНЕ джерело дати для EUR/JPY), фільтр по country | ✅ код+тести на живій фікстурі (лише `initial_jobless_claims` підтверджено збігом цієї сесії, EUR/JPY-назви — з термінології ForexFactory, не live-підтверджені) |
| `metric_sources.py` | реєстр metric_id → (адаптер, env-змінна ключа) — FRED/ECB/BOJ/e-Stat, 15 показників | ✅ |
| `release_log.py` | чиста логіка `should_seed_new_cycle`/`is_past_buffer` (окремо від SQL) + I/O, `get_pending_entries()` по всіх джерелах | ✅ код+тести на чистій логіці |
| `refresh_calendar.py` | тижнева періодичність: FRED-анкоровані (US) + календар-only (EUR/JPY, `find_upcoming_event()`) → `release_log` 'pending' наперед | ✅ живо підтверджено (2026-09-27) — повний 15-показниковий прогін, фід перекотився на новий тиждень, більшість показників отримали реальні forecast-значення |
| `check_releases.py` | частий запуск: 'pending' рядки, чий час+буфер минув → активно викликає відповідний адаптер (`metric_sources.py`), позначає 'detected' | код готовий, **live-прогін неможливо перевірити зараз** — найближчі дати релізів (30 вересня — 2 жовтня, `release_log`, live-перевірено 2026-09-27) ще не настали |

Неперервні щоденні ринкові ряди (ставки/дохідність/FX/commodity-ціни)
навмисно не покриті — немає окремої "події релізу". investing.com
перевірено й відкинуто (403, бот-захист). `monitoring` лише тригерить
ЗБІР даних; сигнал у майбутню analysis/ (Фаза 2, "оновити прогнози")
поки нікуди не веде — споживача ще нема, чесно позначено, не
приховано.

**Блокер оркестрації закрито (2026-09-27):** `orchestration/`
(APScheduler, сервіс `scheduler` у docker-compose) сам запускає
`check_releases.py`/`refresh_calendar.py` та решту конвеєра за
розкладом (`orchestration/schedule.py`, Europe/Kyiv) — деталі й
обґрунтування рушія, docs/decisions.md 2026-09-27. Live-прогін самого
`check_releases.py` (реальний забір даних) усе ще чекає на 30 вересня
— 2 жовтня (найближчий pending — pce_price_index/real_gdp, 2026-09-30
12:30 UTC; live-перевірено 2026-09-27, `release_log`) — не блокер,
лише час, але тепер це станеться само, без ручного запуску.

## Що не зроблено (по фазах PLAN.md)

- **Фаза 1:** повністю готова, включно з оркестрацією (`orchestration/`,
  2026-09-27) — увесь конвеєр тепер запускається сам за розкладом, без
  ручного втручання. news/ — усі потоки й обидва механізми збору
  (GDELT + RSS) живо підтверджено вище. Крипта (BTC/ETH/SOL) —
  Binance + CoinGecko, живо підтверджено. Календар релізів —
  `monitoring/` (вище), seed підтверджено живо, реальний забір даних —
  чекає на 30 вересня (не блокер, лише час). Форекс/товари поза
  watchlist-парами — закрито як окрема задача (рішення користувача,
  2026-09-26): розширення переліку користувач вносить сам через файл
  вибраних активів, нові адаптери на це не пишемо.
- **Фаза 2:** ринкові очікування, порівняння факт/очікування — не
  почато. LLM-аналіз новин — робочий зріз є (усі 3 потоки, вище),
  детерміноване порівняння факт/очікування — окреме, ще не почате
  (screening-трек вище — паралельна робота, інший вид аналізу)
- **Фаза 3:** детекція виходу нових даних (`monitoring/`) — готова й
  тепер запускається сама (`orchestration/`, кожні 15 хв), live-прогін
  реального забору даних не підтверджено (чекає на 30 вересня —
  2 жовтня). Тригер сигналу в analysis/ (споживача ще нема),
  автооновлення прогнозів, сповіщення про відхилення — не почато
- **Фаза 4:** формат регулярного звіту (email/dashboard/файл) — не
  вирішено; список активів поза акціями — крипто збір даних готовий,
  форекс/товари поза watchlist — на розсуд користувача (файл вибраних
  активів), скринінгу (аналог Tier A/B/C) немає ні для одного з них.
  **На майбутнє (фінальна стадія):** редагування списку обраних активів
  через Telegram — зафіксовано користувачем 2026-09-26, не реалізовано.

## Відкриті другорядні питання (не блокуючі)

- `shares_outstanding` відсутній для ~110/501 компаній S&P 500 (SEC
  повертає порожній `units.shares` — ймовірно компанії з кількома
  класами акцій); можливий fallback-тег `CommonStockSharesOutstanding`
  без `dei` — не зроблено, не блокує (365/491 — робочий результат)
`docs/watchlist.md` — усі відкриті питання (крипто-монети, нафта,
"пріоритет 2") закриті 2026-09-25 (docs/decisions.md).

## Наступний змістовний крок

**Крипто+срібло і `monitoring/` (15 показників, US+EUR+JPY) —
реалізовано й живо підтверджено (2026-09-26/27).** Деталі — вище й
`docs/decisions.md`.

**Оркестрація (2026-09-27) — реалізовано.** `orchestration/`
(APScheduler, сервіс `scheduler`) сам запускає весь конвеєр за
розкладом (`orchestration/schedule.py`) — блокер №1 закритий, деталі —
docs/decisions.md.

**Фаза 2 (аналіз/прогноз) — перша ланка ланцюжка реалізована
(2026-09-27).** Домовлений ланцюжок (2026-09-27, дизайн-сесія):
реліз → контекст → **детермінований розрахунок** → LLM-синтез
(Anthropic) → причинний висновок + "що дивитись далі" →
замикання циклу через `monitoring/`. Реалізовано саме
**детермінований розрахунок** — `analysis/expectations/`:
- `parse_expected.py` — парсинг ForexFactory-тексту прогнозу
  ("0.6%"/"-258B"/"615K" → число).
- `comparison_methods.py` — 5 методів приведення факту й прогнозу до
  спільних одиниць (`level_direct`/`mom_pct`/`diff_level`/
  `qoq_pct_annualized`/`yoy_pct`) для всіх 15 показників календаря
  (докладніше `docs/decisions.md`).
- `compare_releases.py` — забирає `release_log` рядки зі статусом
  `detected` (`check_releases.py`), рахує сюрприз, зберігає в новій
  таблиці `expectation_comparisons`, переводить статус у `processed`
  (раніше застрягав на `detected` — перехід навмисно був за analysis/).
- `reporting/expectations_notify.py` — Telegram-сповіщення про
  сюрприз (тільки impact_level high/medium).
- Оркестрація: `compare_expectations`/`notify_expectations`, +5/+10 хв
  після `check_releases` у тому самому 15-хв вікні.
- Тести на фікстурах/monkeypatch (без реальної БД) — `analysis/tests/
  test_parse_expected.py`, `test_comparison_methods.py`,
  `test_compare_releases.py`.

**Не зроблено (наступний крок Фази 2):** live-прогін на справжньому
релізі (найближчі — 30 вересня/2 жовтня, вище); LLM-синтез
(Anthropic) поверх уже готового сюрпризу — досі не почато; "контекст"
(разовий знімок календаря по інших країнах/PMI без збереження) — досі
не почато, обговорювався, не написаний.

(Форекс/товари поза watchlist-парами — закрито як окрема задача,
рішення користувача 2026-09-26: користувач розширює список сам через
файл вибраних активів.)
