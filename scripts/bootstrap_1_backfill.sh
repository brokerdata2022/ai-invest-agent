#!/usr/bin/env bash
# Крок 1 з 2 повного розгортання з нуля (README.md "Перший запуск з
# чистими даними"). Піднімає застосунок, застосовує схему, і запускає
# у ФОНІ три одноразові масові backfill'и, без яких скринінг/синтез
# не мають даних, хоча код і тести коректні (docs/decisions.md,
# 2026-09-27 — жива перевірка "з нуля" на новому Docker Engine
# показала саме цю прогалину, не гіпотетичну).
#
# Twelve Data (collect_universe.py) — ~500 тикерів S&P 500, ліміт
# 8 запитів/хв ⇒ ~65 хв. Це НАЙДОВША частина — решта значно швидша.
#
# Використання:
#   bash scripts/bootstrap_1_backfill.sh
# Далі перевіряйте прогрес (нижче), і коли всі три логи покажуть
# "Готово" — запустіть scripts/bootstrap_2_pipeline.sh.

set -e

echo "== 1/4: піднімаємо контейнери =="
docker compose up -d --build

echo "== 2/4: застосовуємо схему БД =="
docker compose exec app python data-ingestion/apply_schema.py

echo "== 3/4: тести коду (НЕ перевіряють наявність даних, лише код) =="
docker compose exec app pytest -q

echo "== 4/4: запускаємо три одноразові backfill'и у фоні =="
docker compose exec -d app sh -c "python data-ingestion/collect_universe.py > logs/bootstrap_quotes_universe.log 2>&1"
docker compose exec -d app sh -c "python data-ingestion/collect_companies_universe.py > logs/bootstrap_companies_universe.log 2>&1"
docker compose exec -d app sh -c "python data-ingestion/collect_all.py --limit 15 > logs/bootstrap_collect_all.log 2>&1"

cat <<'EOF'

Фонові backfill'и запущено (~1 год, здебільшого через ліміт Twelve Data).

Перевірити прогрес:
  docker compose exec app tail -f logs/bootstrap_quotes_universe.log
  docker compose exec app tail -f logs/bootstrap_companies_universe.log
  docker compose exec app tail -f logs/bootstrap_collect_all.log

Перевірити завершення (collect_universe/collect_companies_universe
закінчуються рядком "Готово: N успішно...", collect_all — блоком
"--- Підсумок ---"):
  docker compose exec app sh -c 'tail -n 5 logs/bootstrap_*.log'

Коли всі три завершились — запустіть:
  bash scripts/bootstrap_2_pipeline.sh
EOF
