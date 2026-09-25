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
- Оркестрація фонових задач (збір даних за розкладом): TBD (Celery/Prefect/
  Airflow — залежить від масштабу). Фаза 1 (збір даних) практично
  завершена (докладніше — docs/status.md) — час вирішити це перед
  Фазою 3 (моніторинг/тригери), яка на це спирається.
- LLM-виклики (аналіз новин, генерація звітів): через DeepSeek API уся робота,  Anthropic API фінальний висновок аналіз

## Джерела даних (пріоритет: безкоштовні + першоджерела)
Повний список і причини вибору кожного — у docs/decisions.md.
Коротко (✅ = адаптер уже реалізовано й підтверджено живо):
- **Макро-дані:** ✅ FRED (США), ✅ ECB Data Portal (єврозона), ✅ BOJ +
  e-Stat (Японія). Китай/Індія свідомо не розглядаються (рішення
  користувача, docs/decisions.md 2026-08-30)
- **Календар релізів з рівнем впливу:** офіційні графіки публікацій
  (BLS/BEA/Fed) + власний статичний список "що вважається
  high/medium impact" (немає офіційного API з готовою розміткою впливу)
  — ще не побудовано
- **Акції:** ✅ SEC EDGAR (звіти/фундаментал, першоджерело,
  companies/sec_edgar_adapter.py) + ✅ Twelve Data (ціни/обсяг,
  неофіційне джерело — quotes/twelvedata_adapter.py; Stooq і Alpaca
  розглядались і відкинуті, деталі — docs/decisions.md 2026-09-14/20)
- **Крипта:** CoinGecko (агрегатор) + Binance public API (першоджерело
  біржових даних) — заплановано, адаптер ще не написаний
- **Форекс:** ECB reference rates (першоджерело, щоденні) — заплановано
- **Товари:** заплановано (джерело ще не обрано)
- **Новини/звіти:** GDELT + офіційні RSS центробанків і статслужб —
  заплановано; активи для відстеження визначені в docs/watchlist.md

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

## Структура репозиторію
```
data-ingestion/   — усе, що стосується ЗБОРУ сирих даних (без аналізу)
  macro/            — FRED, ECB, BOJ, e-Stat адаптери
  companies/        — SEC EDGAR (фундаментал акцій)
  quotes/           — Twelve Data (ціни/обсяг акцій)
  common/           — спільний інтерфейс адаптера, підключення до БД
analysis/         — обробка зібраних даних: прогнози, порівняння з очікуваннями
  screening/        — скринінг акцій S&P 500 (Tier A/B/C + composite score)
monitoring/       — відстеження календаря релізів, тригери на нові дані
reporting/         — генерація коротких звітів і списків активів
db/               — db/schema.sql — схема БД (raw_observations, sources, release_log)
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

# DeepSeek-аналіз зібраних новин (raw_news → news_analysis, потребує
# DEEPSEEK_API_KEY)
docker compose exec app python analysis/news_analysis/run_news_analysis.py --stream watchlist

# Надіслати в Telegram релевантні висновки з news_analysis
docker compose exec app python reporting/news_notify.py --stream watchlist --limit 5

# Прогнати всі тести (data-ingestion + reporting + analysis)
docker compose exec app pytest -q
```

## Статус проєкту
docs/status.md — що працює живо (з цифрами), що не зроблено, наступний
крок. PLAN.md — фази й чекбокси. docs/decisions.md — журнал рішень.
