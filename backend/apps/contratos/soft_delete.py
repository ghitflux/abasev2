from __future__ import annotations

from apps.contratos.competencia import sync_competencia_locks_for_references
from apps.contratos.models import Ciclo, Contrato, Parcela


def soft_delete_contract_tree(contrato: Contrato) -> dict[str, int]:
    referencias = set(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .values_list("referencia_mes", flat=True)
    )

    summary = {
        "contracts_soft_deleted": 0,
        "cycles_soft_deleted": 0,
        "parcelas_soft_deleted": 0,
    }

    for parcela in Parcela.all_objects.filter(
        ciclo__contrato=contrato,
        deleted_at__isnull=True,
    ).exclude(status=Parcela.Status.CANCELADO):
        parcela.soft_delete()
        summary["parcelas_soft_deleted"] += 1

    for ciclo in Ciclo.all_objects.filter(contrato=contrato, deleted_at__isnull=True):
        ciclo.soft_delete()
        summary["cycles_soft_deleted"] += 1

    if contrato.deleted_at is None:
        contrato.soft_delete()
        summary["contracts_soft_deleted"] += 1

    sync_competencia_locks_for_references(
        associado_id=contrato.associado_id,
        referencias=sorted(referencias),
    )
    return summary
