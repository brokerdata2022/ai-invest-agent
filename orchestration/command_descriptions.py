"""
Людські описи кожної джоби (JOBS/SCHEDULE) — для Telegram-команд
(docs/decisions.md 2026-10-03, рішення користувача: "команди мають
бути зрозумілі для користувача + назва джоби та опис що саме вона
робить"). Один рядок на джобу:
- `register_telegram_commands.py` реєструє їх через Telegram
  `setMyCommands` — назва+опис видно одразу в "/"-меню бота.
- `telegram_commands.py` показує той самий текст на /help.

tests/test_command_descriptions.py перевіряє, що жодна джоба з
schedule.py:SCHEDULE/jobs.py:JOBS не лишилась без опису (і навпаки).
Ліміт Telegram на описи команд — 1-256 символів, без переносу рядка.
"""

JOB_DESCRIPTIONS: dict[str, str] = {
    "check_releases": "Перевірити й зібрати нові дані за календарем релізів",
    "refresh_calendar": "Оновити календар релізів на наступний тиждень",
    "calendar_outlook": "Згенерувати ранковий огляд календаря (тиждень/день)",
    "notify_calendar_outlook": "Надіслати огляд календаря релізів",
    "update_forecasts": "Оновити прогноз показника після нового релізу",
    "notify_forecasts": "Надіслати наш прогноз наступних значень показників",
    "compare_expectations": "Порівняти факт з ринковим очікуванням",
    "synthesize_expectations": "LLM-висновок про сюрприз факт/очікування",
    "notify_expectations": "Надіслати сюрприз факт/очікування",
    "notify_release_impact": "Надіслати розбір впливу релізу на інші активи",
    "news_collect_watchlist": "Зібрати новини по watchlist-активах (GDELT)",
    "news_collect_general": "Зібрати загальні ринкові новини (GDELT)",
    "news_collect_rss": "Зібрати геополітичні новини (RSS Fed/ECB/BOJ + редакційні)",
    "news_collect_stock": "Зібрати новини по тикерах зі скринінгу (GDELT)",
    "news_analysis_watchlist": "DeepSeek-аналіз новин watchlist",
    "news_analysis_geopolitical": "DeepSeek-аналіз геополітичних новин",
    "news_analysis_general": "DeepSeek-аналіз загальних новин",
    "news_consolidate_watchlist": "Об'єднати дублі та перекласти новини watchlist",
    "news_consolidate_general": "Об'єднати дублі та перекласти загальні новини",
    "news_consolidate_geopolitical": "Об'єднати дублі та перекласти геополітичні новини",
    "news_merge_similar": "Об'єднати семантичні дублі новин між прогонами",
    "news_notify": "Надіслати найважливіші новини",
    "news_synthesis": "LLM-синтез причинного зв'язку ціна↔новини",
    "notify_synthesis": "Надіслати синтез ціна↔новини",
    "market_synthesis_asia": "Стан ринку після відкриття азіатської сесії",
    "market_synthesis_europe": "Стан ринку після відкриття європейської сесії",
    "market_synthesis_us": "Стан ринку після відкриття американської сесії",
    "notify_market_synthesis": "Надіслати стан ринку",
    "fundamental_analysis": "Фундаментальний ШІ-аналіз звітності топ-акцій",
    "notify_fundamental": "Надіслати фундаментальний аналіз акцій",
    "discover_candidates": "LLM-пошук нових перспективних акцій у новинах",
    "notify_candidates": "Надіслати нових кандидатів-новачків",
    "daily_digest": "Щоденний дайджест найважливішого за добу",
    "crypto_prices": "Зібрати ціни BTC/ETH/SOL (Binance+CoinGecko)",
    "crypto_derivatives_collect": "Зібрати дані ф'ючерсів (Binance+Bybit+OKX)",
    "crypto_screening_daily": "Крипто-скринінг LONG/SHORT/WATCH (денний скан)",
    "crypto_candidates_monitor": "Погодинний моніторинг активних крипто-кандидатів",
    "watchlist_prices": "Зібрати ціни форекс/товарів watchlist (FRED/Twelve Data)",
    "quotes_universe_refresh": "Оновити ціни всього S&P 500 (Twelve Data)",
    "screening_composite_score": "Скринінг акцій S&P 500 (Tier A→B→C + ранжування)",
    "notify_screening": "Надіслати скринінг S&P 500",
    "notify_crypto_screening": "Надіслати крипто-кандидатів SHORT/WATCH",
    "trading_list": "Скласти список активів для розгляду (фільтр за каталізатором)",
    "notify_trading_list": "Надіслати список активів для розгляду",
    "notify_crypto_long": "Надіслати крипто-кандидатів LONG",
    "notify_watchlist": "Надіслати поточні ціни watchlist-активів",
    "companies_universe_refresh": "Оновити фундаментал усього S&P 500 (SEC EDGAR)",
    "macro_daily_series": "Зібрати денні макро-серії (облігації, ставка ФРС, USD/JPY)",
    "forecast_daily_series": "Прогноз денних серій (облігації, ставка ФРС, USD/JPY)",
    "safety_net_collect_all": "Страховий щомісячний перезбір усіх показників",
    "prune_logs": "Прибрати старі файли логів (понад 14 днів)",
    "prune_raw_news": "Прибрати старі новини з БД (понад 48г)",
    "scheduler_heartbeat": "Записати пульс планувальника (діагностика простою)",
    "telegram_commands": "Опитати Telegram і виконати нові команди",
}

# Команди редагування watchlist (2026-10-03, docs/decisions.md) — НЕ
# джоби з JOBS (своя гілка в telegram_commands.py:process_update()),
# але так само потребують назви+опису в "/"-меню Telegram і на /help.
SPECIAL_COMMAND_DESCRIPTIONS: dict[str, str] = {
    "watchlist_list": "Показати поточний watchlist",
    "watchlist_add": "Додати актив у watchlist (пробує Twelve Data, потім Binance)",
    "watchlist_remove": "Вимкнути актив з watchlist",
}

# Підмножина JOB_DESCRIPTIONS, видима й виконувана через Telegram
# (2026-10-03, рішення користувача: "забери всі технічні джоби з меню,
# лиши тільки для отримання інформації"). Решта 32 джоб (збір даних,
# промiжні кроки конвеєра, обслуговування) і далі працюють за
# розкладом (orchestration/schedule.py) без змін — просто більше не
# запускаються вручну з Telegram; ручний запуск лишається через
# `docker compose exec app python orchestration/run_job.py <назва>`.
# Критерій — джоба сама НАДСИЛАЄ користувачу інформацію (notify_*/
# daily_digest), не промiжний крок конвеєра (збір/аналіз/скринінг без
# доставки).
INFO_JOB_NAMES: frozenset[str] = frozenset({
    "notify_calendar_outlook",
    "notify_expectations",
    "notify_forecasts",
    "notify_release_impact",
    "news_notify",
    "notify_synthesis",
    "notify_market_synthesis",
    "notify_candidates",
    "daily_digest",
    "notify_screening",
    "notify_crypto_screening",
    "notify_crypto_long",
    "notify_trading_list",
    "notify_fundamental",
    "notify_watchlist",
})
