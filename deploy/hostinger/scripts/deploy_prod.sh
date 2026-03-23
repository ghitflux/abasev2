#!/bin/bash
# ============================================================
# ABASE v2 — Deploy em Produção na VPS
# ============================================================
# Uso: ./deploy_prod.sh [--skip-backup]
# Pré-requisito: executar como usuário deploy ou root na VPS
# ============================================================
set -euo pipefail

REPO_DIR="/opt/ABASE/repo"
ENV_FILE="/opt/ABASE/env/.env.production"
COMPOSE_FILE="${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml"
BRANCH="abaseprod"
LOG_FILE="/opt/ABASE/logs/deploy_$(date +%Y%m%d_%H%M%S).log"
SKIP_BACKUP="${1:-}"

echo "======================================================" | tee -a "${LOG_FILE}"
echo "ABASE v2 — Deploy de Produção — $(date)" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"

# Verificar pré-requisitos
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERRO: Arquivo de env não encontrado em ${ENV_FILE}" | tee -a "${LOG_FILE}"
    echo "Copie o exemplo: cp ${REPO_DIR}/deploy/hostinger/.env.production.example ${ENV_FILE}" | tee -a "${LOG_FILE}"
    exit 1
fi

# Backup antes do deploy
if [[ "${SKIP_BACKUP}" != "--skip-backup" ]]; then
    echo "[deploy] Fazendo backup preventivo..." | tee -a "${LOG_FILE}"
    bash "${REPO_DIR}/deploy/hostinger/scripts/backup_now.sh" 2>&1 | tee -a "${LOG_FILE}"
fi

# Atualizar repositório
echo "[deploy] Atualizando repositório (branch: ${BRANCH})..." | tee -a "${LOG_FILE}"
cd "${REPO_DIR}"
git fetch origin 2>&1 | tee -a "${LOG_FILE}"
git checkout "${BRANCH}" 2>&1 | tee -a "${LOG_FILE}"
git pull origin "${BRANCH}" 2>&1 | tee -a "${LOG_FILE}"
echo "[deploy] Commit atual: $(git log --oneline -1)" | tee -a "${LOG_FILE}"

# Build dos containers
echo "[deploy] Fazendo build dos containers..." | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    build --no-cache backend celery frontend 2>&1 | tee -a "${LOG_FILE}"

# Subir stack completa
echo "[deploy] Subindo stack de produção..." | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    up -d --force-recreate 2>&1 | tee -a "${LOG_FILE}"

# Aguardar containers ficarem healthy
echo "[deploy] Aguardando containers ficarem healthy..." | tee -a "${LOG_FILE}"
sleep 30

# Verificar status
echo "[deploy] Status dos containers:" | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps 2>&1 | tee -a "${LOG_FILE}"

# Verificar saúde
echo "[deploy] Testando conectividade..." | tee -a "${LOG_FILE}"
sleep 10
curl -f -s -o /dev/null -w "API HTTP Status: %{http_code}\n" \
    http://localhost/api/v1/health/ 2>&1 | tee -a "${LOG_FILE}" || true
curl -f -s -o /dev/null -w "Frontend HTTP Status: %{http_code}\n" \
    http://localhost/ 2>&1 | tee -a "${LOG_FILE}" || true

echo "[deploy] Deploy concluído — $(date)" | tee -a "${LOG_FILE}"
echo "Logs em: ${LOG_FILE}"
