#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPETENCIA="${1:-2026-04}"

cd "$ROOT_DIR"

echo "[1/3] Auditoria de alinhamento da renovacao (${COMPETENCIA})"
docker compose exec -T backend python manage.py repair_renewal_alignment --competencia "$COMPETENCIA"

echo "[2/3] Conferindo fila apta e status persistido"
docker compose exec -T backend python manage.py shell -c "
from datetime import date
from apps.associados.models import Associado
from apps.contratos.renovacao import RenovacaoCicloService

competencia = date.fromisoformat('${COMPETENCIA}-01')
queue_rows = RenovacaoCicloService.listar_detalhes(
    competencia=competencia,
    status='apto_a_renovar',
)
print({
    'competencia': '${COMPETENCIA}',
    'queue_apto': len(queue_rows),
    'persisted_apto': Associado.objects.filter(status='apto_a_renovar').count(),
})
"

echo "[3/3] Check final do Django"
docker compose exec -T backend python manage.py check

echo "Auditoria concluida."
