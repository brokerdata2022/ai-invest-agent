#!/usr/bin/env python3
"""
Telegram-команди людською мовою — ручний запуск джоб замість
`docker compose exec app python orchestration/run_job.py <назва>`
(docs/decisions.md 2026-09-28/2026-10-03, рішення користувача: "команди
мають бути зрозумілі для користувача + назва джоби та опис що саме
вона робить").

Команда = ім'я джоби, але НЕ будь-якої з jobs.py:JOBS — лише
`command_descriptions.py:INFO_JOB_NAMES` (2026-10-03, рішення
користувача: "забери всі технічні джоби з меню, лиши тільки для
отримання інформації" — notify_*/daily_digest, 12 джоб; решта 32
збирають/обробляють дані, самі нічого не надсилають, і далі лише за
розкладом, ручний запуск — docker exec run_job.py). Назва+опис кожної
видно в "/"-меню Telegram (register_telegram_commands.py:setMyCommands)
і на /help тут.

Авторизація: лише TELEGRAM_CHAT_ID з .env (єдиний користувач) —
повідомлення з іншого chat_id повністю ігнорується (ані не виконується,
ані не отримує відповідь).

Запуск джоби — НЕБЛОКУЮЧИЙ subprocess (той самий `run_job.py <назва>`,
тому той самий код/логи/ретраї/Telegram-алерт при провалі, що й за
розкладом): одразу відповідає підтвердженням, НЕ чекає завершення —
деякі джоби тривають десятки хвилин (quotes_universe_refresh ~78 хв),
чекати означало б не обробляти наступні команди весь цей час.

Короткий polling (getUpdates, timeout=0) — щохвилини (schedule.py)
опитує і виходить, не тримає довге з'єднання; offset зберігається в
telegram_command_offset (один рядок, той самий принцип, що
scheduler_heartbeat), щоб те саме повідомлення не обробилось двічі.

Три додаткові спеціальні команди (2026-10-03, docs/decisions.md,
рішення користувача: "редагування списку обраних активів через
Telegram") — НЕ з реєстру JOBS, своя гілка диспетчеризації:
- /watchlist_list — поточний watchlist (common/watchlist_db.py).
- /watchlist_add <TICKER> — додає НОВИЙ актив. НЕ вгадує джерело за
  форматом тикера (перша версія розрізняла "з / чи без /" — живий
  кейс BNB показав, що це ламається вже на наступному прикладі:
  commodity-тикери на Twelve Data теж часто БЕЗ "/", напр. природний
  газ/какао). Замість цього — пробує ВСІ генеричні джерела по черзі,
  той самий тикер, доки одне не підтвердить (той самий підхід, що
  analysis/news_analysis/discover_candidates.py:verify_tradable()):
  1) Twelve Data (форекс/товари/акції — найширше покриття; якщо
  ТОЧНИЙ рядок користувача не підтвердився — ще й `symbol_search()`
  (2026-10-03, живий кейс "NATGAS" дав 404 на точний рядок — лише
  точний рядок без пошуку змусив би користувача вгадувати формат
  навмання);
  2) Binance spot (+"USDT", якщо символ сам не крипто-пара) —
  `crypto/binance_adapter.py:BinanceAdapter(symbol=...)`, конструктор
  отримав `symbol=` в обхід фіксованого METRICS (2026-10-03), той
  самий принцип, що Twelve Data. Жодне з двох не підтвердило → чесна
  відмова: fred/coingecko мають фіксований словник METRICS у своєму
  адаптері без прямого символьного параметра, новий актив ТАМ і далі
  вимагає коду — користувачу не потрібно знати, яке джерело спробувати,
  команда сама перебирає все доступне.
- /watchlist_remove <asset_id|TICKER> — вимикає (enabled=false).

Використання:
    python telegram_commands.py
"""

import logging
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT / "reporting"))

