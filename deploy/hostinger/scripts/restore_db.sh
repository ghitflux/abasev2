#!/bin/bash
# ============================================================
# ABASE v2 — Restore do Banco de Dados MySQL
# ============================================================
# Uso: ./restore_db.sh <caminho-do-dump.sql.gz>
# Exemplo: ./restore_db.sh /opt/ABASE/data/backups/daily/db_20260317_120000.sql.gz
# ============================================================
set -euo pipefail

DUMP_FILE="${1:-}"
ENV_FILE="/opt/ABASE/env/.env.production"
REPO_DIR="/opt/ABASE/repo"
COMPOSE_FILE="${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml"
LOG_FILE="/opt/ABASE/logs/restore_db_$(date +%Y%m%d_%H%M%S).log"

if [[ -z "${DUMP_FILE}" ]]; then
    echo "Uso: $0 <caminho-do-dump.sql.gz>"
    echo ""
    echo "Dumps disponíveis:"
    ls -lh /opt/ABASE/data/backups/daily/db_*.sql.gz 2>/dev/null || echo "(nenhum encontrado)"
    exit 1
fi

if [[ ! -f "${DUMP_FILE}" ]]; then
    echo "ERRO: Arquivo não encontrado: ${DUMP_FILE}"
    exit 1
fi

echo "======================================================" | tee -a "${LOG_FILE}"
echo "ABASE v2 — Restore DB — $(date)" | tee -a "${LOG_FILE}"
echo "Arquivo: ${DUMP_FILE}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"

source "${ENV_FILE}"

# Backup preventivo antes do restore
echo "[restore_db] Fazendo backup preventivo antes do restore..." | tee -a "${LOG_FILE}"
bash "${REPO_DIR}/deploy/hostinger/scripts/backup_now.sh" 2>&1 | tee -a "${LOG_FILE}"

# Restore
echo "[restore_db] Restaurando banco de dados..." | tee -a "${LOG_FILE}"
if [[ "${DUMP_FILE}" == *.gz ]]; then
    zcat "${DUMP_FILE}" | docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
        exec -T mysql mysql -u"${DATABASE_USER}" -p"${DATABASE_PASSWORD}" "${DATABASE_NAME}" \
        2>&1 | tee -a "${LOG_FILE}"
else
    docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
        exec -T mysql mysql -u"${DATABASE_USER}" -p"${DATABASE_PASSWORD}" "${DATABASE_NAME}" \
        < "${DUMP_FILE}" 2>&1 | tee -a "${LOG_FILE}"
fi

# Rodar migrations para garantir consistência
echo "[restore_db] Rodando migrations pós-restore..." | tee -a "${LOG_FILE}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    exec -T backend python manage.py migrate --noinput 2>&1 | tee -a "${LOG_FILE}"

echo "[restore_db] Restore concluído — $(date)" | tee -a "${LOG_FILE}"
echo "Logs em: ${LOG_FILE}"
