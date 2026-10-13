#!/usr/bin/env bash
#
# Перезбирає продакшен-копію в production/ з поточного стану дев-репо.
#
# production/ — ОКРЕМИЙ git-репозиторій зі власним origin (у .gitignore
# цього). Скрипт синхронізує туди КОД і docs/, не торкаючись ні
# продакшен-документації, ні .git, ні резерву БД — тож після нього
# достатньо `git -C production add -A && git -C production commit`.
#
# Використання:
#   bash scripts/build_production.sh              # код + docs
#   bash scripts/build_production.sh --with-db    # і перезняти резерв БД
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
DEV_ROOT="$PWD"
PROD="$DEV_ROOT/production"

WITH_DB=0
[ "${1:-}" = "--with-db" ] && WITH_DB=1

echo "→ Збірка продакшен-копії: $PROD"
echo

# ─── Що НЕ йде в продакшен ─────────────────────────────────────────
#
# Файли продакшен-документації й скриптів резерву НЕ перелічені тут —
# вони живуть ЛИШЕ в production/ і цього дерева не мають. rsync без
# --delete їх не зачепить, бо нема чим перекрити. Саме тому тут немає
# --delete: він знищив би їх при кожній збірці.
EXCLUDES=(
  --exclude='.git/'              # у production/ свій
  --exclude='production/'        # не копіювати себе в себе
  --exclude='logs/'              # раннтайм-вивід, у контейнері наново
  --exclude='__pycache__/'
  --exclude='*.pyc'
  --exclude='.pytest_cache/'
  --exclude='.vscode/'           # налаштування IDE розробника
  --exclude='.claude/'           # інструменти сесій розробки
  --exclude='.env'               # СЕКРЕТИ
  --exclude='backup.sql'         # локальні дампи
  --exclude='backup_*.sql'
  --exclude='CLAUDE.md'          # інструкції для сесій розробки
  --exclude='PLAN.md'            # план розробки
  --exclude='README.md'          # у production/ свій README
  --exclude='.gitignore'         # у production/ свій
  --exclude='docs/archive/'      # журнали закритих фаз
  --exclude='production-notes/'  # тексти позначок, потрібні лише тут
  --exclude='build_production.sh' # продакшен себе не збирає
)

rsync -a "${EXCLUDES[@]}" "$DEV_ROOT/" "$PROD/"
echo "  · код і docs/ синхронізовано"

# ─── Позначки на перенесених docs/ ─────────────────────────────────
#
# decisions.md / architecture.md / trading-list.md посилаються на
# CLAUDE.md, PLAN.md і docs/archive/, яких у продакшені немає. Текст
# журналу НЕ переписуємо (це запис, а не опис стану) — додаємо
# позначку, що ці посилання ведуть у дев-репо.
#
# Самі тексти — у scripts/production-notes/, а НЕ в цьому скрипті.
# Перша версія тримала їх тут і писала поверх файлу після кожного
# rsync: будь-яка продакшен-правка в перенесеному docs/ тихо
# знищувалась наступною перезбіркою — так загинув вимір, що виправляв
# застарілу оцінку в trading-list.md.
NOTED=(decisions.md architecture.md trading-list.md)
NOTES_DIR="$DEV_ROOT/scripts/production-notes"

for name in "${NOTED[@]}"; do
  target="$PROD/docs/$name"
  [ -f "$target" ] || continue
  grep -q 'Позначка продакшен-версії' "$target" && continue

  note="$NOTES_DIR/$name"
  [ -f "$note" ] || note="$NOTES_DIR/_default.md"
  [ -f "$note" ] || { echo "❌ Немає тексту позначки: $note"; exit 1; }

  # Перший рядок файлу мусить бути заголовком — позначка йде ПІСЛЯ
  # нього, щоб назва лишалась першим, що видно.
  case "$(head -1 "$target")" in
    '# '*) ;;
    *) echo "❌ docs/$name: перший рядок не заголовок '# ...'"; exit 1 ;;
  esac

  tmp="$(mktemp)"
  { head -1 "$target"; echo; cat "$note"; echo; tail -n +2 "$target"; } > "$tmp"
  mv "$tmp" "$target"
  echo "  · позначено docs/$name ($(basename "$note"))"
done

# ─── Резерв БД ─────────────────────────────────────────────────────
if [ "$WITH_DB" -eq 1 ]; then
  echo
  echo "→ Перезняття резерву БД із дев-бази"
  COMPOSE_DIR="$DEV_ROOT" bash "$PROD/scripts/backup_db.sh"
