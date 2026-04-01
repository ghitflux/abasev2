#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

TIMESTAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP_DIR_REL="backups/legacy_restore_${TIMESTAMP}"
BACKUP_DIR_HOST="${REPO_ROOT}/${BACKUP_DIR_REL}"
STAGING_DIR_CONTAINER="/workspace/${BACKUP_DIR_REL}/staged_return_files"
REPORT_JSON_CONTAINER="/workspace/${BACKUP_DIR_REL}/restore_report.json"

BACKEND_MEDIA_VOLUME="${BACKEND_MEDIA_VOLUME:-abase-v2_backend_media}"

mkdir -p "$BACKUP_DIR_HOST"

echo "[1/3] Backup SQL em ${BACKUP_DIR_HOST}/pre_restore.sql"
docker compose exec -T mysql sh -lc \
  'mysqldump --no-tablespaces -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  > "${BACKUP_DIR_HOST}/pre_restore.sql"

echo "[2/3] Snapshot do volume ${BACKEND_MEDIA_VOLUME} em ${BACKUP_DIR_HOST}/backend_media.tar.gz"
docker run --rm \
  -v "${BACKEND_MEDIA_VOLUME}:/source" \
  -v "${BACKUP_DIR_HOST}:/backup" \
  alpine sh -lc 'cd /source && tar czf /backup/backend_media.tar.gz .'

echo "[3/3] Restauração completa via backend-tools"
docker compose --profile tools run --rm backend-tools \
  python manage.py restore_legacy_snapshot \
  --file /workspace/dumps_legado/abase_banco_legado_31.03.2026.sql \
  --legacy-media-root /workspace/anexos_legado \
  --staging-dir "${STAGING_DIR_CONTAINER}" \
  --report-json "${REPORT_JSON_CONTAINER}" \
  --execute

echo "Concluído. Relatório: ${BACKUP_DIR_HOST}/restore_report.json"
