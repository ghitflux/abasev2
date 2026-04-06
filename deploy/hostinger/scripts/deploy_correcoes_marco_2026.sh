#!/bin/bash
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/ABASE/repo}"
ENV_FILE="${ENV_FILE:-/opt/ABASE/env/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_DIR}/deploy/hostinger/docker-compose.prod.yml}"
COMPETENCIA="${COMPETENCIA:-2026-03}"
ARQUIVO_RETORNO_ID="${ARQUIVO_RETORNO_ID:-46}"

cd "${REPO_DIR}"

echo "[1/8] Backup preventivo..."
bash "${REPO_DIR}/deploy/hostinger/scripts/backup_now.sh"

echo "[2/8] Atualizando código..."
git fetch --all --prune
git pull --ff-only

echo "[3/8] Rebuild sem cache..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    build --no-cache backend celery frontend

echo "[4/8] Restart com force-recreate..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    up -d --force-recreate backend celery frontend

echo "[5/8] Aplicando migrations..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    exec -T backend python manage.py migrate --noinput

echo "[6/8] Check rápido do backend..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    exec -T backend python manage.py check

echo "[7/8] Dry-run da correção de março/2026..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    exec -T backend python manage.py corrigir_importacao_retorno \
    --competencia "${COMPETENCIA}" \
    --arquivo-retorno-id "${ARQUIVO_RETORNO_ID}"

echo "[8/8] Apply da correção de março/2026..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" \
    exec -T backend python manage.py corrigir_importacao_retorno \
    --competencia "${COMPETENCIA}" \
    --arquivo-retorno-id "${ARQUIVO_RETORNO_ID}" \
    --apply

echo
echo "[ok] Deploy e correção concluídos."