# _common додає data-ingestion у sys.path (дефіс у назві теки — не
# валідне ім'я Python-пакета), тому імпортується ПЕРШИМ (той самий
# принцип, що reporting/CLAUDE.md).
from _common import bold, escape_html  # noqa: E402
from command_descriptions import INFO_JOB_NAMES, JOB_DESCRIPTIONS, SPECIAL_COMMAND_DESCRIPTIONS  # noqa: E402
from common.db import get_connection  # noqa: E402
from common.watchlist_db import add_asset, fetch_watchlist, find_asset, set_enabled  # noqa: E402
from crypto.binance_adapter import BinanceAdapter  # noqa: E402
from news.gdelt_adapter import validate_gdelt_term  # noqa: E402
from quotes.twelvedata_adapter import TwelveDataAdapter  # noqa: E402
from quotes.twelvedata_adapter import search_symbol as search_twelvedata_symbol  # noqa: E402
from telegram_client import get_updates, send_telegram_message  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HELP_COMMANDS = frozenset({"help", "start"})
WATCHLIST_COMMANDS = frozenset({"watchlist_list", "watchlist_add", "watchlist_remove"})


def parse_command(text: str) -> str | None:
    """'/notify_screening@MyBot аргумент' → 'notify_screening'. None,
    якщо повідомлення не схоже на команду (не починається з '/',
    порожнє, чи сам '/' без імені)."""
    if not text or not text.startswith("/"):
        return None
    first_word = text.split(maxsplit=1)[0]
    command = first_word[1:].split("@", 1)[0].lower()
    return command or None


def parse_command_args(text: str) -> str:
    """Текст ПІСЛЯ самої команди, без зайвих пробілів — '' якщо
    аргументів не було ('/watchlist_add GBP/USD' → 'GBP/USD')."""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def normalize_ticker_to_asset_id(ticker: str) -> str:
    """'GBP/USD' → 'gbpusd'; 'BNB'/'BNBUSDT' → 'bnb' (однаково) — той
    самий внутрішній asset_id незалежно від того, яким саме записом
    (із суфіксом USDT чи без) користувач звернувся, і від того, яке
    джерело зрештою підтвердило тикер (Twelve Data чи Binance,
    2026-10-03) — дозволяє /watchlist_remove прийняти як asset_id
    ('gbpusd'), так і тикер ('GBP/USD'/'BNB'/'BNBUSDT') однаково."""
    normalized = ticker.strip().upper().replace("/", "")
    normalized = normalized.removesuffix("USDT")
    return normalized.lower()


def is_authorized(chat_id, configured_chat_id: str) -> bool:
    return str(chat_id) == str(configured_chat_id)


def format_help() -> str:
    info_descriptions = {k: v for k, v in JOB_DESCRIPTIONS.items() if k in INFO_JOB_NAMES}
    all_descriptions = {**SPECIAL_COMMAND_DESCRIPTIONS, **info_descriptions}
    lines = [bold("📋 Доступні команди:"), ""]
    for name in sorted(all_descriptions):
        lines.append(f"• {bold('/' + name)} — {escape_html(all_descriptions[name])}")
    return "\n".join(lines)


def format_launch_ack(job_name: str) -> str:
    description = JOB_DESCRIPTIONS.get(job_name, "")
    return f"🚀 Запущено: {bold(job_name)}\n{escape_html(description)}"


def format_unknown_command(command: str) -> str:
    return f"❓ Невідома команда: {bold('/' + command)}\n/help — список команд"


def format_watchlist_list(rows: list[dict]) -> str:
    if not rows:
        return "📋 Watchlist порожній."
    lines = [bold(f"📋 Watchlist ({len(rows)}):"), ""]
    for row in rows:
        lines.append(f"• {bold(row['asset_id'])} — {escape_html(row['label'])} ({escape_html(row['source'])})")
    return "\n".join(lines)


def validate_twelvedata_ticker(ticker: str, api_key: str) -> bool:
    """Живий запит Twelve Data (той самий підхід, що
    discover_candidates.py:verify_tradable()) — True лише якщо символ
    реальний і має хоч одну точку ціни."""
    try:
        records = TwelveDataAdapter(api_key=api_key, ticker=ticker).collect(limit=1)
    except (ValueError, requests.exceptions.RequestException):
        logger.exception("watchlist_add: помилка перевірки тикера %r у Twelve Data", ticker)
        return False
    return bool(records)


