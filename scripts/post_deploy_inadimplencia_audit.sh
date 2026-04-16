#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose exec -T backend python manage.py shell <<'PY'
from django.utils import timezone

from apps.contratos.models import Contrato, Parcela
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.tesouraria.services import BaixaManualService

mes_atual = timezone.localdate().replace(day=1)
rows = BaixaManualService.listar_parcelas_pendentes()
row_keys = {
    (
        row.get("parcela_id"),
        row.get("associado_id"),
        row.get("referencia_mes"),
    )
    for row in rows
}

missing = []
parcelas = (
    Parcela.objects.select_related("ciclo__contrato__associado")
    .filter(
        ciclo__contrato__contrato_canonico__isnull=True,
        status__in=[Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO],
        referencia_mes__lt=mes_atual,
        descartado_em__isnull=True,
        deleted_at__isnull=True,
    )
    .order_by("ciclo__contrato__associado__nome_completo", "referencia_mes", "id")
)

for parcela in parcelas.iterator():
    keys = {
        (parcela.id, parcela.ciclo.contrato.associado_id, parcela.referencia_mes),
        (None, parcela.ciclo.contrato.associado_id, parcela.referencia_mes),
    }
    if row_keys.isdisjoint(keys):
        missing.append(
            {
                "parcela_id": parcela.id,
                "associado": parcela.ciclo.contrato.associado.nome_completo,
                "cpf": parcela.ciclo.contrato.associado.cpf_cnpj,
                "contrato": parcela.ciclo.contrato.codigo,
                "referencia": str(parcela.referencia_mes),
                "status": parcela.status,
            }
        )

print("=== Auditoria Inadimplentes ===")
print(f"parcelas_pendentes_api={len(rows)}")
print(f"parcelas_materializadas_sem_fila={len(missing)}")
if missing:
    print("amostra_missing=", missing[:20])

print("=== Auditoria Detalhe Associado ===")
contracts_with_unpaid = []
for contrato in Contrato.objects.filter(contrato_canonico__isnull=True).exclude(status=Contrato.Status.CANCELADO).iterator():
    projection = build_contract_cycle_projection(contrato)
    unresolved = [
        row
        for row in projection["unpaid_months"]
        if row["status"] not in {"quitada", "descontado", "liquidada"}
    ]
    regularized = [
        row
        for row in projection["unpaid_months"]
        if row["status"] in {"quitada", "descontado", "liquidada"}
    ]
    if unresolved or regularized:
        contracts_with_unpaid.append(
            {
                "contrato": contrato.codigo,
                "associado": contrato.associado.nome_completo,
                "nao_descontadas": len(unresolved),
                "quitadas_fora_ciclo": len(regularized),
            }
        )

print(f"contratos_com_historico_unpaid={len(contracts_with_unpaid)}")
print("amostra_contratos=", contracts_with_unpaid[:20])
PY
