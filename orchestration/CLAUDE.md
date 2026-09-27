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

## Контракт провалу
Джоба вважається провальною, якщо subprocess завершився з ненульовим
exit-кодом, впав у timeout, або Python-функція кинула виняток — тоді
Telegram-алерт (`alerts.py`). Успіх — тільки запис у `logs/`, без
Telegram-шуму (щоб не заспамити чат щогодини). Джоби самі відповідають
за власну ідемпотентність (напр. `monitoring/release_log.py` —
'pending' лишається 'pending', якщо дані ще не з'явились) —
orchestration нічого не повторює й не запам'ятовує сама.

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