def validate_binance_symbol(symbol: str) -> bool:
    """Той самий підхід, що validate_twelvedata_ticker() — живий запит
    Binance spot klines (BinanceAdapter(symbol=...) в обхід METRICS,
    2026-10-03). True лише якщо символ реальний і має хоч одну свічку."""
    try:
        records = BinanceAdapter(metric_id="_watchlist_add_check", symbol=symbol).collect(limit=1)
    except (ValueError, requests.exceptions.RequestException):
        logger.exception("watchlist_add: помилка перевірки символу %r у Binance", symbol)
        return False
    return bool(records)


def _reactivate_or_report_existing(conn, asset_id: str) -> str | None:
    """Якщо asset_id вже є у watchlist (увімкнений чи ні) — повертає
    готове повідомлення. None, якщо asset_id новий — викликач продовжує
    додавання (live-перевірка + add_asset)."""
    existing = find_asset(conn, asset_id)
    if existing is None:
        return None
    if existing["enabled"]:
        return f"{bold(asset_id)} уже є в watchlist."
    set_enabled(conn, asset_id, True)
    return f"✅ {bold(asset_id)} повернуто у watchlist (був вимкнений)."


def _resolve_news_search_term(primary: str, widened: str | None = None) -> str | None:
    """Live-перевірка GDELT (validate_gdelt_term) ПЕРЕД тим, як термін
    піде в продакшн watchlist-запит — 2026-10-04, живий кейс "BNB":
    доданий без цієї перевірки термін зламав ЦІЛИЙ watchlist-запит
    (один поганий OR-термін псує запит для ВСІХ активів одразу, не
    лише нового). `primary` пробується першим; якщо GDELT відхилив і
    задано `widened` (ширший варіант, напр. з уточнювальним словом) —
    пробує його; якщо й це не пройшло — None (актив іде в watchlist і
    збирає ЦІНУ, просто без участі в GDELT-запиті — fetch_terms()
    сам пропускає рядки з search_term=NULL)."""
    if validate_gdelt_term(primary):
        return f'"{primary}"'
    if widened is not None and validate_gdelt_term(widened):
        return f'"{widened}"'
    return None


def _try_add_via_twelvedata(conn, ticker_arg: str, asset_id: str, twelvedata_api_key: str | None) -> str | None:
    """None = не підтвердило (чи немає ключа) — викликач пробує
    наступне джерело. Не окрема відмова для ЦЬОГО джерела — остаточна
    відмова (жодне джерело не підтвердило) формулюється в
    handle_watchlist_add(), одним повідомленням на всі спроби.

    Точний рядок користувача СПЕРШУ (найчастіший випадок — уже
    правильний тикер), і лише якщо він не підтвердився — пошук через
    `symbol_search` (2026-10-03, живий кейс "NATGAS": точний рядок дав
    404, хоча Twelve Data, можливо, знає інструмент під іншим кодом —
    без цього користувач мусив би вгадувати формат навмання). Знайдений
    кандидат ще раз підтверджується живими даними — symbol_search сам
    лише довідниковий каталог, не гарантія наявності історії цін."""
    if not twelvedata_api_key:
        return None

    ticker = ticker_arg.strip().upper()
    if validate_twelvedata_ticker(ticker, twelvedata_api_key):
        resolved = ticker
    else:
        candidate = search_twelvedata_symbol(ticker_arg, twelvedata_api_key)
        if candidate is None or not validate_twelvedata_ticker(candidate, twelvedata_api_key):
            return None
        resolved = candidate

    metric_id = f"{asset_id}_close"
    search_term = _resolve_news_search_term(resolved)
    add_asset(
        conn, asset_id=asset_id, source="twelvedata", metric_id=metric_id,
        ticker=resolved, label=resolved, search_term=search_term,
    )
    note = "" if search_term else " (без новинного пошуку — термін не пройшов перевірку GDELT)"
    return f"✅ Додано {bold(resolved)} у watchlist (asset_id={asset_id}, джерело: Twelve Data){note}."


