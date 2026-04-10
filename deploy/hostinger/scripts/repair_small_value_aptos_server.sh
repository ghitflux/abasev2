#!/bin/bash
set -euo pipefail

# Script de reparo: remove aptos_a_renovar indevidos de contratos 30/50 importados.
# O bypass allow_small_value_renewal foi removido da regra; este script corrige
# os registros que receberam o override no deploy anterior.

REPO_DIR="${REPO_DIR:-/opt/ABASE/repo}"
ENV_FILE="${ENV_FILE:-/opt/ABASE/env/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml}"
REPORT_DIR="${REPORT_DIR:-/tmp}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

dc() {
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T backend "$@"
}

cd "${REPO_DIR}"

echo "[1/6] Backup preventivo..."
bash "${REPO_DIR}/deploy/hostinger/scripts/backup_now.sh"

echo "[2/6] Atualizando código..."
git fetch --all --prune
git pull --ff-only

echo "[3/6] Rebuild sem cache..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    build --no-cache backend celery frontend

echo "[4/6] Restart com force-recreate..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    up -d --force-recreate backend celery frontend

echo "[5/6] Aplicando migrations e check..."
dc python manage.py migrate --noinput
dc python manage.py check

echo "[6/6] Aplicando reparo small_value (remove overrides e reconstrói ciclos)..."
dc python manage.py repair_small_value_return_renewal_block \
    --apply \
    --report-json "${REPORT_DIR}/repair_small_value_aptos_${TIMESTAMP}.json"

echo
echo "=== Conferência de remanescentes ==="
dc python manage.py shell -c "
from apps.contratos.small_value_return_renewal_repair import repair_small_value_return_renewal_block
result = repair_small_value_return_renewal_block(apply=False)
remaining = result.get('candidate_contracts_total', 0)
print('remaining_small_value_aptos:', remaining)
if remaining == 0:
    print('[ok] Nenhum remanescente. Reparo concluido com sucesso.')
else:
    print('[ATENCAO] Ainda ha', remaining, 'contratos 30/50 com apto_a_renovar. Investigar.')
"

echo
echo "[ok] Script concluido. Relatorio salvo em ${REPORT_DIR}/repair_small_value_aptos_${TIMESTAMP}.json"
