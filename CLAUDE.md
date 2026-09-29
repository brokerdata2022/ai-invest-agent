# AI Investment Research Agent

## Що це
Агент, який автоматично збирає макроекономічні дані, звіти компаній, новини та
офіційну статистику, аналізує їх відносно ринкових очікувань, формує прогнози,
відстежує вихід нових даних (і оновлює аналіз після кожного релізу), та на
основі всього цього генерує короткі звіти й списки цікавих активів для
інвестицій/спекуляцій.


## Стек
- Мова бекенду: **Python**
- База даних: **PostgreSQL + TimescaleDB** (одна база для часових рядів
  і реляційних даних одночасно — не тримаємо дві окремі СУБД)
- працюємо сесійно, з підключенням git, через vscode з необхідними розширеннями, локально тестуємо та запускаємо через Docker
- Оркестрація фонових задач (збір даних за розкладом): **APScheduler**,
  окремий сервіс `scheduler` у docker-compose (не Celery/Prefect/Airflow —
  зайва інфраструктура для незалежних періодичних джоб без черг/DAG;
  рішення й обґрунтування — docs/decisions.md, 2026-09-27). Розклад —
  `orchestration/schedule.py`, часовий пояс — Europe/Kyiv.
- LLM-виклики (аналіз новин, генерація звітів): через DeepSeek API уся робота,  Anthropic API фінальний висновок аналіз

## Джерела даних (пріоритет: безкоштовні + першоджерела)
Повний список і причини вибору кожного — у docs/decisions.md.
Коротко (✅ = адаптер уже реалізовано й підтверджено живо):
- **Макро-дані:** ✅ FRED (США), ✅ ECB Data Portal (єврозона), ✅ BOJ +
  e-Stat (Японія). Китай/Індія свідомо не розглядаються (рішення
  користувача, docs/decisions.md 2026-08-30)
- **Календар релізів з рівнем впливу:** ✅ 15 показників — US (FRED
  офіційна ДАТА, 10 показників) + єврозона/Японія (ECB/BOJ/e-Stat дані,
  ForexFactory-фід — єдине джерело дати й часу, 5 показників: EUR/USD
  і USD/JPY у watchlist потребують даних по обох валютах, не тільки
  долару). ForexFactory-фід (неофіційний, живо перевірений, покриває й
  EUR/JPY) дає точний ЧАС/impact/forecast; для FRED-показників — з
  fallback (типовий час 8:30 ET + власний high/medium/low), для
  єврозони/Японії fallback немає (немає іншого джерела дати).
  Двофазно: `monitoring/refresh_calendar.py` (тижнево, заводить
  наперед) → `monitoring/check_releases.py` (часто, активно тригерить
  збір після настання часу+буфера, реєстр адаптерів —
  `monitoring/metric_sources.py`)
- **Акції:** ✅ SEC EDGAR (звіти/фундаментал, першоджерело,
  companies/sec_edgar_adapter.py) + ✅ Twelve Data (ціни/обсяг,
  неофіційне джерело — quotes/twelvedata_adapter.py; Stooq і Alpaca
  розглядались і відкинуті, деталі — docs/decisions.md 2026-09-14/20)
- **Крипта (спот):** ✅ Binance public API (ціна/обсяг, першоджерело
  біржі, crypto/binance_adapter.py) + ✅ CoinGecko (market cap,
  агрегатор, crypto/coingecko_adapter.py) — BTC/ETH/SOL, docs/watchlist.md
