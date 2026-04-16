#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPETENCIA="${1:-2026-04}"

cd "$ROOT_DIR"

echo "[1/5] Aplicando migracoes pendentes"
docker compose exec -T backend python manage.py migrate

echo "[2/5] Auditoria antes da correcao"
docker compose exec -T backend python manage.py repair_renewal_alignment --competencia "$COMPETENCIA"

echo "[3/5] Aplicando correcao de alinhamento"
docker compose exec -T backend python manage.py repair_renewal_alignment --apply --competencia "$COMPETENCIA"

echo "[4/5] Auditoria depois da correcao"
docker compose exec -T backend python manage.py repair_renewal_alignment --competencia "$COMPETENCIA"

echo "[5/5] Conferindo fila apta e status persistido"
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

echo "Correcao pos-deploy concluida."
