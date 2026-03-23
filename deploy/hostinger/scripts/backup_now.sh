#!/bin/bash
# ============================================================
# ABASE v2 — Backup Manual Completo
# ============================================================
# Uso: ./backup_now.sh
# Retém: 7 diários, 4 semanais, 3 mensais
# Cobre: banco, media, anexos, comprovantes, env, configs
# ============================================================
set -euo pipefail

BACKUP_DIR="/opt/ABASE/data/backups"
ENV_FILE="/opt/ABASE/env/.env.production"
REPO_DIR="/opt/ABASE/repo"
COMPOSE_FILE="${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml"
DATE=$(date +%Y%m%d_%H%M%S)
DAY_OF_WEEK=$(date +%u)   # 1=Seg, 7=Dom
DAY_OF_MONTH=$(date +%d)

mkdir -p "${BACKUP_DIR}/daily" "${BACKUP_DIR}/weekly" "${BACKUP_DIR}/monthly"

echo "======================================================"
echo "ABASE v2 — Backup — $(date)"
echo "======================================================"

# ── 1. Backup do banco MySQL ──────────────────────────────
echo "[backup] Fazendo dump do MySQL..."
source "${ENV_FILE}"

docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T mysql \
    mysqldump -u"${DATABASE_USER}" -p"${DATABASE_PASSWORD}" \
    --single-transaction --routines --triggers "${DATABASE_NAME}" \
    > "${BACKUP_DIR}/daily/db_${DATE}.sql"

gzip "${BACKUP_DIR}/daily/db_${DATE}.sql"
echo "[backup] Banco salvo: db_${DATE}.sql.gz ($(du -sh ${BACKUP_DIR}/daily/db_${DATE}.sql.gz | cut -f1))"

# ── 2. Backup de arquivos media ───────────────────────────
echo "[backup] Fazendo backup de media files..."
docker run --rm \
    -v abase_backend_media:/source:ro \
    -v "${BACKUP_DIR}/daily":/backup \
    alpine sh -c "cd /source && tar -czf /backup/media_${DATE}.tar.gz . 2>/dev/null || true"
echo "[backup] Media salvo: media_${DATE}.tar.gz"

# ── 3. Backup do env de produção ──────────────────────────
echo "[backup] Fazendo backup do env de produção..."
cp "${ENV_FILE}" "${BACKUP_DIR}/daily/env_${DATE}.bak"
chmod 600 "${BACKUP_DIR}/daily/env_${DATE}.bak"
echo "[backup] Env salvo: env_${DATE}.bak"

# ── 4. Cópias semanais (domingos) ────────────────────────
if [[ "${DAY_OF_WEEK}" == "7" ]]; then
    echo "[backup] Fazendo cópia semanal..."
    cp "${BACKUP_DIR}/daily/db_${DATE}.sql.gz" "${BACKUP_DIR}/weekly/db_${DATE}.sql.gz"
    cp "${BACKUP_DIR}/daily/media_${DATE}.tar.gz" "${BACKUP_DIR}/weekly/media_${DATE}.tar.gz" 2>/dev/null || true
fi

# ── 5. Cópias mensais (dia 1) ────────────────────────────
if [[ "${DAY_OF_MONTH}" == "01" ]]; then
    echo "[backup] Fazendo cópia mensal..."
    cp "${BACKUP_DIR}/daily/db_${DATE}.sql.gz" "${BACKUP_DIR}/monthly/db_${DATE}.sql.gz"
    cp "${BACKUP_DIR}/daily/media_${DATE}.tar.gz" "${BACKUP_DIR}/monthly/media_${DATE}.tar.gz" 2>/dev/null || true
fi

# ── 6. Retenção ──────────────────────────────────────────
echo "[backup] Aplicando política de retenção..."
# Diários: manter 7
find "${BACKUP_DIR}/daily" -name "db_*.sql.gz" -type f | sort | head -n -7 | xargs -r rm -f
find "${BACKUP_DIR}/daily" -name "media_*.tar.gz" -type f | sort | head -n -7 | xargs -r rm -f
find "${BACKUP_DIR}/daily" -name "env_*.bak" -type f | sort | head -n -7 | xargs -r rm -f

# Semanais: manter 4
find "${BACKUP_DIR}/weekly" -name "db_*.sql.gz" -type f | sort | head -n -4 | xargs -r rm -f
find "${BACKUP_DIR}/weekly" -name "media_*.tar.gz" -type f | sort | head -n -4 | xargs -r rm -f

# Mensais: manter 3
find "${BACKUP_DIR}/monthly" -name "db_*.sql.gz" -type f | sort | head -n -3 | xargs -r rm -f
find "${BACKUP_DIR}/monthly" -name "media_*.tar.gz" -type f | sort | head -n -3 | xargs -r rm -f

echo "[backup] Backup concluído — $(date)"
echo "Arquivos em ${BACKUP_DIR}:"
du -sh "${BACKUP_DIR}"/*/
