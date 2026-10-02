"""
Розклад автоматичного запуску джоб. ЄДИНИЙ файл, який редагується, щоб
змінити періодичність чи час — код джоб (jobs.py/runner.py/main.py)
чіпати не треба (orchestration/CLAUDE.md).

TIMEZONE — часовий пояс, за яким читаються всі "hour"/"minute" нижче
(переходи літній/зимовий — автоматично, стандартний zoneinfo).
Перекривається змінною середовища SCHEDULER_TIMEZONE (.env), якщо
задано — за замовчуванням Europe/Kyiv.

SCHEDULE — {назва джоби: {"trigger": {...аргументи APScheduler
CronTrigger...}, "why": "одне речення чому саме такий інтервал"}}.
Назва джоби має точно збігатися з ключем у jobs.py:JOBS (перевіряється
tests/test_schedule.py). Аргументи "trigger" — та сама мова, що звичний
cron (minute/hour/day/day_of_week/day, "*/15" — кожні 15 хв), включно з
"second" (0-59, за замовчуванням 0):
https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html

"second" (2026-10-02, живий фідбек користувача — "запускати збір рівно
в час релізу, щохвилини") використовується для ланцюжка
check_releases→update_forecasts→compare_expectations→
synthesize_expectations→notify_expectations: усі п'ять тепер щохвилини
(було: зсуви В МЕЖАХ 15-хв вікна), порядок виконання в межах ТІЄЇ
САМОЇ хвилини підтримується зсувом по секундах замість зсуву по
хвилинах. Де порядок критичний (update_forecasts ПЕРЕД
compare_expectations — див. "why" нижче), секундного зазору (10с)
достатньо: обидві джоби — дешеві детерміновані SQL/обчислення без
мережі, живі логи показують ~0.1-0.3с виконання. Де є LLM-виклик
(synthesize_expectations перед notify_expectations) — зазор ширший
(30с), бо мережевий виклик DeepSeek не настільки передбачуваний.
"""

import os

TIMEZONE = os.environ.get("SCHEDULER_TIMEZONE", "Europe/Kyiv")

