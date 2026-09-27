"""
Реєстр RSS-фідів — курований список джерел (той самий підхід, що й
WATCHLIST_TERMS/METRICS у проєкті), АЛЕ не курований список ТЕМ.
Кожен фід — окремий рядок у sources (db/schema.sql), не спільний "rss"
— щоб зберегти атрибуцію джерела в raw_news.source, а не тільки в
raw_payload.

Два класи джерел в одному реєстрі, обидва stream="geopolitical":

1. Fed/ECB/BOJ — офіційні релізи центробанків (first-party, вузькі за
   обсягом, тільки прес-релізи). Перевірено живим запитом (WebFetch,
   до коду) 2026-09-26: усі три RSS 2.0, title/link/pubDate є завжди;
   description дає Fed, ECB і BOJ — ні (тег присутній, завжди
   порожній). Покривають ті самі три економіки, що macro/-адаптери
   (fred_adapter.py/ecb_adapter.py/boj_adapter.py) — news/ і macro/
   свідомо дублюють географію: macro/ дає числові показники, news/ —
   контекст навколо них.

2. bbc/aljazeera/guardian/npr/skynews/dw — широкі редакційні "top
   stories" фіди НЕЗАЛЕЖНИХ агентств, додані 2026-09-27
   (docs/decisions.md) — заміна GDELT-запиту з курованим списком фраз
   (`news/queries.py:GEOPOLITICAL_TERMS`, видалено), який структурно
   ловив тільки наперед передбачені теми (санкції/конфлікти/торгові
   війни/центробанки/вибори) — велика непередбачена подія (загроза
   вторгнення, військове нарощування, науковий прорив) не збігається
   дослівно з жодною курованою фразою й просто НІКОЛИ не потрапляла в
   raw_news. Рішення користувача: замість вгадувати теми наперед,
   брати НАЙШИРШУ стрічку кожного джерела (не GDELT-подібний
   query-фільтр по ключових словах) і покластись на
   analysis/news_analysis/aggregate.py:cluster_articles()/source_count
   — якщо новина правдива й важлива, вона з'явиться в кількох
   незалежних джерелах одночасно, це і є природний фільтр значущості/
   шуму, а DeepSeek (analysis/) вирішує релевантність для ринку.
   Усі 6 URL живо перевірені (HTTP 200) 2026-09-27, перед кодом.
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
    "bbc_rss": {
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "stream": "geopolitical",
    },
    "aljazeera_rss": {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "stream": "geopolitical",
    },
    "guardian_rss": {
        "url": "https://www.theguardian.com/world/rss",
        "stream": "geopolitical",
    },
    "npr_rss": {
        "url": "https://feeds.npr.org/1001/rss.xml",
        "stream": "geopolitical",
    },
    "skynews_rss": {
        "url": "https://feeds.skynews.com/feeds/rss/world.xml",
        "stream": "geopolitical",
    },
    "dw_rss": {
        "url": "https://rss.dw.com/xml/rss-en-all",
        "stream": "geopolitical",
    },
}