- **Крипта (ф'ючерси, скринінг лонг/шорт/спостереження):** ✅ Binance +
  Bybit + OKX Futures (crypto/binance_futures_adapter.py,
  crypto/bybit_futures_adapter.py, crypto/okx_futures_adapter.py) —
  ширший ринок за watchlist (не лише BTC/ETH/SOL), окремий трек від
  скринінгу акцій, деталі — `analysis/crypto_screening/`, PLAN.md
  Фаза 4
- **Форекс/Товари поза watchlist-парами:** закрито як окрема задача
  (рішення користувача, 2026-09-26) — розширення переліку валютних
  пар/товарів понад watchlist (docs/watchlist.md) користувач вносить
  сам через файл вибраних активів, не через нові адаптери на запит
- **Новини/звіти:** ✅ GDELT (2 потоки: watchlist/general,
  news/gdelt_adapter.py) + ✅ 9 RSS-фідів (Fed/ECB/BOJ + 6 широких
  редакційних — BBC/Al Jazeera/Guardian/NPR/Sky News/DW,
  news/rss_adapter.py) для потоку geopolitical (замінив курований
  GDELT-запит 2026-09-27 — губив непередбачені події, docs/decisions.md);
  активи для відстеження — docs/watchlist.md, **для чого нам новини й що
  для цього ще потрібно — docs/news-purpose.md** (5 цілей, поставлено
  2026-09-26)

## Як запустити локально
```bash
cp .env.example .env         # заповнити FRED_API_KEY, SEC_EDGAR_USER_AGENT,
                              # TWELVEDATA_API_KEY, DB_*, TELEGRAM_*
docker compose up -d --build # піднімає TimescaleDB + контейнер застосунку
                              # (усі Python-залежності вже встановлені в образі,
                              # venv на хості не потрібен)

docker compose exec app python data-ingestion/apply_schema.py   # (пере)застосувати схему
docker compose exec app python data-ingestion/run_collect.py --metric cpi
docker compose exec app python reporting/telegram_notify.py --metric cpi
docker compose exec app pytest
```
Після зміни requirements.txt перезібрати образ: `docker compose up -d --build`.

⚠️ Це лише дим-тест на одному показнику. Свіжа БД після цього порожня —
скринінг/синтез/дайджест нічого не покажуть, доки не пройдено
обов'язковий bootstrap: `README.md`, "Перший запуск з чистими даними"
(`scripts/bootstrap_1_backfill.sh` + `scripts/bootstrap_2_pipeline.sh`).

## Структура репозиторію
```
data-ingestion/   — усе, що стосується ЗБОРУ сирих даних (без аналізу)
  macro/            — FRED, ECB, BOJ, e-Stat адаптери
  companies/        — SEC EDGAR (фундаментал акцій)
  quotes/           — Twelve Data (ціни/обсяг акцій)
  common/           — спільний інтерфейс адаптера, підключення до БД
analysis/         — обробка зібраних даних: прогнози, порівняння з очікуваннями
  llm_common.py     — спільна LLM-проводка: провайдер, розбір відповіді,
                      аудит-лог виклику (новий LLM-скрипт бере це звідси)
  forecasting/      — трендові моделі + backtest проти naive
  expectations/     — факт vs ринкове очікування + LLM-синтез сюрпризу
  news_analysis/    — класифікація новин, агрегація, LLM-синтези
  screening/        — скринінг акцій S&P 500 (Tier A/B/C + composite score)
monitoring/       — відстеження календаря релізів, тригери на нові дані
reporting/         — генерація коротких звітів і списків активів
                    (_common.py — спільний бойлерплейт notify-скриптів)
orchestration/    — автозапуск усього конвеєра за розкладом (APScheduler);
                    schedule.py — єдиний файл для зміни періодичності
db/               — db/schema.sql — схема БД (raw_observations, sources, release_log)
scripts/          — bootstrap_1_backfill.sh / bootstrap_2_pipeline.sh
                    (єдиний правильний порядок розгортання з нуля)
logs/             — раннтайм-вивід джоб (у .gitignore, прибирається
                    джобою prune_logs через 14 днів)
docs/             — архітектурні рішення, дизайн-документи
  docs/archive/     — повні (нестиснуті) версії журналів рішень/сесій
```
Кожна з цих папок має власний CLAUDE.md з деталями саме цього домену.
Дивись docs/architecture.md для повної картини потоку даних.

## Критичні правила (не порушувати)
1. **Розділення "збір даних" і "аналіз" — завжди окремі шари.**
   data-ingestion ніколи не повинен містити логіку прогнозування чи
   інтерпретації. Він лише дістає й нормалізує сирі дані. Це дозволяє
   тестувати й змінювати аналітику, не чіпаючи джерела даних, і навпаки.
2. **Кожне джерело даних — окремий адаптер з однаковим інтерфейсом**
   (див. data-ingestion/CLAUDE.md). Ніколи не пишемо кастомний парсинг
   прямо в коді аналізу.
3. **Жодних API-ключів/секретів у коді чи в CLAUDE.md.** Тільки .env,
   .env додано в .gitignore з першого коміту.
4. **Кожен новий тип прогнозу/показника — спочатку записується в
   docs/decisions.md** (одне речення: що, чому, які альтернативи
   відкинули). Це рятує від "чому ми взагалі так зробили" через 3 місяці.
5. **LLM-виклики для аналізу новин/звітів завжди логуються** (промпт +
   відповідь + timestamp + джерело) — потрібно для перевірки, чому агент
   зробив той чи інший висновок постфактум.
6. **Ніколи не видаляти сирі зібрані дані**, навіть якщо джерело
   змінилось/зникло — тільки архівувати. Історичні дані — це те, на чому
   тримається якість майбутніх прогнозів.
   **Виняток — `raw_news` (2026-09-28, рішення користувача):**
   обґрунтування правила (якість МАЙБУТНІХ ПРОГНОЗІВ) стосується
   макропоказників, не новинних статей — стаття тижневої давності не
   покращує прогноз. Збір обмежено 24г (`common/news_db.py:
   MAX_ARTICLE_AGE_HOURS`), зберігання — 48г (`RETENTION_HOURS`,
   джоба `prune_raw_news`). `raw_observations` (макро/акції/крипта)
   це правило НЕ торкається — і далі append-only назавжди.

## Команди
```bash
# Застосувати/оновити схему БД
docker compose exec app python data-ingestion/apply_schema.py

# Зібрати один макропоказник (metric_id — список у docs/metrics-catalog.md)
docker compose exec app python data-ingestion/run_collect.py --metric cpi

# Зібрати дані по тикеру (котирування чи фундаментал)
docker compose exec app python data-ingestion/run_collect.py --source twelvedata --ticker AAPL
docker compose exec app python data-ingestion/run_collect.py --source sec_edgar --ticker AAPL

# Масовий збір по всьому S&P 500 (companies/ — SEC EDGAR фундаментал)
docker compose exec app python data-ingestion/collect_companies_universe.py

# Скринінг акцій — воронка Tier A → B → C → ранжування
docker compose exec app python analysis/screening/tier_a.py
docker compose exec app python analysis/screening/tier_b.py
docker compose exec app python analysis/screening/tier_c.py
docker compose exec app python analysis/screening/composite_score.py --top 10

# Надіслати останнє зібране значення показника в Telegram
docker compose exec app python reporting/telegram_notify.py --metric cpi

# Зібрати новини (GDELT) для потоку watchlist → raw_news
docker compose exec app python data-ingestion/run_collect_news.py --stream watchlist

# Зібрати новини (GDELT) для тикерів, що пройшли скринінг (Tier C) →
# теж raw_news/watchlist, окремий query від команди вище
docker compose exec app python analysis/news_analysis/collect_stock_news.py

# Зібрати загальний ринковий потік (GDELT) → raw_news/general
docker compose exec app python data-ingestion/run_collect_news.py --stream general

# Зібрати геополітичний потік → raw_news/geopolitical. НЕ через GDELT
# (--stream geopolitical більше не існує в run_collect_news.py, видалено
# 2026-09-27 — курований GDELT-запит губив непередбачені події) — 9
# RSS-фідів (Fed/ECB/BOJ + 6 редакційних: BBC/Al Jazeera/Guardian/NPR/
# Sky News/DW):
docker compose exec app python data-ingestion/run_collect_rss.py

# DeepSeek-аналіз зібраних новин (raw_news → news_analysis, потребує
# DEEPSEEK_API_KEY)
docker compose exec app python analysis/news_analysis/run_news_analysis.py --stream watchlist

# Надіслати в Telegram релевантні висновки з news_analysis
docker compose exec app python reporting/news_notify.py --stream watchlist --limit 5

# Показати агреговані новини (кластери дублікатів + зведення по активу)
docker compose exec app python analysis/news_analysis/show_aggregated_news.py

# Крипто-скринінг ф'ючерсів (лонг/шорт/спостереження, Binance+Bybit+OKX)
docker compose exec app python analysis/crypto_screening/run_screening.py
docker compose exec app python analysis/crypto_screening/monitor_candidates.py

# Прогнати всі тести (data-ingestion + reporting + analysis)
docker compose exec app pytest -q

# Оркестрація (orchestration/) — усе вище запускається САМО за розкладом
# (сервіс scheduler, docker compose up -d, restart: unless-stopped)
docker compose logs -f scheduler

# Ручний запуск однієї джоби негайно (для тестів), той самий код/образ
docker compose exec app python orchestration/run_job.py check_releases
docker compose exec app python orchestration/run_job.py --list
```

## Статус проєкту
- **docs/status.md** — що працює живо (з цифрами), що не зроблено,
  наступний крок.
- **docs/production-readiness.md** — що потрібно доробити до продакшену,
  пріоритезовано (P0/P1/P2) + чекліст розгортання на VPS.
- **PLAN.md** — фази й чекбокси. **docs/decisions.md** — журнал рішень.

Головна незакрита задача (2026-09-27): **прогнозування** — доведене до
робочого стану лише на 1 показнику з 15 і назовні не виходить, хоча це
перше, що обіцяє опис проєкту вище.