def _try_add_via_binance(conn, asset_id: str) -> str | None:
    """None = Binance не підтвердив — той самий контракт, що
    _try_add_via_twelvedata(). `asset_id` уже нормалізований
    (normalize_ticker_to_asset_id) — тут лише додаємо "USDT" й
    пробуємо як спот-пару."""
    base = asset_id.upper()
    symbol = f"{base}USDT"
    if not validate_binance_symbol(symbol):
        return None

    metric_id = f"{asset_id}_close"
    label = f"{base}/USDT"
    # Короткі тикери (3-4 символи) — САМЕ той випадок, що GDELT
    # відхиляє як "too short" (той самий "Uber"-урок) — "crypto"
    # додає контекст/довжину без зміни суті пошуку.
    search_term = _resolve_news_search_term(base, widened=f"{base} crypto")
    add_asset(
        conn, asset_id=asset_id, source="binance", metric_id=metric_id,
        ticker=symbol, label=label, search_term=search_term,
    )
    note = "" if search_term else " (без новинного пошуку — термін не пройшов перевірку GDELT)"
    return f"✅ Додано {bold(label)} у watchlist (asset_id={asset_id}, джерело: Binance){note}."


def handle_watchlist_add(conn, ticker_arg: str, twelvedata_api_key: str | None) -> str:
    """Пробує генеричні джерела ПО ЧЕРЗІ на тому самому тикері —
    Twelve Data (форекс/товари/акції), потім Binance spot (+"USDT",
    крипто) — не вгадує заздалегідь за форматом (2026-10-03, живий
    кейс: "/"-гейт зі старої версії неправильно відсік би й ВІРНІ
    commodity-тикери Twelve Data без "/", напр. природний газ/какао).
    Перше джерело, що підтвердить тикер живим запитом, — те й додає."""
    ticker_arg = ticker_arg.strip()
    if not ticker_arg:
        return "Вкажіть тикер, напр. /watchlist_add GBP/USD, /watchlist_add BNB, /watchlist_add NATGAS"

    asset_id = normalize_ticker_to_asset_id(ticker_arg)
    existing_reply = _reactivate_or_report_existing(conn, asset_id)
    if existing_reply is not None:
        return existing_reply

    reply = _try_add_via_twelvedata(conn, ticker_arg, asset_id, twelvedata_api_key)
    if reply is not None:
        return reply

    reply = _try_add_via_binance(conn, asset_id)
    if reply is not None:
        return reply

    return (
        f"❌ Жодне з доступних джерел не підтвердило {bold(ticker_arg)} — "
        f"пробували точний рядок І пошук за назвою (Twelve Data "
        f"symbol_search), і Binance spot. Або символ/назва насправді не "
        f"збігається з жодним реальним інструментом, або це macro-серія "
        f"FRED чи метрика CoinGecko поза крипто-спотом — ці два джерела не "
        f"мають генеричного пошуку за тикером, додати можна лише зміною "
        f"коду адаптера."
    )


def handle_watchlist_remove(conn, asset_arg: str) -> str:
    asset_arg = asset_arg.strip()
    if not asset_arg:
        return "Вкажіть актив, напр. /watchlist_remove GBP/USD"

    asset_id = normalize_ticker_to_asset_id(asset_arg)
    existing = find_asset(conn, asset_id)
    if existing is None:
        return f"❓ {bold(asset_id)} немає у watchlist."
    if not existing["enabled"]:
        return f"{bold(asset_id)} уже вимкнений."

    # Вимкнути можна БУДЬ-ЯКИЙ актив незалежно від джерела (на відміну
    # від watchlist_add, де обмеження лише на ДОДАВАННЯ нового —
    # DYNAMICALLY_ADDABLE_SOURCES тут не застосовується).
    set_enabled(conn, asset_id, False)
    return f"🗑 {bold(asset_id)} вимкнено з watchlist."


