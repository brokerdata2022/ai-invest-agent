"""
Реєстр офіційних RSS-фідів — курований список (той самий підхід, що й
WATCHLIST_TERMS/METRICS у проєкті). Кожен фід — окремий рядок у
sources (db/schema.sql), не спільний "rss" — щоб зберегти атрибуцію
джерела в raw_news.source, а не тільки в raw_payload.

Перевірено живим запитом (WebFetch, до коду) 2026-09-26: усі три
RSS 2.0, title/link/pubDate є завжди; description дає Fed, ECB і BOJ
— ні (BOJ: тег присутній, але завжди порожній) — адаптер не вимагає
description, тільки title/link/pubDate.

Потік — geopolitical: офіційні релізи центробанків — макро-політичний
контекст, не прив'язаний до конкретного watchlist-активу, той самий
клас, що й GEOPOLITICAL_TERMS (central bank) у news/queries.py.

Fed/ECB/BOJ покривають ті самі три економіки, що й macro/-адаптери
(fred_adapter.py/ecb_adapter.py/boj_adapter.py) — news/ і macro/
свідомо дублюють географію: macro/ дає числові показники (ставки,
CPI), news/ дає контекст навколо них (чому/коли щось змінюється).
Інші центробанки — не додано (жодного офіційного RSS URL не
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
    "boj_rss": {
        "url": "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "stream": "geopolitical",
    },
}
