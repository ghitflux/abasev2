#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPETENCIA="${COMPETENCIA:-2026-03}"
ARQUIVO_RETORNO_ID="${ARQUIVO_RETORNO_ID:-46}"
RETURN_FILE="${RETURN_FILE:-${ROOT_DIR}/backups/Relatorio_D2102-03-2026.txt}"
BACKEND_CONTAINER="${LOCAL_BACKEND_CONTAINER:-abase-v2-backend-1}"
MYSQL_CONTAINER="${ABASE_LOCAL_DB_CONTAINER:-abase-v2-mysql-1}"
LOCAL_DB_NAME="${ABASE_LOCAL_DB_NAME:-abase_v2}"
LOCAL_DB_USER="${ABASE_LOCAL_DB_USER:-root}"
LOCAL_DB_PASSWORD="${ABASE_LOCAL_DB_PASSWORD:-abase}"

if [[ ! -f "${RETURN_FILE}" ]]; then
    echo "[erro] Arquivo retorno não encontrado: ${RETURN_FILE}" >&2
    exit 1
fi

cd "${ROOT_DIR}"

echo "[1/5] Sincronizando dump de produção para a base local..."
python scripts/sync_db_from_prod.py

echo "[2/5] Aplicando migrations locais sobre o dump restaurado..."
docker exec "${BACKEND_CONTAINER}" bash -lc "cd /app && python manage.py migrate --noinput"

echo "[3/5] Resolvendo caminho do arquivo retorno no banco restaurado..."
ARQUIVO_URL="$(
    docker exec "${MYSQL_CONTAINER}" mysql -N -B -u"${LOCAL_DB_USER}" -p"${LOCAL_DB_PASSWORD}" "${LOCAL_DB_NAME}" \
        -e "SELECT arquivo_url FROM importacao_arquivoretorno WHERE id=${ARQUIVO_RETORNO_ID} LIMIT 1;"
)"

if [[ -z "${ARQUIVO_URL}" ]]; then
    echo "[erro] ArquivoRetorno ${ARQUIVO_RETORNO_ID} não encontrado na base local." >&2
    exit 1
fi

echo "[4/5] Copiando arquivo retorno para o MEDIA_ROOT local..."
docker exec "${BACKEND_CONTAINER}" sh -lc "mkdir -p \"\$(dirname \"/app/media/${ARQUIVO_URL}\")\""
docker cp "${RETURN_FILE}" "${BACKEND_CONTAINER}:/app/media/${ARQUIVO_URL}"

echo "[5/5] Executando correção validada localmente..."
docker exec "${BACKEND_CONTAINER}" bash -lc \
    "cd /app && python manage.py corrigir_importacao_retorno --competencia ${COMPETENCIA} --arquivo-retorno-id ${ARQUIVO_RETORNO_ID} --apply"

echo
echo "[ok] Validação local concluída."
