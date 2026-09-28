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
3. **`docker compose restart scheduler`**, якщо контейнер уже працює —
   `main.py` реєструє джоби (APScheduler) ОДИН РАЗ при старті процесу.
   Зміна коду самого скрипта джоби підхоплюється сама (bind mount,
   subprocess перечитує файл щоразу), а от нова джоба чи новий час у
   `schedule.py`/`jobs.py` — ні, доки процес не перезапущено (живий
   баг, docs/decisions.md 2026-09-27: `notify_expectations` виконав
   уже новий код за старим триггером, до того як `apply_schema.py`
   встиг створити потрібну таблицю).

## Контракт провалу
Джоба вважається провальною, якщо subprocess завершився з ненульовим
exit-кодом, впав у timeout, або Python-функція кинула виняток — тоді
Telegram-алерт (`alerts.py`). Успіх — тільки запис у `logs/`, без
Telegram-шуму (щоб не заспамити чат щогодини). Джоби самі відповідають
за власну ідемпотентність (напр. `monitoring/release_log.py` —
'pending' лишається 'pending', якщо дані ще не з'явились) —
orchestration нічого не повторює й не запам'ятовує сама.

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

## Команди
```bash
# сервіс scheduler запускається сам (docker compose up -d, restart: unless-stopped)
docker compose logs -f scheduler

# ручний запуск однієї джоби негайно (для тестів) — той самий образ/код
docker compose exec app python orchestration/run_job.py check_releases
docker compose exec app python orchestration/run_job.py --list

# тести
docker compose exec app pytest orchestration/tests
```
