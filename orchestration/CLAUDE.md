# orchestration — правила модуля

## Відповідальність
Тільки ВИКЛИК уже написаних скриптів/функцій за розкладом. Жодної
бізнес-логіки — якщо виникає спокуса щось порахувати чи
відфільтрувати тут, це belongs у data-ingestion/monitoring/analysis/
reporting, не сюди (той самий принцип, critical rule 1 кореневого
CLAUDE.md).

## Розділення "коли" і "що"
- `schedule.py` — ТІЛЬКИ розклад (назва джоби → коли + чому). Єдиний
  файл, який редагується, щоб змінити періодичність чи час.
- `jobs.py` — ТІЛЬКИ реєстр "що виконати" для кожної назви з
  `schedule.py` (subprocess-команда чи Python-функція).
- `runner.py`/`main.py`/`alerts.py`/`run_job.py` — виконання й
  сповіщення, не чіпати заради зміни розкладу чи додавання джоби.

## Додавання нової джоби
1. Додати запис у `jobs.py:JOBS` (що виконати).
2. Додати запис у `schedule.py:SCHEDULE` з тим самим ключем (`trigger`
   + `why`) — `tests/test_schedule.py` впаде, якщо ключі розійдуться.
3. Додати опис у `command_descriptions.py:JOB_DESCRIPTIONS` (та сама
   назва ключа) — `tests/test_command_descriptions.py` впаде інакше;
   запустити `register_telegram_commands.py`, щоб нова команда
   з'явилась у "/"-меню Telegram.
4. **`docker compose restart scheduler`**, якщо контейнер уже працює —
   `main.py` реєструє джоби (APScheduler) ОДИН РАЗ при старті процесу.
   Зміна коду самого скрипта джоби підхоплюється сама (bind mount,
   subprocess перечитує файл щоразу), а от нова джоба чи новий час у
   `schedule.py`/`jobs.py` — ні, доки процес не перезапущено (живий
   баг, docs/decisions.md 2026-09-27: `notify_expectations` виконав
   уже новий код за старим триггером, до того як `apply_schema.py`
   встиг створити потрібну таблицю).

## Контракт провалу й повторних спроб
Джоба вважається провальною, якщо subprocess завершився з ненульовим
exit-кодом, впав у timeout, або Python-функція кинула виняток. Перед
тим, як визнати провал остаточним, `runner.py` САМ повторює джобу
(`DEFAULT_RETRIES = 1` — одна повторна спроба, `RETRY_BACKOFF_SECONDS`
паузи між ними; перекривається на джобу через `jobs.py:JOBS[...]["retries"]`,
`0` — для важких годинних прогонів типу `quotes_universe_refresh`, де
негайний повторний прогін лише вдруге вперся б у те саме джерело/ліміт
без паузи). Рішення користувача 2026-09-28: "джоби не мають
провалюватися, бо ми не отримуємо останні дані" — транзієнтний
мережевий збій найчастіше просто зникає на повторній спробі, а
append-only дедуп (rule 6 CLAUDE.md) робить повтор безпечним для будь-
якої джоби проєкту.

Telegram-алерт (`alerts.py`) — лише ОДИН раз, після того як вичерпано
всі спроби (не за кожну окрему невдалу спробу). Успіх (одразу чи на
ретраї) — тільки запис у `logs/`, без Telegram-шуму. Джоби самі
відповідають за власну ідемпотентність (напр. `monitoring/release_log.py`
— 'pending' лишається 'pending', якщо дані ще не з'явились) —
orchestration нічого не запам'ятовує МІЖ окремими запусками сама
(ретрай — виняток, він живе всередині одного виклику `run_job()`).

## Логи джоб
Кожен запуск пише окремий файл `logs/<джоба>_<UTC-timestamp>.log`
(`runner.py`). Це ~150 файлів на добу, тому є джоба `prune_logs`
(щодня 4:30, `jobs.py:LOG_RETENTION_DAYS = 14`) — без неї диск сервера
росте нескінченно. `logs/` у `.gitignore` і не є джерелом істини
(критичне правило №6 про сирі ДАНІ в БД, не про раннтайм-вивід).

## Часовий пояс
Один параметр — `schedule.py:TIMEZONE` (за замовчуванням Europe/Kyiv,
перекривається `SCHEDULER_TIMEZONE` в `.env`). Не хардкодити часовий
пояс деінде.

## Telegram-команди людською мовою (ручний запуск джоб)
`telegram_commands.py` (щохвилини, той самий ритм, що `check_releases`)
опитує Telegram `getUpdates` і запускає відповідну джобу ІМЕНЕМ
замість `docker compose exec app python run_job.py <назва>`.
Авторизація — лише `TELEGRAM_CHAT_ID` з `.env`. **Важливо:** запуск
джоби — НЕБЛОКУЮЧИЙ subprocess `python run_job.py <назва>` (не прямий
виклик `runner.run_job()` у своєму процесі) — цей дочірній процес
переживає сам `telegram_commands.py` (той встигає завершитись за
секунди) і несе ВЕСЬ звичний контракт провалу й ретраїв (`runner.py`)
сам, незалежно.

**Меню звужено до "інформаційних" джоб (2026-10-03, рішення
користувача після живого тесту):** через Telegram виконуються ЛИШЕ
джоби з `command_descriptions.py:INFO_JOB_NAMES` (12 з 44 — ті, що
САМІ надсилають інформацію: `notify_*`/`daily_digest`), не будь-яка
з `JOBS` — технічна джоба (збір даних/LLM-аналіз без доставки),
набрана вручну, дає "Невідома команда". Решта 32 джоб і далі
виконуються за розкладом автоматично — без змін, звужено лише
РУЧНИЙ запуск через Telegram; ручний запуск технічної джоби лишається
через `docker compose exec app python run_job.py <назва>`.

Назва+опис кожної команди — `command_descriptions.py:JOB_DESCRIPTIONS`
(тест звіряє паритет з `JOBS`) + `SPECIAL_COMMAND_DESCRIPTIONS`
(watchlist-команди, не джоби); `register_telegram_commands.py` —
ручний разовий скрипт, реєструє їх у "/"-меню Telegram
(`setMyCommands`), перезапустити після додавання нової
джоби/watchlist-команди чи зміни `INFO_JOB_NAMES`.

## Команди
```bash
# сервіс scheduler запускається сам (docker compose up -d, restart: unless-stopped)
docker compose logs -f scheduler

# разово (і після кожної нової джоби) — зареєструвати "/"-меню команд у Telegram
docker compose exec app python orchestration/register_telegram_commands.py

# ручний запуск однієї джоби негайно (для тестів) — той самий образ/код
docker compose exec app python orchestration/run_job.py check_releases
docker compose exec app python orchestration/run_job.py --list

# тести
docker compose exec app pytest orchestration/tests
```
