"""
Спільний бойлерплейт reporting-скриптів: доступ до БД (sys.path), читання
Telegram-креденшелів, словники емодзі напрямку, читання рядків як dict.

Жодного форматування конкретного звіту тут — воно лишається в кожному
скрипті (reporting/CLAUDE.md: тільки представлення). Винесено те, що
було скопійоване в 6-7 файлах слово в слово:

- `sys.path`-вставка для `common.db` (data-ingestion — не валідне ім'я
  Python-пакета через дефіс, тому додаємо вміст теки напряму). Робиться
  при ІМПОРТІ цього модуля, тож у скрипті рядок `from _common import ...`
  має стояти ПЕРЕД `from common.db import ...`.
- `resolve_telegram_credentials()` — той самий early-exit "токен/чат не
  задані" з main() кожного notify-скрипта.
- `DIRECTION_EMOJI` / `MARKET_DIRECTION_LABEL` — були в 3 і 2 файлах
  відповідно.
- `fetch_dicts()` — `cur.description`-в-dict, був продубльований у
  кожному fetch_*() (raw cursor замість RealDictCursor — щоб не тягнути
  psycopg2.extras у кожен скрипт).
- `mark_notified()` — спільний дедуп-паттерн "позначити рядки як вже
  надіслані" (2026-09-28, критичний фікс — живий фідбек користувача:
  `news_notify.py` слав ІДЕНТИЧНІ ранкове й вечірнє повідомлення, коли
  за день з'являлось мало нового). Той самий принцип, що вже був у
  `expectations_notify.py`/`expectations._db.mark_notified` — тут
  узагальнено на решту 4 notify-скриптів, СВОЇМ кодом (не імпортом з
  analysis/, contained independence нижче).
"""

import logging
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-ingestion")
)

logger = logging.getLogger(__name__)

# Напрямок сигналу з analysis/ → емодзі. Той самий набір значень, що
# analysis/llm_common.py:DIRECTIONS (без прямого імпорту — reporting/ і
# analysis/ лишаються незалежними деплойментами, reporting/CLAUDE.md).
DIRECTION_EMOJI = {"up": "🟢", "down": "🔴", "neutral": "⚪", "unclear": "❓"}

# Той самий напрямок, але для синтезу стану РИНКУ (market_synthesis):
# up/down тут означають risk-on/risk-off, тому окремий підпис.
MARKET_DIRECTION_LABEL = {
    "up": "🟢 risk-on",
    "down": "🔴 risk-off",
    "neutral": "⚪ збалансовано",
    "unclear": "❓ немає чіткого сигналу",
}


def resolve_telegram_credentials() -> tuple[str, str]:
    """(token, chat_id) з .env або вихід із кодом 1 і зрозумілим
    повідомленням — сповіщення без креденшелів безсенсове, це не та
    помилка, яку варто ковтати."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID не задані в .env (див. .env.example)"
        )
        sys.exit(1)
    return token, chat_id


def fetch_dicts(conn, query: str, params: tuple = ()) -> list[dict]:
    """Рядки запиту як list[dict] (ключі — імена колонок)."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [d[0] for d in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def fetch_one_dict(conn, query: str, params: tuple = ()):
    """Перший рядок як dict, або None якщо запит нічого не повернув."""
    rows = fetch_dicts(conn, query, params)
    return rows[0] if rows else None


# Білий список таблиць для mark_notified() — psycopg2 не вміє
# параметризувати SQL-ідентифікатори (лише значення), тому ім'я
# таблиці підставляється в SQL напряму; безпечно, бо `table` завжди
# літерал у коді виклику (ніколи не користувацький ввід), і білий
# список унеможливлює будь-яке інше ім'я.
_NOTIFIABLE_TABLES = frozenset({
    "news_analysis", "news_synthesis", "market_synthesis", "candidate_assets",
    "news_consolidated",
})


def mark_notified(conn, table: str, ids: list[int]) -> None:
    """UPDATE <table> SET notified_at = now() WHERE id = ANY(ids).

    Викликати одразу після успішної відправки в Telegram — щоб
    наступний прогін (news_notify.py — двічі на добу) не надіслав ті
    самі рядки повторно, якщо за вікно з'явилось мало нового."""
    if not ids:
        return
    if table not in _NOTIFIABLE_TABLES:
        raise ValueError(f"mark_notified: непідтримувана таблиця {table!r}")
    with conn.cursor() as cur:
        cur.execute(f"UPDATE {table} SET notified_at = now() WHERE id = ANY(%s)", (ids,))  # noqa: S608 — table з білого списку вище, не користувацький ввід
    conn.commit()
