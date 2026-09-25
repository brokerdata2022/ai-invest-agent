
## Сесія N: Tier C скринінгу (valuation)

**Рішення:** реалізовано третій (останній) рівень hard-фільтрів скринінгу
в `analysis/screening/tier_c.py`, за критеріями з `docs/screening-criteria.md`:

- P/E (price / TTM EPS) в діапазоні (10, 35), межі виключно
- P/S (market cap / TTM revenue) < 8
- PEG (P/E / (eps_growth_yoy * 100)) < 2

**TTM:** сума останніх 4 квартальних значень (не останнє квартальне
значення), обчислюється чистою функцією `ttm_sum()`, яка бере вже
відсортовану спаданням дати серію (той самий формат, що повертає
`_series()` з `tier_b.py`) і повертає `None`, якщо історії < 4 кварталів
(немає штучного заповнення — тикер просто не пройде через `eps_ttm is None`).

**PEG не рахує зростання EPS повторно.** `eps_growth_yoy` береться напряму
з результату Tier B (`TierBResult.eps_yoy`), який вже обчислений і
провалідований (>= 15% YoY) на попередньому рівні — уникнення дублювання
логіки й повторних SQL-запитів.

**Архітектура функції:** `passes_tier_c()` — чиста функція (як
`passes_tier_a`/`passes_tier_b`), приймає вже обчислені price, market_cap,
eps_ttm, revenue_ttm, eps_growth_yoy і повертає `(bool, dict)` з ранньою
зупинкою на першому провальному критерії — деталі (`pe`, `ps`, `peg`)
накопичуються тільки до точки провалу, так само як у Tier B.

`run_tier_c(tier_a_results=None, tier_b_results=None)` — SQL-шар:
об'єднує `TierAResult` (price, market_cap) і `TierBResult` (eps_yoy) по
тикеру, для кожного тикера з Tier B бере `eps_series`/`revenue_series`
через `_series()` з `tier_b.py` (без дублювання логіки читання з БД),
рахує TTM і викликає `passes_tier_c()`.

**Тестування:** 19 тестів чистої логіки (`ttm_sum`, `passes_tier_c`) без
БД, за зразком `test_tier_a.py`/`test_tier_b.py` — усі межові випадки
(P/E/P/S/PEG рівно на межі — не проходять, виключно `<`/`>`), відсутні
або від'ємні вхідні дані (None-пропуски компонентів), рання зупинка
деталей. Імпорти `common.db`/`screening.tier_a`/`screening.tier_b`
зроблені лаконічно всередині `run_tier_c()`, а не на рівні модуля — це
дозволяє тестувати `ttm_sum()`/`passes_tier_c()` без БД і без залежності
від наявності `tier_a.py`/`tier_b.py` в шляху імпорту.

**Наступний крок:** composite score (формула вже визначена в
`docs/screening-criteria.md`) → фінальний топ-10 список кандидатів з
результатів, що пройшли всі три рівні (Tier A → Tier B → Tier C).
