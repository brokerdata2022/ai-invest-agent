# Статус проєкту

Одна сторінка "де ми зараз" — заміняє розкидані по PLAN.md/decisions.md
записи "наступна сесія починає звідси". Оновлюється після кожної
завершеної сесії. Детальний план по фазах — `PLAN.md`, обґрунтування
рішень — `docs/decisions.md`, повний журнал сесій — `docs/archive/`.

## Що працює живо (підтверджено реальними прогонами)

### Збір даних (data-ingestion/)
| Джерело | Адаптер | Що збирає | Статус |
|---|---|---|---|
| FRED | `macro/fred_adapter.py` | CPI, Core CPI, PCE, Fed Funds Rate, 10Y/2Y Treasury, Jobless Claims, GDP, Retail Sales, USD/JPY, і ін. (США) | ✅ живо |
| ECB Data Portal | `macro/ecb_adapter.py` | HICP, Deposit Rate, Unemployment (єврозона) | ✅ живо |
| BOJ | `macro/boj_adapter.py` | Policy Rate (Японія) | ✅ живо |
| e-Stat | `macro/estat_adapter.py` | CPI (Японія) | ✅ живо |
| SEC EDGAR | `companies/sec_edgar_adapter.py` | revenue/EPS/shares/assets/liabilities, S&P 500 (500/503 компаній) | ✅ живо |
| Twelve Data | `quotes/twelvedata_adapter.py` | ціна/обсяг акцій | ✅ живо |

### Скринінг акцій (analysis/screening/) — воронка Tier A → B → C → ранжування
Критерії — `docs/screening-criteria.md`. Universe — S&P 500 (constituents.csv).

| Крок | Що фільтрує | Живий результат |
|---|---|---|
| Tier A | ліквідність (ціна >$10, капіталізація >$10 млрд, $ обсяг >$10 млн/день) | 411 / 491 пройшли (2026-09-25, актуальні ціни — цифра рухається з ринком, не константа) |
| Tier B | фундаментал (прибутковість, revenue/EPS YoY, дилюція, L/A) | 35 / 411 пройшли |
| Tier C | valuation (P/E, P/S, PEG) | 16 / 35 пройшли |
| Composite score | ранжування пройшли-Tier-C за формулою (не фільтр) | 16 ранжованих, топ-10 показано |

**Продуктивність (виправлено 2026-09-25):** до фіксу N+1-запитів сам
Tier A займав ~9.5 хв на 491 тикер. Після фіксу — весь ланцюжок
Tier A→B→C→ранжування виконується за ~7 секунд (підтверджено живим
прогоном користувача, `composite_score.py --top 10`, числа збіглися:
411/35/16 — фікс не змінив результат, тільки швидкість). Причина й
деталі фіксу — `docs/decisions.md`, 2026-09-25.

**Топ-10 кандидатів (живий прогін 2026-09-25):** FANG, COP, HPE, IVZ,
UBER, BX, STLD, HAL, MDT, CASY (score/деталі — вивід
`composite_score.py --top 10`, не зберігається в БД, тільки друкується).

Тести: 113/113 до фіксу N+1 (`docker compose exec app pytest -q`) —
67 data-ingestion/reporting + 46 analysis/screening; +4 нові на
`avg_dollar_volume_from_series` (117 очікується, ще не підтверджено
живим прогоном pytest).

### Новини (news/, GDELT + DeepSeek) — watchlist-потік підтверджено живо
3 потоки (watchlist/general/geopolitical, обсяг — `docs/decisions.md`
2026-09-25 "news/ — обсяг, межа шарів і схема БД"), поки реалізовано
тільки watchlist, і тільки не-акційна частина (`docs/watchlist.md`):

| Крок | Модуль | Статус |
|---|---|---|
| Збір (GDELT) | `data-ingestion/news/gdelt_adapter.py` + `queries.py` | ✅ живо, 75 статей у `raw_news` (2026-09-25) |
| Аналіз (DeepSeek) | `analysis/news_analysis/` (deepseek_client/relevance_filter/_db) | ✅ живо, коректний структурований JSON на 5/5 статей |
| Сповіщення (Telegram) | `reporting/news_notify.py` | ✅ живо, 4 релевантні з 5 надіслано в Telegram (2026-09-25) |

**Не зроблено:** query для акцій зі скринінгу (watchlist-потік для
S&P 500 тикерів), general/geopolitical потоки (RSS-адаптер), і
`--tracked-assets` для watchlist ще не проставляється автоматично зі
списку `docs/watchlist.md` — тому `asset_id` у `news_analysis` поки
завжди `None` (DeepSeek не має з чим зіставляти).

## Що не зроблено (по фазах PLAN.md)

- **Фаза 1:** календар релізів (для Фази 3) — не побудовано. news/
  (GDELT) — watchlist-потік (не-акційна частина) живо підтверджено
  вище; акції зі скринінгу, general/geopolitical потоки, RSS-адаптер
  — ще ні.
- **Фаза 2:** ринкові очікування, порівняння факт/очікування — не
  почато. LLM-аналіз новин — перший робочий зріз є (watchlist-потік,
  вище), детерміноване порівняння факт/очікування — окреме, ще не
  почате (screening-трек вище — паралельна робота, інший вид аналізу)
- **Фаза 3:** моніторинг/тригери — не почато
- **Фаза 4:** формат регулярного звіту (email/dashboard/файл) — не
  вирішено; список активів поза акціями (крипто/форекс/товари) — тільки
  watchlist, немає ні збору даних, ні скринінгу

## Відкриті другорядні питання (не блокуючі)

- `shares_outstanding` відсутній для ~110/501 компаній S&P 500 (SEC
  повертає порожній `units.shares` — ймовірно компанії з кількома
  класами акцій); можливий fallback-тег `CommonStockSharesOutstanding`
  без `dei` — не зроблено, не блокує (365/491 — робочий результат)
`docs/watchlist.md` — усі відкриті питання (крипто-монети, нафта,
"пріоритет 2") закриті 2026-09-25 (docs/decisions.md).

## Наступний змістовний крок

news/ у процесі (watchlist-потік живо підтверджено, вище). Далі —
на вибір користувача, не техпріоритет:
1. **Розширити news/** — query для акцій зі скринінгу, `--tracked-assets`
   з `docs/watchlist.md` (щоб `asset_id` не був завжди `None`),
   general/geopolitical потоки, RSS-адаптер.
2. **monitoring/** — календар релізів + тригери на нові дані (Фаза 1
   хвіст + Фаза 3 старт), поки не почато.
