# Статус проєкту

Одна сторінка "де ми зараз". Оновлюється після кожної завершеної сесії.

- Що потрібно для продакшену, пріоритезовано — **`docs/production-readiness.md`**
- Фази й чекбокси — `PLAN.md`
- Чому кожне рішення таке — `docs/decisions.md`
- Повний покроковий журнал сесій (як усе дійшло до цього стану) —
  `docs/archive/status-journal-2026-09-27.md`, `docs/archive/plan-journal-2026-08-09.md`

**Останній аудит:** 2026-09-27 — оптимізація коду (−480 рядків
дублювання, `analysis/llm_common.py` + `reporting/_common.py`), ротація
`logs/`, прив'язка порту БД до 127.0.0.1, реорганізація документації.
Деталі — `docs/decisions.md`, прогалини — `docs/production-readiness.md`.

---

## Збір даних (`data-ingestion/`) — 10 адаптерів, усі живо підтверджені

| Джерело | Адаптер | Що збирає |
|---|---|---|
| FRED | `macro/fred_adapter.py` | CPI, Core CPI, PCE, Fed Funds, 10Y/2Y Treasury, Jobless Claims, GDP, Retail Sales, Housing Starts, Mortgage 30Y, NFP, Unemployment, EUR/USD, USD/JPY, WTI/Brent, кава (США) |
| ECB Data Portal | `macro/ecb_adapter.py` | HICP, Deposit Rate, Unemployment (єврозона) |
| BOJ | `macro/boj_adapter.py` | Policy Rate (Японія) |
| e-Stat | `macro/estat_adapter.py` | CPI (Японія) |
| SEC EDGAR | `companies/sec_edgar_adapter.py` | revenue/EPS/shares/assets/liabilities, 500/503 компаній S&P 500 |
| Twelve Data | `quotes/twelvedata_adapter.py` | ціна/обсяг акцій, золото (XAU/USD) |
| Binance | `crypto/binance_adapter.py` | ціна/обсяг BTC/ETH/SOL |
| CoinGecko | `crypto/coingecko_adapter.py` | market cap BTC/ETH/SOL + срібло (проксі kinesis-silver, ⚠️ без живого прогону) |
| GDELT | `news/gdelt_adapter.py` | новини, потоки watchlist/general |
| RSS (9 фідів) | `news/rss_adapter.py` | Fed/ECB/BOJ + BBC/Al Jazeera/Guardian/NPR/Sky News/DW, потік geopolitical |

Watchlist активів — `docs/watchlist.md`, каталог metric_id —
`docs/metrics-catalog.md`.

## Аналіз (`analysis/`)

| Напрям | Модулі | Стан |
|---|---|---|
| Скринінг акцій | `screening/` — Tier A→B→C + composite score, `screening_results` | ✅ живо: 411 → 35 → 16 тикерів (цифри рухаються з ринком) |
| Новини: класифікація | `news_analysis/relevance_filter.py` | ✅ живо, усі 3 потоки |
| Новини: агрегація | `news_analysis/aggregate.py` — кластери дублікатів, зведення по активу | ✅ живо |
| LLM-синтез ціна↔новини (Цілі 1, 2) | `news_analysis/synthesize.py` | ✅ живо |
| LLM-синтез стану ринку (Ціль 4) | `news_analysis/synthesize_market.py` | ✅ живо, risk-off 0.55 |
| LLM-відбір нових активів (Ціль 3) | `news_analysis/discover_candidates.py` | ⚠️ код готовий, реального кандидата ще не знайдено (IPO-шум у `GENERAL_TERMS`) |
| Факт vs очікування | `expectations/` — 5 методів, `expectation_comparisons` | ⚠️ чекає справжнього релізу |
| LLM-синтез сюрпризу | `expectations/synthesize.py` | ✅ на синтетичному релізі; справжній — чекає |
| **Прогнозування** | `forecasting/` — лінійна регресія + backtest | 🔴 **1 показник із 15, перевага над naive 0.7% (шум), назовні не виходить** — головна незакрита задача, `docs/production-readiness.md` |