SCHEDULE = {
    "check_releases": {
        "trigger": {"minute": "*"},
        "why": "Щохвилини, не раз на 15 хв (2026-10-02, живий фідбек користувача: 'запускати збір рівно в час релізу, щохвилини, а не моніторити вроздріб' — попередня комбінація 15-хв цикл + 30-хв буфер давала затримку детекції до ~44 хв навіть при живому scheduler, хоча точний scheduled_at уже відомий з тижневого calendar-seed). НЕ навантаження 24/7: коли pending-рядків із настаним часом немає, check_releases.py робить лише один дешевий SELECT і виходить — реальний виклик адаптера відбувається тільки для показників, час яких дійсно настав. docs/decisions.md.",
    },
    "refresh_calendar": {
        "trigger": {"day_of_week": "mon", "hour": 6, "minute": 0},
        "why": "refresh_calendar.py сам розрахований на тижневу періодичність — заводить наперед на наступний тиждень.",
    },
    "update_forecasts": {
        "trigger": {"minute": "*", "second": 10},
        "why": "Щохвилини, +10с після check_releases (second=0) — 2026-10-02, той самий перехід на щохвилинний ритм, що й check_releases (docs/decisions.md). Читає ті самі 'detected' release_log-рядки, що compare_expectations (+15с), але статус НЕ чіпає, тому МАЄ встигнути ДО compare_expectations, поки рядки ще 'detected' (перехід у 'processed' — виключно compare_releases.py); якщо не встигне в ЦЮ хвилину (рідкісний повільний check_releases) — рядок лишається 'detected' до НАСТУПНОЇ хвилини, де update_forecasts знову має пріоритет перед compare_expectations, то й не губиться (не одноразове вікно, як було на 15-хв сітці).",
    },
    "compare_expectations": {
        "trigger": {"minute": "*", "second": 15},
        "why": "Щохвилини, +15с після check_releases (2026-10-02, docs/decisions.md) — 5с після update_forecasts (second=10), якому МАЄ поступитись чергою (див. update_forecasts:why); insert_observations() коміт synchronous у тому самому процесі check_releases, тож 15с — не очікування фіксації, а просто порядок черги в межах хвилини.",
    },
    "synthesize_expectations": {
        "trigger": {"minute": "*", "second": 20},
        "why": "Щохвилини, +20с після check_releases, +5с після compare_expectations (2026-10-02, docs/decisions.md) — LLM-синтез причинного висновку поверх уже готового сюрпризу (порівняння — рідкісна подія, зазвичай 0 нових за хвилину, тож прогін майже завжди лише дешевий SELECT 'нема нових' без LLM-виклику), перед notify_expectations.",
    },
    "notify_expectations": {
        "trigger": {"minute": "*", "second": 50},
        "why": "Щохвилини, +50с після check_releases, +30с після synthesize_expectations (2026-10-02, docs/decisions.md) — надсилає вже готові порівняння разом із синтезом, якщо встиг (30с — щедрий запас на DeepSeek-виклик, типово кілька секунд); LEFT JOIN у expectations_notify.py не блокується, якщо ні — ЦЯ хвилина піде без синтезу, але сам факт/сюрприз все одно надійде без затримки (синтез-текст для такого рідкісного запізнення не повторюється повторно, той самий компроміс, що був і на 15-хв сітці, лише тепер рідший завдяки ширшому відносному запасу).",
    },
    "notify_release_impact": {
        "trigger": {"minute": "*", "second": 55},
        "why": "Щохвилини, +5с після notify_expectations (2026-10-02, рішення користувача: 'сюрприз лишається сюрпризом, а широкий аналіз ринку — це новий звіт') — ОКРЕМЕ Telegram-повідомлення з комплексним розбором впливу (expectation_synthesis.asset_impacts), свій дедуп (impact_notified_at), не блокує й не вповільнює короткий сюрприз-звіт вище. Читає вже готовий synthesize_expectations (20с), жодного нового обчислення — лише форматування й відправка, 5с більш ніж достатньо.",
    },
    "news_collect_watchlist": {
        "trigger": {"hour": "0,6,12,18", "minute": 0},
        "why": "4 рази на добу — вікно збору (GDELT timespan=3d) з запасом перекриває цей інтервал, дедуп по url прибирає повтори (docs/decisions.md, 2026-09-26).",
    },
    "news_collect_general": {
        "trigger": {"hour": "6,14,20", "minute": 2},
        "why": "Той самий 6-годинний ритм, що й watchlist, +2 хв зсув — обидва GDELT-запити (різні query), одночасний старт із news_collect_watchlist бив по тому самому джерелу й ловив 429 (живо виявлено 2026-09-27); той самий принцип зсуву, що вже застосований до news_collect_stock (+5 хв), просто раніше пропущений тут.",
    },
    "news_collect_rss": {
        "trigger": {"hour": "6,14,20", "minute": 0},
        "why": "Офіційні RSS оновлюються нечасто — той самий ритм, що GDELT, для одноманітності циклу.",
    },
    "news_collect_stock": {
        "trigger": {"hour": "6,14,20", "minute": 5},
        "why": "+5 хв після news_collect_* — окремий GDELT-запит (тикери зі скринінгу), зсунутий старт, щоб не бити джерело одночасно.",
    },
    "news_analysis_watchlist": {
        "trigger": {"hour": "0,6,12,18", "minute": 20},
        "why": "+20 хв — дає збору (watchlist+stock) час завершитись перед DeepSeek-аналізом тих самих статей.",
    },
    "news_analysis_geopolitical": {
        "trigger": {"hour": "6,18", "minute": 20},
        "why": "Той самий офсет, що news_analysis_watchlist — незалежний потік, той самий ритм.",
    },
    "news_analysis_general": {
        "trigger": {"hour": "6,18", "minute": 20},
        "why": "Той самий офсет, що news_analysis_watchlist — незалежний потік, той самий ритм.",
    },
    "news_consolidate_watchlist": {
        "trigger": {"hour": "6,14,20", "minute": 25},
        "why": "+25 хв — після news_collect_watchlist(+0)/news_collect_stock(+5), до news_notify(+30). Один LLM-виклик на потік: фільтрує/об'єднує/перекладає сирі статті (2026-09-28, живий фідбек — окремі статті різними мовами йшли окремими повідомленнями).",
    },
    "news_consolidate_general": {
        "trigger": {"hour": "6,14,20", "minute": 26},
        "why": "Той самий принцип, що news_consolidate_watchlist, +1 хв зсув (не бити DeepSeek трьома одночасними запитами) — незалежний потік.",
    },
    "news_consolidate_geopolitical": {
        "trigger": {"hour": "6,14,20", "minute": 27},
        "why": "Той самий принцип, +2 хв зсув від watchlist — незалежний потік, RSS-джерела (news_collect_rss@0) уже завершились.",
    },
    "news_merge_similar": {
        "trigger": {"hour": "6,14,20", "minute": 28},
        "why": "+28 хв — після всіх трьох news_consolidate_* (25/26/27), до news_notify(+30). Семантичне об'єднання дублів МІЖ прогонами (2026-09-29, живий приклад — 3 переклади того самого факту про золото пішли окремими записами).",
    },
    "news_notify": {
        "trigger": {"hour": "6,14,20", "minute": 30},
        "why": "+30 хв — після news_merge_similar(+28), одне сповіщення з усіх зібраних потоків разом (рішення користувача 2026-09-28: не лише watchlist).",
    },
    "news_synthesis": {
        "trigger": {"hour": 6, "minute": 40},
        "why": "Раз на добу (не кожні 6 год, як збір) — ціна оновлюється раз на добу (watchlist_prices@6:00), частіший синтез на тому самому ціновому вікні дав би лише зайву вартість LLM без нової інформації; +40 хв дає час watchlist_prices (6:00) і news_analysis_watchlist (6:20) завершитись.",
    },
    "notify_synthesis": {
        "trigger": {"hour": 6, "minute": 45},
        "why": "+5 хв після news_synthesis, щоб надсилати вже готові висновки.",
    },
    "market_synthesis": {
        "trigger": {"hour": 18, "minute": 40},
        "why": "Раз на добу, ввечері (не зранку, як news_synthesis) — geopolitical/general збираються й аналізуються двічі на добу (6,18), вечірній прогін охоплює новини за весь день; +20 хв після news_analysis_geopolitical/general@18:20 дає їм час завершитись.",
    },
    "notify_market_synthesis": {
        "trigger": {"hour": 18, "minute": 45},
        "why": "+5 хв після market_synthesis, щоб надсилати вже готовий висновок.",
    },
    "discover_candidates": {
        "trigger": {"hour": 19, "minute": 0},
        "why": "Раз на добу, після market_synthesis@18:40/45 (не одночасно) — той самий принцип контролю вартості LLM, що news_synthesis/market_synthesis.",
    },
    "notify_candidates": {
        "trigger": {"hour": 19, "minute": 5},
        "why": "+5 хв після discover_candidates, щоб надсилати вже готовий список.",
    },
    "daily_digest": {
        "trigger": {"hour": 20, "minute": 0},
        "why": "Раз на добу, після всіх вечірніх джоб (market_synthesis@18:40/45, discover_candidates@19:00/05) — 24-годинне вікно однаково охоплює й ранкові news_synthesis@6:40/45.",
    },
    "crypto_prices": {
        "trigger": {"minute": 0},
        "why": "Крипта торгується 24/7 — щогодини, без прив'язки до релізів чи торгової сесії.",
    },
    "crypto_derivatives_collect": {
        "trigger": {"hour": 6, "minute": 10},
        "why": "Раз на добу (не щогодини, як crypto_prices — це bulk-знімок 300-500+ пар на біржу, добова гранулярність достатня для RSI(14)/тренду на денних свічках і day-over-day зміни OI, crypto_screening/), +10 хв від watchlist_prices, щоб не старт одночасно.",
    },
    "crypto_screening_daily": {
        "trigger": {"hour": 6, "minute": 25},
        "why": "+15 хв після crypto_derivatives_collect — дає час свіжій OI/обсяг-історії зафіксуватись, перш ніж Tier A/LONG рахують зміну OI за 7 днів. Раз на добу: широкий скан усього ринку — дорого й не потрібно частіше (тонкий моніторинг уже знайдених кандидатів — окрема, годинна джоба нижче).",
    },
    "crypto_candidates_monitor": {
        "trigger": {"minute": 30},
        "why": "Щогодини — користувач, 2026-09-27: денний відбір (1д) для широкого сканування ринку прийнятний, але для самого стеження за вже знайденими пампами (кандидати на SHORT/WATCH) 1д занадто повільно, потрібно 1г. Дешево (лише активні кандидати, не весь ринок).",
    },
    "watchlist_prices": {
        "trigger": {"hour": 6, "minute": 0},
        "why": "Комодіті/форекс-джерела (FRED/TwelveData) оновлюються раз на добу — досить одного ранкового прогону.",
    },
    "quotes_universe_refresh": {
        "trigger": {"hour": 3, "minute": 0},
        "why": "Раз на добу, до screening_composite_score@05:00 (буфер ~2 год на ~500 запитів із лімітом Twelve Data 8/хв, ~65 хв) — жива діра, знайдена 2026-09-27: без цієї джоби ціни S&P 500 universe для Tier A/B/C ніколи не оновлювались після одноразового ручного backfill (docs/decisions.md).",
    },
    "screening_composite_score": {
        "trigger": {"hour": 5, "minute": 0},
        "why": "Раз на добу — фундаментал (SEC EDGAR) міняється повільно, ціни в Tier A/B живі на момент запуску.",
    },
    "companies_universe_refresh": {
        "trigger": {"day_of_week": "sun", "hour": 8, "minute": 0},
        "why": "SEC-звіти (10-Q/10-K) виходять щоквартально — щотижневого прогону більш ніж достатньо, не бити SEC даремно.",
    },
    "safety_net_collect_all": {
        "trigger": {"day": 1, "hour": 7, "minute": 0},
        "why": "Щомісячний best-effort перезбір усіх показників — страховка, якщо check_releases щось пропустив; append-only дедуп робить повтор безпечним.",
    },
    "prune_logs": {
        "trigger": {"hour": 4, "minute": 30},
        "why": "Раз на добу, у найтихішу годину (між quotes_universe_refresh@3:00 і screening_composite_score@5:00) — кожен запуск джоби пише окремий файл у logs/, ~150 файлів на добу, без прибирання диск VPS росте нескінченно (jobs.py:_prune_logs, LOG_RETENTION_DAYS).",
    },
    "prune_raw_news": {
        "trigger": {"hour": 4, "minute": 35},
        "why": "Раз на добу, той самий тихий слот, що prune_logs (+5 хв) — видаляє raw_news старші за 48г (rішення користувача 2026-09-28, common/news_db.py:RETENTION_HOURS). Раз на добу досить: колекція вже обмежена 24г (MAX_ARTICLE_AGE_HOURS), 48г-вікно дає запас на день без вибуху обсягу БД.",
    },
    "scheduler_heartbeat": {
        "trigger": {"minute": "*/5"},
        "why": "Власний пульс планувальника (docs/production-readiness.md, P0) — main.py звіряє розрив при старті процесу, щоб ненормально довгий простій контейнера/хоста більше не лишався непоміченим мовчки (живий випадок 2026-10-02: реліз о 15:30 опрацьовано лише о 17:57 через непомічену ~11-год простою scheduler). 5 хв — частіше, ніж поріг алерту в main.py (20 хв), щоб кілька пропущених тиків поспіль (напр. misfire_grace_time) не виглядали як справжній простій.",
    },
}