else
  echo "  · резерв БД НЕ перезнімався (--with-db, щоб перезняти)"
  BK="$PROD/db/backup/invest_agent_data.sql.gz"
  [ -f "$BK" ] && echo "    поточний: $(du -h "$BK" | cut -f1), від $(date -r "$BK" +%F)"
fi

# ─── Перевірка ─────────────────────────────────────────────────────
echo
echo "→ Перевірка продакшен-копії"

# Питання не "що лежить на диску", а "що потрапить у КОМІТ". Різниця
# не теоретична: якщо продакшен-копію хоч раз запустити локально
# (docker compose up у production/ — саме так перевіряється
# розгортання), там зʼявляться .env і __pycache__. Вони в .gitignore
# продакшену, тобто нешкідливі — а перевірка "по find" падала б на
# них щоразу й привчала б ігнорувати власний ❌.
LEAKS=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  git -C "$PROD" check-ignore -q "$f" 2>/dev/null && continue  # у .gitignore — ок
  LEAKS="$LEAKS$f"$'\n'
done <<EOF
$(cd "$PROD" && find . -not -path './.git/*' \
  \( -name 'CLAUDE.md' -o -name 'PLAN.md' -o -name '.env' -o -name '*.key' \
     -o -name 'backup.sql' -o -name 'backup_*.sql' -o -name '*.pyc' \
     -o -name '__pycache__' -o -path './docs/archive*' \
     -o -path './.vscode*' -o -path './.claude*' \) -print)
EOF
if [ -n "${LEAKS//[$'\n']/}" ]; then
  echo "❌ У продакшен-КОМІТ потрапило б зайве (і це НЕ в .gitignore):"
  printf '%s' "$LEAKS" | sed 's/^/     /'
  exit 1
fi
echo "  · дев-артефактів і секретів немає"

# Код мусить бути ПОБАЙТОВО тим самим. Перевірка сильніша за прогін
# тестів: збірка Python-файли не редагує, тож будь-яка розбіжність тут
# означає, що rsync чогось не доніс.
#
# Порівнюємо МАНІФЕСТ контрольних сум, а не `diff -rq`: у diff
# --exclude збігається лише з базовим іменем (патерн ".git/" зі слешем
# не матчиться взагалі), а його вивід ще й локалізований — фільтрувати
# його грепом ненадійно. Перша версія цієї перевірки через diff саме
# через це молча пропускала все й "проходила" завжди.
_manifest() {
  ( cd "$1" && find . -type f -name '*.py' \
      -not -path './.git/*' -not -path './production/*' \
      -not -path '*/__pycache__/*' -not -path './.pytest_cache/*' \
      -printf '%P\n' | LC_ALL=C sort | xargs -d '\n' md5sum )
}
DEV_M="$(mktemp)"; PROD_M="$(mktemp)"
trap 'rm -f "$DEV_M" "$PROD_M"' EXIT
_manifest "$DEV_ROOT" > "$DEV_M"
_manifest "$PROD"     > "$PROD_M"
if ! diff -q "$DEV_M" "$PROD_M" >/dev/null; then
  echo "❌ Код розійшовся з дев-версією:"
  diff "$DEV_M" "$PROD_M" | head -20
  exit 1
fi
echo "  · код збігається побайтово ($(wc -l < "$DEV_M") файлів .py, md5 кожного)"

# Усе, без чого розгортання не працює.
for f in config.py docker-compose.yml Dockerfile requirements.txt pytest.ini \
         db/schema.sql .env.example .dockerignore .gitignore \
         README.md DEPLOYMENT.md OPERATIONS.md TROUBLESHOOTING.md \
         docs/jobs.md docs/decisions.md docs/architecture.md \
         scripts/backup_db.sh scripts/restore_db.sh \
         scripts/bootstrap_1_backfill.sh scripts/bootstrap_2_pipeline.sh; do
  [ -f "$PROD/$f" ] || { echo "❌ У продакшені немає $f"; exit 1; }
done
echo "  · обов'язкові файли на місці"

echo
echo "✅ Готово. Далі:"
echo "     docker compose exec app pytest -q      # 1354 тести (той самий код)"
echo "     git -C production status"
echo "     git -C production add -A && git -C production commit -m '…'"
echo "     git -C production push"
