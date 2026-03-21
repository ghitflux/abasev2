#!/bin/bash
# ============================================================
# ABASE v2 — Rollback de Produção
# ============================================================
# Uso: ./rollback.sh <git-commit-hash>
# Exemplo: ./rollback.sh abc1234
# ============================================================
set -euo pipefail

REPO_DIR="/opt/ABASE/repo"
ENV_FILE="/opt/ABASE/env/.env.production"
COMPOSE_FILE="${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml"
TARGET_COMMIT="${1:-}"
LOG_FILE="/opt/ABASE/logs/rollback_$(date +%Y%m%d_%H%M%S).log"

echo "======================================================" | tee -a "${LOG_FILE}"
echo "ABASE v2 — Rollback — $(date)" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"

if [[ -z "${TARGET_COMMIT}" ]]; then
    echo "Uso: $0 <git-commit-hash>"
    echo ""
    echo "Últimos commits disponíveis:"
    cd "${REPO_DIR}" && git log --oneline -10
    exit 1
fi

echo "[rollback] Commit atual: $(cd ${REPO_DIR} && git log --oneline -1)" | tee -a "${LOG_FILE}"
echo "[rollback] Alvo do rollback: ${TARGET_COMMIT}" | tee -a "${LOG_FILE}"

# Backup antes do rollback
echo "[rollback] Fazendo backup preventivo antes do rollback..." | tee -a "${LOG_FILE}"
bash "${REPO_DIR}/deploy/hostinger/scripts/backup_now.sh" 2>&1 | tee -a "${LOG_FILE}"

# Reverter código
echo "[rollback] Revertendo para commit ${TARGET_COMMIT}..." | tee -a "${LOG_FILE}"
cd "${REPO_DIR}"
git checkout "${TARGET_COMMIT}" 2>&1 | tee -a "${LOG_FILE}"

# Rebuild e redeploy
echo "[rollback] Fazendo rebuild dos containers..." | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    build --no-cache backend celery frontend 2>&1 | tee -a "${LOG_FILE}"

echo "[rollback] Subindo containers revertidos..." | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    up -d --force-recreate 2>&1 | tee -a "${LOG_FILE}"

sleep 20

echo "[rollback] Status após rollback:" | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps 2>&1 | tee -a "${LOG_FILE}"

echo "[rollback] Rollback concluído para: $(cd ${REPO_DIR} && git log --oneline -1)" | tee -a "${LOG_FILE}"
echo "Logs em: ${LOG_FILE}"
