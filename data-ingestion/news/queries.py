"""
Побудова GDELT query-рядка per stream — чисте звуження джерела
(rule 1: жодної оцінки релевантності тут, тільки те, ЩО шукати).

Наразі тільки watchlist (docs/watchlist.md, закритий список активів
поза акціями S&P 500, 2026-09-25). general/geopolitical і query для
акцій зі скринінгу (потребує читання поточного списку з БД) — ще не
побудовані, докладніше docs/decisions.md, 2026-09-25.
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
