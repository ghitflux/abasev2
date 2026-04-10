#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

timestamp="$(date +%Y%m%dT%H%M%S)"
report_dir="$ROOT_DIR/backend/media/relatorios/legacy_import"
report_path="$report_dir/repair_small_value_return_renewal_block_${timestamp}.json"

mkdir -p "$report_dir"

echo "[1/4] Aplicando migrações pendentes"
python manage.py migrate

echo "[2/4] Removendo contratos 30/50 importados do fluxo de aptos a renovar"
python manage.py repair_small_value_return_renewal_block --apply --report-json "$report_path"

echo "[3/4] Conferindo remanescentes 30/50 em aptos a renovar"
python manage.py shell -c "
from apps.refinanciamento.models import Refinanciamento
from apps.importacao.models import ArquivoRetornoItem
aptos = Refinanciamento.objects.filter(
    status='apto_a_renovar',
    deleted_at__isnull=True,
    contrato_origem__isnull=False,
)
contrato_ids = list(aptos.values_list('contrato_origem_id', flat=True).distinct())
remaining = sorted(set(
    ArquivoRetornoItem.objects.filter(
        deleted_at__isnull=True,
        valor_descontado__in=['30.00', '50.00'],
        parcela__ciclo__contrato_id__in=contrato_ids,
    ).values_list('parcela__ciclo__contrato_id', flat=True)
))
print({'aptos_total': aptos.count(), 'small_value_remaining': len(remaining), 'contract_ids': remaining[:100]})
"

echo "[4/4] Check final do Django"
python manage.py check

echo "Concluído. Relatório salvo em: $report_path"
