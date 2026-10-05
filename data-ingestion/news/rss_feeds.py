"""
Реєстр RSS-фідів — курований список джерел (той самий підхід, що й
WATCHLIST_TERMS/METRICS у проєкті), АЛЕ не курований список ТЕМ.
Кожен фід — окремий рядок у sources (db/schema.sql), не спільний "rss"
— щоб зберегти атрибуцію джерела в raw_news.source, а не тільки в
raw_payload.

Три класи джерел в одному реєстрі:

1. (geopolitical) Fed/ECB/BOJ — офіційні релізи центробанків (first-party, вузькі за
   обсягом, тільки прес-релізи). Перевірено живим запитом (WebFetch,
   до коду) 2026-09-26: усі три RSS 2.0, title/link/pubDate є завжди;
   description дає Fed, ECB і BOJ — ні (тег присутній, завжди
   порожній). Покривають ті самі три економіки, що macro/-адаптери
   (fred_adapter.py/ecb_adapter.py/boj_adapter.py) — news/ і macro/
   свідомо дублюють географію: macro/ дає числові показники, news/ —
   контекст навколо них.

2. (geopolitical) bbc/aljazeera/guardian/npr/skynews/dw — широкі редакційні "top
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

3. (general) РИНКОВІ/БІЗНЕС-фіди — додані 2026-10-05
   (docs/decisions.md). До цього потік `general` мав ЄДИНЕ джерело —
   GDELT, без жодного резерву, і коли IP потрапив у тривалий штрафний
   стан GDELT (429 + мʼякий троттл "200 {}"), потік просто помер:
   нуль статей за 7 днів, нуль релевантних. Живий фідбек користувача
   того дня: "а чого до цієї пори не має резервних джерел!!!!" —
   справедливо: `geopolitical` отримав RSS-резерв ще 2026-09-27, а
   `general`/`watchlist` залишились одноджерельними, і збій був ТИХИЙ
   (мʼякий троттл читався як "немає новин", скрипт виходив з кодом 0).

   Та сама логіка, що й у класі 2: беремо НАЙШИРШУ бізнес-стрічку
   кожного джерела, не вгадуємо теми наперед; значущість визначає
   `aggregate.py:cluster_articles()` за кількістю незалежних джерел,
   релевантність для ринку — DeepSeek.

   Усі URL живо перевірені (HTTP 200, валідний XML, pubDate у
   кожного) 2026-10-05 ПЕРЕД написанням коду. FT-фід лишається
   корисним попри пейволл: ми беремо лише title+url, тіло статті не
   читаємо.

   Nasdaq (`https://www.nasdaq.com/feed/rssoutbound?category=Markets`)
   перевірку пройшов, але в РЕАЛЬНИХ прогонах дав read timeout двічі
   поспіль (30с і 45с) — тому в реєстр НЕ включений. Правило
   data-ingestion/CLAUDE.md: неофіційне джерело, недоступне поспіль,
   не латаємо нескінченно. Вісім інших бізнес-фідів дають ~200
   статей на прогін, тож втрата покриття незначна.

   `watchlist` (новини ПО КОНКРЕТНОМУ активу) резерву так і не має —
   і це чесне обмеження, не недогляд: RSS не вміє запиту "лише про
   золото", цільовий запит може зробити тільки GDELT. Натомість той
   самий збій тепер не тихий: мʼякий троттл піднімає помилку, джоба
   падає, runner.py бачить провал (gdelt_adapter.py, 2026-10-05).
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
    # ---- Ринкові/бізнес-фіди, потік general (2026-10-05) ----
    "cnbc_markets_rss": {
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "stream": "general",
    },
    "yahoo_finance_rss": {
        "url": "https://finance.yahoo.com/news/rssindex",
        "stream": "general",
    },
    "marketwatch_rss": {
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "stream": "general",
    },
    "investing_rss": {
        "url": "https://www.investing.com/rss/news.rss",
        "stream": "general",
    },
    "bbc_business_rss": {
        "url": "https://feeds.bbci.co.uk/news/business/rss.xml",
        "stream": "general",
    },
    "guardian_business_rss": {
        "url": "https://www.theguardian.com/uk/business/rss",
        "stream": "general",
    },
    "npr_business_rss": {
        "url": "https://feeds.npr.org/1006/rss.xml",
        "stream": "general",
    },
    "ft_rss": {
        "url": "https://www.ft.com/rss/home",
        "stream": "general",
    },
}
