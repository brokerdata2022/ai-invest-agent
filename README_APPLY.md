# Як застосувати Tier C + Composite score

Ці файли готуються НОВІ (працюють поверх вже наявних у твоєму репо
tier_a.py / tier_b.py, нічого в них не змінюють):

1. `analysis/screening/tier_c.py` — новий файл, скопіювати як є.
   (підтверджено живо: 16 з 35 пройшли)
2. `analysis/screening/composite_score.py` — новий файл, скопіювати як є.
   Ранжує тикери, що пройшли Tier C, за формулою з docs/screening-criteria.md.
3. `analysis/tests/test_tier_c.py` — 19 тестів чистої логіки.
4. `analysis/tests/test_composite_score.py` — 7 тестів percentile_ranks().

Ці — фрагменти для дописування вручну (я не бачу актуальний вміст
твоїх decisions.md/PLAN.md в цій сесії, тому не хочу перезаписувати
їх наосліп):

5. `docs/decisions_tier_c_append.md` — додати вміст в кінець
   `docs/decisions.md`.
6. `docs/plan_session_append.md` — додати вміст в кінець `PLAN.md`
   (містить записи і про Tier C, і про composite score).

## Перевірка

```
docker compose exec app python -m pytest analysis/tests/test_tier_c.py analysis/tests/test_composite_score.py -v
docker compose exec app python analysis/screening/composite_score.py --top 10
```

`--top N` опційний — за замовчуванням виводить усіх, хто пройшов
Tier C (зараз 16), відсортованих за score. Скільки з верху брати для
реальних торгів — рішення поза кодом.

## Важливо: перевір узгодження полів

`composite_score.py` намагається знайти на `TierAResult`/`TierBResult`
кілька можливих назв полів (`avg_dollar_volume`/`avg_volume`,
`revenue_yoy`/`revenue_growth_yoy`/`revenue_growth`,
`eps_yoy`/`eps_growth_yoy`/`eps_growth`) — це страховка від того, що я
відтворював ці інтерфейси з опису сесії (оригінальні tier_a.py/tier_b.py
в мене тут втрачені при скиданні контексту, хоча в твоєму репо вони
незмінні й робочі). Якщо жодна назва не підійде, скрипт сам залогує
`WARNING` з переліком РЕАЛЬНИХ полів об'єкта (`vars(a)`/`vars(b)`) і
пропустить тикер замість падіння — просто скинь мені цей лог, і я
поправлю назви одним рядком.

`tier_c.py` (без змін від попереднього разу) очікує:
- `run_tier_a() -> list[TierAResult]` з полями `ticker`, `price`, `market_cap`
- `run_tier_b() -> list[TierBResult]` (без параметрів) з полями `ticker`, `eps_yoy`
- `_series(conn, source, metric_id)` в `tier_b.py`
