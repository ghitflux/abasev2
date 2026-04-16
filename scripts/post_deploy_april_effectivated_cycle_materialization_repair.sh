#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPETENCIA="${1:-2026-04}"

echo "==> Auditoria antes da correção de materialização (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_april_effectivated_cycle_materialization \
  --competencia "$COMPETENCIA"

echo
echo "==> Aplicando correção de materialização (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_april_effectivated_cycle_materialization \
  --competencia "$COMPETENCIA" \
  --apply

echo
echo "==> Auditoria após a correção de materialização (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_april_effectivated_cycle_materialization \
  --competencia "$COMPETENCIA"

echo
echo "==> Reiniciando backend"
docker compose restart backend
