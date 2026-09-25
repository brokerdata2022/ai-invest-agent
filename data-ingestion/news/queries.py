"""
Побудова GDELT query-рядка per stream — чисте звуження джерела
(rule 1: жодної оцінки релевантності тут, тільки те, ЩО шукати).

watchlist (docs/watchlist.md, закритий список активів поза акціями
S&P 500) — build_watchlist_query(). Акції зі скринінгу — окрема
функція build_stocks_query(), окремий запит (не один об'єднаний з
build_watchlist_query()) — щоб не наближатись до невідомого офіційно
ліміту довжини/к-сті OR-термінів GDELT DOC API. Обидві пишуться в той
самий stream="watchlist" (це та сама категорія "вже відібрані
активи"), просто двома окремими викликами collect().

geopolitical — build_geopolitical_query(), фіксований курований набір
тем (санкції/конфлікти/торгові війни/центробанки/вибори), НЕ прив'язаний
до конкретного активу (asset_id лишається None — DeepSeek не отримує
tracked_assets для цього потоку, analysis/news_analysis/run_news_analysis.py).

general — ще не побудований, докладніше docs/decisions.md, 2026-09-25.
"""

# Один пошуковий термін на актив із docs/watchlist.md — найпоширеніша
# назва в новинах, не тикер біржі (GDELT — загальний новинний текст,
# не фінансові дані).
WATCHLIST_TERMS: dict[str, str] = {
    "xauusd": '"gold price"',
    "xagusd": '"silver price"',
    "wti_crude": '"WTI crude"',
    "brent_crude": '"Brent crude"',
    "coffee": '"coffee futures"',
    "eurusd": '"EUR/USD"',
    "usdjpy": '"USD/JPY"',
    "btc": "Bitcoin",
    "eth": "Ethereum",
    "sol": "Solana",
}


def build_watchlist_query() -> str:
    return "(" + " OR ".join(WATCHLIST_TERMS.values()) + ")"


# Внутрішні ідентифікатори активів watchlist-потоку — підказка для
# DeepSeek (analysis/news_analysis/), яким asset_id позначати статтю,
# якщо вона прямо про один з цих активів. Ті самі ключі, що й
# WATCHLIST_TERMS (одне джерело істини для "що таке watchlist").
WATCHLIST_ASSET_IDS: list[str] = list(WATCHLIST_TERMS)


# Ручні заміни назви для тикерів, де офіційна назва з S&P 500
# constituents.csv ("Security") сама по собі — надто коротке й надто
# загальновживане англійське слово для GDELT full-text search.
# Підтверджено ДВОМА живими прогонами 2026-09-25: query з терміном
# "Uber" (сам по собі, у лапках) GDELT відхиляв як "The specified
# phrase is too short" — і на 41 символі, і на 175 символах (в іншій
# групі з 8 додатковими термінами) — тобто причина не в довжині
# ЗАГАЛЬНОГО query (інші короткі однослівні назви в тих самих групах,
# "Emcor"/"Wabtec"/"Casey's", проходили без проблем). GDELT сам
# документує відхилення "дуже коротких АБО дуже загальновживаних"
# слів навіть у лапках (blog.gdeltproject.org) — "uber" це звичайне
# англійське слово (підсилювач, "über"), а не тільки назва компанії,
# на відміну від "Emcor"/"Wabtec". Точний алгоритм "загальновживаності"
# GDELT не документує, тому фіксуємо конкретний підтверджений випадок
# явно (як власну назву компанії, а не вгадану трансформацію) — той
# самий підхід кураторства, що й WATCHLIST_TERMS/METRICS в проєкті.
STOCK_NAME_OVERRIDES: dict[str, str] = {
    "UBER": "Uber Technologies",
}


