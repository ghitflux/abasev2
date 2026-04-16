#!/usr/bin/env bash
set -euo pipefail

COMPETENCIA="${1:-}"

if [[ -z "${COMPETENCIA}" ]]; then
  echo "Uso: bash scripts/post_deploy_effectivated_renewal_cycle_repair.sh YYYY-MM"
  exit 1
fi

echo "==> Auditoria antes da correção (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_effectivated_renewal_cycles --competencia "${COMPETENCIA}"

echo
echo "==> Aplicando correção (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_effectivated_renewal_cycles --apply --competencia "${COMPETENCIA}"

echo
echo "==> Auditoria após a correção (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_effectivated_renewal_cycles --competencia "${COMPETENCIA}"

echo
echo "==> Auditoria histórica conservadora"
docker compose exec -T backend python manage.py repair_effectivated_renewal_cycles

echo
echo "==> Reiniciando backend"
docker compose restart backend
