#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPETENCIA="${1:-2026-04}"
shift || true

if [ "$#" -eq 0 ]; then
  echo "Uso: bash scripts/repair_specific_aptos_server.sh 2026-04 CPF1 CPF2 ..."
  exit 1
fi

CPFS=("$@")
CPFS_CSV="$(IFS=,; echo "${CPFS[*]}")"

cd "$ROOT_DIR"

echo "[1/4] Rebuild de contratos e sincronizacao de status para os CPFs informados"
docker compose exec -T backend python manage.py shell -c "
from apps.associados.models import Associado
from apps.contratos.cycle_projection import sync_associado_mother_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state

cpfs = [item.strip() for item in '${CPFS_CSV}'.split(',') if item.strip()]
for cpf in cpfs:
    associado = Associado.objects.filter(cpf_cnpj=cpf).first()
    if associado is None:
        print({'cpf': cpf, 'found': False})
        continue
    for contrato in associado.contratos.exclude(status='cancelado'):
        rebuild_contract_cycle_state(contrato, execute=True)
    sync_associado_mother_status(associado)
    associado.refresh_from_db()
    print({'cpf': cpf, 'found': True, 'status': associado.status})
"

echo "[2/4] Auditoria geral de alinhamento"
docker compose exec -T backend python manage.py repair_renewal_alignment --competencia "$COMPETENCIA"

echo "[3/4] Conferencia da fila apta para os mesmos CPFs"
docker compose exec -T backend python manage.py shell -c "
from datetime import date
from apps.associados.models import Associado
from apps.contratos.renovacao import RenovacaoCicloService

cpfs = {item.strip() for item in '${CPFS_CSV}'.split(',') if item.strip()}
competencia = date.fromisoformat('${COMPETENCIA}-01')
rows = RenovacaoCicloService.listar_detalhes(
    competencia=competencia,
    status='apto_a_renovar',
)
queue_cpfs = {
    str(row.get('cpf_cnpj') or '').replace('.', '').replace('-', '').replace('/', '')
    for row in rows
}
for cpf in sorted(cpfs):
    associado = Associado.objects.filter(cpf_cnpj=cpf).first()
    print({
        'cpf': cpf,
        'found': bool(associado),
        'status_persistido': associado.status if associado else None,
        'na_fila_apta': cpf in queue_cpfs,
    })
"

echo "[4/4] Reiniciando backend e web"
docker compose restart backend web

echo "Correcao especifica concluida."
