#!/usr/bin/env bash
# Крок 2 з 2 повного розгортання з нуля — запускайте ЛИШЕ ПІСЛЯ того,
# як усі три backfill'и з scripts/bootstrap_1_backfill.sh завершились
# (без них screening/synthesize не матимуть даних).
#
# Прогонить увесь конвеєр ОДИН РАЗ, у порядку залежностей, через
# orchestration/run_job.py — той самий код, що виконує планувальник
# автоматично (docker-compose сервіс scheduler), тож це не "інший
# шлях для ручного тесту", а справжня перевірка продакшн-автоматизації.
#
# Використання:
#   bash scripts/bootstrap_2_pipeline.sh

set -e

run() {
    echo "== $1 =="
    docker compose exec app python orchestration/run_job.py "$1"
}

echo "--- Скринінг (Tier A/B/C, потребує свіжий universe з кроку 1) ---"
run screening_composite_score

echo "--- Збір новин (усі потоки) ---"
run news_collect_watchlist
run news_collect_stock
run news_collect_general
run news_collect_rss

echo "--- Ціни (watchlist-товари/форекс/золото + весь S&P 500 universe) ---"
run watchlist_prices
run quotes_universe_refresh

echo "--- DeepSeek-класифікація зібраних новин ---"
run news_analysis_watchlist
run news_analysis_general
run news_analysis_geopolitical

echo "--- LLM-синтез (Цілі 1/2/3/4, docs/news-purpose.md) ---"
run news_synthesis
run market_synthesis
run discover_candidates

echo "--- Щоденний дайджест (Ціль 5) ---"
run daily_digest

cat <<'EOF'

Готово. Увесь конвеєр прогнано один раз вручну й підтверджено робочим.
Далі сервіс scheduler (docker compose ps) продовжує сам за розкладом
orchestration/schedule.py — жодних ручних кроків більше не потрібно.
EOF
