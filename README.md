# AI Investment Research Agent

Агент, який автоматично збирає макроекономічні дані, звіти компаній,
новини й офіційну статистику, аналізує їх відносно ринкових очікувань
і формує короткі звіти. Детальний опис задуму — `CLAUDE.md`, поточний
статус і план — `PLAN.md`.

## Стек

- Python (бекенд)
- PostgreSQL + TimescaleDB (єдина база — часові ряди й реляційні дані разом)
- Docker / Docker Compose (усі залежності в образі, venv на хості не потрібен)

## Вимоги

- Docker + Docker Compose ([docs.docker.com/get-docker](https://docs.docker.com/get-docker/))
- Git
- Безкоштовний FRED API-ключ: <https://fred.stlouisfed.org/docs/api/api_key.html>
  (потрібен тільки для макро-даних США; для єврозони, ECB Data Portal,
  ключ не потрібен)
- Telegram-бот (опційно, тільки для сповіщень): створити через
  [@BotFather](https://t.me/BotFather), дізнатись свій chat_id через
  [@userinfobot](https://t.me/userinfobot)

## Запуск на новому ПК/сервері з нуля

```bash
# 1. Клонувати репозиторій
git clone https://github.com/brokerdata2022/ai-invest-agent.git
cd ai-invest-agent

# 2. Налаштувати змінні середовища
cp .env.example .env
# Відкрити .env і заповнити:
#   FRED_API_KEY      — з fred.stlouisfed.org
#   DB_PASSWORD        — будь-який пароль для локальної БД (обов'язково,
#                         контейнер не підніметься без нього)
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — опційно, для сповіщень

# 3. Підняти TimescaleDB + контейнер застосунку
docker compose up -d --build

# 4. Застосувати схему БД (створює таблиці raw_observations, sources, release_log)
docker compose exec app python data-ingestion/apply_schema.py

# 5. Перевірити, що все працює
docker compose exec app pytest
```

Якщо всі тести пройшли — середовище готове.

## Щоденне використання

```bash
# Зібрати конкретний показник (список усіх metric_id — docs/metrics-catalog.md)
docker compose exec app python data-ingestion/run_collect.py --metric cpi
docker compose exec app python data-ingestion/run_collect.py --metric eurozone_hicp

# Надіслати останнє зібране значення в Telegram
docker compose exec app python reporting/telegram_notify.py --metric cpi

# Прогнати тести
docker compose exec app pytest
```

Код монтується в контейнер як volume — зміни у файлах (напр. через
VSCode) видно всередині контейнера одразу, без перезбірки. Ребілд
(`docker compose up -d --build`) потрібен лише коли змінюється
`requirements.txt` або `Dockerfile`.

## Перевірка даних у БД напряму

```bash
docker compose exec db psql -U ${DB_USER:-invest_agent} -d ${DB_NAME:-invest_agent} -c \
  "SELECT source, metric_id, value, observed_at, revision FROM raw_observations ORDER BY observed_at DESC LIMIT 20;"

# Скільки записів по кожному джерелу
docker compose exec db psql -U ${DB_USER:-invest_agent} -d ${DB_NAME:-invest_agent} -c \
  "SELECT source, count(*), min(observed_at), max(observed_at) FROM raw_observations GROUP BY source;"
```

## Повне перезбирання (якщо щось пішло не так)

Якщо контейнери/БД поводяться дивно (застарілий стан, конфлікти
volume після зміни docker-compose.yml тощо) — безпечний спосіб почати
начисто. **Увага: `-v` видаляє volume бази даних, тобто всі зібрані
дані.** Якщо дані важливі — спершу зробіть дамп:
```bash
docker compose exec db pg_dump -U ${DB_USER:-invest_agent} ${DB_NAME:-invest_agent} > backup.sql
```

Повне перезбирання:
```bash
docker compose down -v          # зупинити й видалити контейнери + volume БД
docker compose up -d --build    # підняти заново з чистого стану
docker compose exec app python data-ingestion/apply_schema.py
docker compose exec app pytest
```

## Структура репозиторію

```
data-ingestion/   — збір сирих даних (адаптери джерел: FRED, ECB, ...)
analysis/         — обробка зібраних даних: прогнози, порівняння з очікуваннями (Фаза 2)
monitoring/       — відстеження календаря релізів (Фаза 3)
reporting/        — генерація звітів і сповіщень
docs/             — архітектура, журнал рішень (decisions.md), каталог показників
db/               — schema.sql (структура БД)
```

Кожна тека має власний `CLAUDE.md` з деталями. Повна картина потоку
даних — `docs/architecture.md`. Поточний статус і що далі — `PLAN.md`.

## Усунення проблем

**`FRED_API_KEY не задано`** — перевірте, що `.env` існує (не тільки
`.env.example`) і ключ реально вписаний.

**`ForeignKeyViolation: Key (source)=(...) is not present in table "sources"`**
— джерело не зареєстроване в seed-даних `db/schema.sql`. Якщо це не
ваш кастомний адаптер — перевірте, що ви на актуальній версії коду, і
перезастосуйте схему: `docker compose exec app python data-ingestion/apply_schema.py`.

**Дані виглядають застарілими / не оновлюються** — не всі показники
винні в коді: зовнішні джерела (особливо ECB) іноді закривають старі
датасети й переносять на нові без помилки в запиті (детальніше —
`docs/decisions.md`, запис про міграцію ICP→HICP). Перевірте офіційну
дату останнього релізу показника і порівняйте з тим, що повернув
запит.