Спільна LLM-проводка (провайдер, розбір відповіді, аудит-лог) —
`analysis/llm_common.py`. Провайдер перемикається однією змінною
`SYNTHESIS_LLM_PROVIDER`; зараз DeepSeek, Anthropic — свідомо пізніше.

## Моніторинг (`monitoring/`) — календар релізів, 15 показників

Двофазно: `refresh_calendar.py` (тижнево, заводить `pending` наперед)
→ `check_releases.py` (кожні 15 хв, активно тригерить збір після
настання часу + буфер). Джерело дати: FRED `/release/dates` для 10
US-показників, ForexFactory-фід для 5 EUR/JPY (для US — збагачення
точним часом/impact/forecast).

- ✅ `refresh_calendar` — живо, повний 15-показниковий прогін.
- ⚠️ `check_releases` — реального забору за розкладом ще **не
  спостерігали**: найближчі релізи 30.09–02.10.

Неперервні щоденні ряди (ставки/дохідності/FX/commodity) навмисно не
покриті — у них немає "події релізу".

## Звітність (`reporting/`)

7 Telegram-сценаріїв: останнє значення показника, релевантні новини,
синтез ціна/новини, стан ринку, кандидати-новачки, сюрприз
факт/очікування, щоденний дайджест (`daily_digest.py`, без нового
LLM-виклику). Спільний бойлерплейт — `reporting/_common.py`.

⚠️ Захист від повторів (`notified_at`) є лише в `expectations_notify.py`
— решта завжди шле "останній стан", тобто може повторюватись
(`docs/production-readiness.md`, P1 №6).

## Оркестрація (`orchestration/`)

APScheduler у сервісі `scheduler` (docker compose, `restart:
unless-stopped`), 28 джоб, часовий пояс Europe/Kyiv. Розклад —
`orchestration/schedule.py` (єдиний файл для зміни періодичності),
реєстр "що виконати" — `jobs.py`. Провал джоби (ненульовий exit,
timeout, виняток) → Telegram-алерт; успіх → лише файл у `logs/`.
Логи прибираються джобою `prune_logs` (14 днів).

⚠️ Живість самого планувальника ніхто не контролює: якщо контейнер у
crash-loop, алертів не буде взагалі (`docs/production-readiness.md`,
P0 №3).

## Тести

375 проходять — усі на фікстурах/monkeypatch, без мережі й без реальної
БД:

```bash
docker compose exec app pytest -q
```

Тести перевіряють **код**, не наявність даних: на свіжій БД вони
проходять, а скринінг/синтез/дайджест нічого не покажуть, доки не
виконано bootstrap (`README.md`, "Перший запуск з чистими даними").

## Відкриті другорядні питання (не блокують)

- `shares_outstanding` відсутній для ~110/501 компаній S&P 500 (SEC
  віддає порожній `units.shares` — ймовірно компанії з кількома класами
  акцій). 365/491 — робочий результат.
- GDELT віддає 429 при інтенсивному використанні (спільний вихідний IP);
  адаптер має retry з backoff, дедуп робить повтор безпечним.
- Ціни нових тикерів зі скринінгу накопичуються природно — для % зміни
  одразу потрібен був би backfill при появі тикера в `screening_results`.

## Наступний змістовний крок

1. **Прогнозування** — backtest решти 14 показників і вивід прогнозу
   назовні (PLAN.md Фаза 2, єдиний незакритий чекбокс).
2. **Бекап БД** — джоба `pg_dump` (P0, суперечність із критичним
   правилом №6).
3. **Heartbeat планувальника** (P0).
4. Живий прогін ланки реліз → порівняння → синтез → сповіщення на
   справжньому релізі 30.09–02.10.

Повний пріоритезований список — `docs/production-readiness.md`.
