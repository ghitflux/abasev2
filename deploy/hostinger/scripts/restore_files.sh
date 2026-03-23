#!/bin/bash
# ============================================================
# ABASE v2 — Restore de Arquivos (Media, Anexos, Comprovantes)
# ============================================================
# Uso: ./restore_files.sh <caminho-do-media.tar.gz>
# Exemplo: ./restore_files.sh /opt/ABASE/data/backups/daily/media_20260317_120000.tar.gz
# ============================================================
set -euo pipefail

MEDIA_FILE="${1:-}"
LOG_FILE="/opt/ABASE/logs/restore_files_$(date +%Y%m%d_%H%M%S).log"

if [[ -z "${MEDIA_FILE}" ]]; then
    echo "Uso: $0 <caminho-do-media.tar.gz>"
    echo ""
    echo "Backups de media disponíveis:"
    ls -lh /opt/ABASE/data/backups/daily/media_*.tar.gz 2>/dev/null || echo "(nenhum encontrado)"
    exit 1
fi

if [[ ! -f "${MEDIA_FILE}" ]]; then
    echo "ERRO: Arquivo não encontrado: ${MEDIA_FILE}"
    exit 1
fi

echo "======================================================" | tee -a "${LOG_FILE}"
echo "ABASE v2 — Restore Media — $(date)" | tee -a "${LOG_FILE}"
echo "Arquivo: ${MEDIA_FILE}" | tee -a "${LOG_FILE}"
echo "======================================================" | tee -a "${LOG_FILE}"

# Extrair para diretório temporário
TMP_DIR="/tmp/abase_media_restore_$(date +%s)"
mkdir -p "${TMP_DIR}"
echo "[restore_files] Extraindo ${MEDIA_FILE}..." | tee -a "${LOG_FILE}"
tar -xzf "${MEDIA_FILE}" -C "${TMP_DIR}"

# Copiar para volume Docker
echo "[restore_files] Copiando para volume Docker (abase_backend_media)..." | tee -a "${LOG_FILE}"
docker run --rm \
    -v abase_backend_media:/target \
    -v "${TMP_DIR}":/source:ro \
    alpine sh -c "cp -a /source/. /target/ && echo 'Cópia concluída'"

# Copiar para diretório host persistente
echo "[restore_files] Copiando para /opt/ABASE/data/media..." | tee -a "${LOG_FILE}"
cp -a "${TMP_DIR}/." /opt/ABASE/data/media/ 2>/dev/null || true

# Limpar temporários
rm -rf "${TMP_DIR}"

echo "[restore_files] Restore de arquivos concluído — $(date)" | tee -a "${LOG_FILE}"
echo "Logs em: ${LOG_FILE}"

# Verificar
echo "[restore_files] Conteúdo do volume restaurado:"
docker run --rm -v abase_backend_media:/data alpine ls -la /data/ 2>/dev/null || echo "(volume não disponível)"
