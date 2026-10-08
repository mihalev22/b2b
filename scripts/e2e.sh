#!/usr/bin/env bash
# Сквозная проверка поднятого стека: health → загрузка → очередь → позиции → экспорт.
# Запуск: bash scripts/e2e.sh [BASE_URL]   (по умолчанию http://localhost:3000 — через nginx фронта)
set -euo pipefail

BASE="${1:-http://localhost:3000}"
API="$BASE/api/v1"
FIXTURE="$(dirname "$0")/fixtures/spec.csv"
TIMEOUT="${E2E_TIMEOUT:-60}"

fail() { echo "FAIL: $*" >&2; exit 1; }
field() { sed -nE "s/.*\"$1\":\"?([^\",}]*)\"?.*/\1/p"; }

echo "== health"
health=$(curl -fsS "$API/health") || fail "api недоступен на $API"
echo "$health" | grep -q '"status":"ok"' || fail "health не ok: $health"

echo "== upload"
created=$(curl -fsS -F "file=@$FIXTURE;type=text/csv" "$API/jobs") || fail "загрузка файла"
job=$(echo "$created" | field job_id)
[ -n "$job" ] || fail "нет job_id в ответе: $created"
echo "job $job"

echo "== wait"
status=""
for _ in $(seq 1 "$TIMEOUT"); do
  info=$(curl -fsS "$API/jobs/$job")
  status=$(echo "$info" | field status)
  case "$status" in done|failed) break ;; esac
  sleep 1
done
[ "$status" = "done" ] || fail "задание в статусе '$status': $info"
expected=$(($(wc -l < "$FIXTURE") - 1))
total=$(echo "$info" | field total_count)
[ "$total" = "$expected" ] || fail "позиций $total, ожидалось $expected"

echo "== items"
items=$(curl -fsS "$API/jobs/$job/items?limit=200")
echo "$items" | grep -q "\"total\":$expected" || fail "items: $items"

echo "== export"
code=$(curl -sS -o /dev/null -w '%{http_code}' "$API/jobs/$job/export")
[ "$code" = "200" ] || fail "экспорт вернул $code"

echo "== spa"
code=$(curl -sS -o /dev/null -w '%{http_code}' "$BASE/jobs/$job")
[ "$code" = "200" ] || fail "SPA-маршрут вернул $code"

echo "OK: $expected позиций прошли путь загрузка → очередь → обработка → экспорт"
