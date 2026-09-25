"""
Реєстр офіційних RSS-фідів — курований список (той самий підхід, що й
WATCHLIST_TERMS/METRICS у проєкті). Кожен фід — окремий рядок у
sources (db/schema.sql), не спільний "rss" — щоб зберегти атрибуцію
джерела в raw_news.source, а не тільки в raw_payload.

Перевірено живим запитом 2026-09-26: обидва RSS 2.0, title/link/
pubDate є завжди; description дає Fed, ECB — ні (адаптер не вимагає
description, тільки title/link/pubDate).

Потік — geopolitical: офіційні релізи центробанків — макро-політичний
контекст, не прив'язаний до конкретного watchlist-активу, той самий
клас, що й GEOPOLITICAL_TERMS (central bank) у news/queries.py.

BOJ/інші центробанки — не додано (жодного офіційного RSS URL не
перевірено живим запитом), розширюється по факту, той самий реєстр.
"""

RSS_FEEDS: dict[str, dict[str, str]] = {
    "fed_rss": {
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "stream": "geopolitical",
    },
    "ecb_rss": {
        "url": "https://www.ecb.europa.eu/rss/press.xml",
        "stream": "geopolitical",
    },
}