def launch_job(job_name: str) -> None:
    """Неблокуючий запуск того самого скрипта, що ручний
    `python orchestration/run_job.py <назва>` — subprocess.Popen, НЕ
    `.run()`: не чекаємо завершення (докстрінг модуля)."""
    subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "orchestration" / "run_job.py"), job_name],
        cwd=REPO_ROOT,
    )


def get_offset(conn) -> int:
    with conn.cursor() as cur:
        cur.execute("SELECT last_update_id FROM telegram_command_offset WHERE id = 1")
        row = cur.fetchone()
    return (row[0] + 1) if row else 0


def save_offset(conn, last_update_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO telegram_command_offset (id, last_update_id)
            VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE SET last_update_id = EXCLUDED.last_update_id
            """,
            (last_update_id,),
        )
    conn.commit()


def process_update(
    update: dict, configured_chat_id: str, token: str, conn=None, twelvedata_api_key: str | None = None,
) -> None:
    """`conn`/`twelvedata_api_key` потрібні лише для WATCHLIST_COMMANDS
    (help/job-launch/unknown гілки їх не торкаються) — необов'язкові
    параметри, щоб існуючі викликачі/тести без watchlist-команд
    лишались без змін."""
    message = update.get("message")
    if not message or "text" not in message:
        return  # інший тип оновлення (edited_message/channel_post/...) — ігноруємо

    chat_id = message["chat"]["id"]
    if not is_authorized(chat_id, configured_chat_id):
        logger.warning("Повідомлення від неавторизованого chat_id=%s ігнорується", chat_id)
        return

    text = message["text"]
    command = parse_command(text)
    if command is None:
        return  # не команда (звичайний текст) — мовчки пропускаємо

    if command in HELP_COMMANDS:
        send_telegram_message(token, configured_chat_id, format_help(), parse_mode="HTML")
    elif command == "watchlist_list":
        rows = fetch_watchlist(conn)
        send_telegram_message(token, configured_chat_id, format_watchlist_list(rows), parse_mode="HTML")
    elif command == "watchlist_add":
        reply = handle_watchlist_add(conn, parse_command_args(text), twelvedata_api_key)
        send_telegram_message(token, configured_chat_id, reply, parse_mode="HTML")
    elif command == "watchlist_remove":
        reply = handle_watchlist_remove(conn, parse_command_args(text))
        send_telegram_message(token, configured_chat_id, reply, parse_mode="HTML")
    elif command in INFO_JOB_NAMES:
        launch_job(command)
        send_telegram_message(token, configured_chat_id, format_launch_ack(command), parse_mode="HTML")
        logger.info("Команда /%s від chat_id=%s — запущено", command, chat_id)
    else:
        send_telegram_message(token, configured_chat_id, format_unknown_command(command), parse_mode="HTML")


def main() -> None:
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID не задані в .env — слухач команд не запущено")
        sys.exit(1)

    twelvedata_api_key = os.environ.get("TWELVEDATA_API_KEY")

    conn = get_connection()
    try:
        offset = get_offset(conn)
        updates = get_updates(token, offset=offset, timeout=0)
        if not updates:
            logger.info("Нових повідомлень немає")
            return

        for update in updates:
            try:
                process_update(
                    update, configured_chat_id=chat_id, token=token,
                    conn=conn, twelvedata_api_key=twelvedata_api_key,
                )
            except Exception:
                logger.exception("Помилка обробки update_id=%s — пропущено", update.get("update_id"))
            finally:
                # Зберігаємо offset ОДРАЗУ після кожного (не батчем наприкінці) —
                # щоб помилка на update #5 з 10 не змусила наступний прогін
                # повторно обробити вже опрацьовані 1-4 (той самий принцип, що
                # mark_notified одразу після кожного send у reporting/).
                save_offset(conn, update["update_id"])

        logger.info("Опрацьовано %d оновлень", len(updates))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
