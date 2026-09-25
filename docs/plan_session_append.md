
## Сесія N+1: Tier C скринінгу (valuation)

**Зроблено:**
- `analysis/screening/tier_c.py` — третій рівень hard-фільтрів (P/E, P/S, PEG),
  TTM з останніх 4 кварталів, PEG використовує `eps_yoy` з Tier B (без
  повторного рахунку зростання).
- `analysis/tests/test_tier_c.py` — 19 тестів чистої логіки (`ttm_sum`,
  `passes_tier_c`), усі межові випадки й None-пропуски, без БД.
- `docs/decisions.md` — запис про рішення (TTM-логіка, повторне
  використання `eps_yoy` з Tier B, рання зупинка деталей).

**Як запустити:**
```
docker compose exec app python -m pytest analysis/tests/test_tier_c.py -v
docker compose exec app python analysis/screening/tier_c.py
```

**Наступна сесія починає звідси:** усі три рівні hard-фільтрів (Tier A —
ліквідність, Tier B — фундаментал, Tier C — valuation) реалізовані й
живо підтверджені (Tier A: 365-411 з ~491-501, Tier B: 35 з 411; Tier C —
чекає на живий прогін користувача). Наступний крок — composite score
(формула вже в `docs/screening-criteria.md`:
`score = 0.35×percentile(revenue_growth) + 0.30×percentile(eps_growth) +
0.20×percentile(-P/E) + 0.15×percentile(avg_dollar_volume)`), який
ранжує тикери, що пройшли Tier C, і відбирає фінальний топ-10 список
кандидатів для торгів.

Відкриті другорядні питання (не блокуючі): watchlist.md пріоритет 2
(загальні активи для news/), конкретні крипто-монети (BTC+ETH —
припущення, не підтверджено), WTI vs Brent для нафти, shares_outstanding
пробіл для ~63-110 компаній S&P 500 (можливий fallback-тег
`CommonStockSharesOutstanding` без `dei` у майбутньому).

## Сесія N+2: Composite score (фінальне ранжування)

**Зроблено:**
- `analysis/screening/composite_score.py` — ранжує тикери, що пройшли
  Tier A → Tier B → Tier C, за формулою:
  `score = 0.35×percentile(revenue_growth) + 0.30×percentile(eps_growth)
  + 0.20×percentile(-P/E) + 0.15×percentile(avg_dollar_volume)`.
  Percentile рахується ВСЕРЕДИНІ списку тикерів, що пройшли Tier C (не
  відносно всього S&P 500) — порівнюємо вже відфільтрованих кандидатів
  між собою.
- Це не ще один hard-фільтр — нічого не відсіює, тільки сортує.
  `run_composite_score()` повертає повний ранжований список;
  `--top N` в CLI лише обрізає вивід (кількість кандидатів для торгів
  свідомо не захардкожена як рівно 10 — може бути більше або менше).
- `analysis/tests/test_composite_score.py` — 7 тестів чистої функції
  `percentile_ranks()` (базовий випадок, однакове значення, tie-обробка
  середнім рангом, інверсія для -P/E), без БД.

**Як запустити:**
```
docker compose exec app python -m pytest analysis/tests/test_composite_score.py -v
docker compose exec app python analysis/screening/composite_score.py --top 10
```

**Наступна сесія починає звідси:** усі три рівні hard-фільтрів і
фінальне ранжування реалізовані й (Tier A/B/C) живо підтверджені.
Composite score чекає на живий прогін. Після підтвердження —
відкриті другорядні питання: watchlist.md пріоритет 2, крипто-монети
(BTC+ETH — припущення), WTI vs Brent, shares_outstanding пробіл
(~63 компанії S&P 500), і питання reporting/monitoring (поза межами
поточних сесій за архітектурою проєкту).