def build_stocks_query(ticker_names: dict[str, str]) -> str:
    """Query для тикерів, що пройшли скринінг (analysis/screening/).

    ticker_names — {тикер: назва компанії}; пошуковий термін — назва
    компанії (STOCK_NAME_OVERRIDES, якщо є, інакше як дано), якщо
    відома (менш неоднозначна за GDELT full-text search, ніж короткий
    тикер на кшталт "BX"/"COP", які збігаються зі звичайними словами),
    інакше сам тикер. Список тикерів свідомо НЕ читається тут з
    БД/screening — ticker_names передає викликач (analysis/, бо
    data-ingestion не повинен залежати від analysis/, rule 1
    CLAUDE.md) — ця функція лишається чистою й тестованою без
    БД/мережі.
    """
    if not ticker_names:
        raise ValueError("ticker_names не може бути порожнім")
    terms = []
    for ticker, name in ticker_names.items():
        resolved = STOCK_NAME_OVERRIDES.get(ticker, name)
        terms.append(f'"{resolved}"' if resolved else ticker)
    return "(" + " OR ".join(terms) + ")"


# MAX_QUERY_LEN — підтверджено живо: 294-символьний query (16 повних
# назв) GDELT відхилив як "too short or too long", 117-150 символів
# проходили без проблем (docs/decisions.md, 2026-09-25) — 150
# консервативний запас під підтверджений робочий розмір, точна межа
# офіційно не задокументована.
#
# MIN_QUERY_LEN — НЕ підтверджено як окрема причина (docs/decisions.md,
# 2026-09-25 "MIN_QUERY_LEN — спростовано як причина"): єдиний
# 41-символьний query, що падав, також містив "Uber" (STOCK_NAME_
# OVERRIDES нижче) — той самий query довжиною 175 символів (після
# об'єднання з іншою групою) падав з тим самим "too short", тобто
# справжня причина була термін "Uber", не довжина. Поріг лишається як
# захисна евристика (шкоди не завдає — об'єднаний "хвіст" все одно
# лишається значно коротшим за підтверджений збійний максимум 294),
# але не варто довіряти йому як задокументованому факту.
MAX_QUERY_LEN = 150
MIN_QUERY_LEN = 70


# Курований набір геополітичних тем — контекст для ринкового аналізу
# в цілому, НЕ прив'язаний до конкретного активу (на відміну від
# watchlist). Багатослівні фрази навмисно (кожен термін ≥2 слова, крім
# "OPEC" — акронім, власна назва, як "Emcor"/"Wabtec", а не звичайне
# слово): GDELT відхиляє окремі короткі загальновживані англійські
# слова навіть у лапках (docs/decisions.md, 2026-09-25, кейс "Uber") —
# "sanctions"/"tariffs"/"election" самі по собі ризиковані з тієї самої
# причини, тому обрані як частина довшої специфічної фрази.
GEOPOLITICAL_TERMS: dict[str, str] = {
    "sanctions": '"economic sanctions"',
    "conflict": '"armed conflict"',
    "trade_war": '"trade war"',
    "tariffs": '"trade tariffs"',
    "central_bank_policy": '"central bank"',
    "opec": "OPEC",
    "election": '"national election"',
}


def build_geopolitical_query() -> str:
    return "(" + " OR ".join(GEOPOLITICAL_TERMS.values()) + ")"


def batch_ticker_names(
    ticker_names: dict[str, str],
    max_query_len: int = MAX_QUERY_LEN,
    min_query_len: int = MIN_QUERY_LEN,
) -> list[dict[str, str]]:
    """Ділить ticker_names на групи такого розміру, щоб
    build_stocks_query() кожної групи лишався під max_query_len
    символів — довжина назв компаній дуже різна ("Uber" проти
    "Huntington Ingalls Industries"), тому групування за к-стю
    тикерів (фіксоване число на групу) було б або занадто
    консервативним, або все одно інколи перевищувало б ліміт.

    Жадібне заповнення до max_query_len може лишити замалий "хвіст"
    в останній групі (GDELT відхиляє й це, min_query_len вище) —
    такий хвіст приєднується до попередньої групи, а не лишається
    окремим приреченим на "too short" запитом."""
    if not ticker_names:
        return []

    batches: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for ticker, name in ticker_names.items():
        candidate = {**current, ticker: name}
        if current and len(build_stocks_query(candidate)) > max_query_len:
            batches.append(current)
            current = {ticker: name}
        else:
            current = candidate
    if current:
        batches.append(current)

    if len(batches) > 1 and len(build_stocks_query(batches[-1])) < min_query_len:
        batches[-2] = {**batches[-2], **batches[-1]}
        batches.pop()

    return batches
