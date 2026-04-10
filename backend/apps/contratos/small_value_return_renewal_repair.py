from __future__ import annotations

from collections import Counter
from decimal import Decimal

from django.db import transaction

from apps.refinanciamento.models import Refinanciamento

from .canonicalization import operational_contracts_queryset
from .cycle_projection import build_contract_cycle_projection
from .cycle_rebuild import rebuild_contract_cycle_state
from .models import Contrato
from .small_value_rules import is_return_imported_small_value_contract


def _mensalidade_bucket(contrato: Contrato) -> str:
    mensalidade = Decimal(str(contrato.valor_mensalidade or Decimal("0.00"))).quantize(
        Decimal("0.01")
    )
    if mensalidade == Decimal("30.00"):
        return "mensalidade_30"
    if mensalidade == Decimal("50.00"):
        return "mensalidade_50"
    return "mensalidade_outros"


def list_return_imported_small_value_contracts() -> list[Contrato]:
    queryset = (
        Contrato.objects.select_related("associado", "agente")
        .exclude(status=Contrato.Status.CANCELADO)
        .filter(valor_mensalidade__in=[Decimal("30.00"), Decimal("50.00")])
        .order_by("associado__nome_completo", "id")
    )
    return [
        contrato
        for contrato in queryset.iterator()
        if is_return_imported_small_value_contract(contrato)
    ]


def collect_operational_apto_snapshot() -> dict[str, object]:
    queryset = operational_contracts_queryset(
        Contrato.objects.select_related("associado", "agente").order_by(
            "associado__nome_completo",
            "id",
        )
    )
    apto_contracts: list[Contrato] = []
    by_associado_status: Counter[str] = Counter()
    by_mensalidade_bucket: Counter[str] = Counter()
    by_small_value_origin: Counter[str] = Counter()

    for contrato in queryset.iterator():
        projection = build_contract_cycle_projection(contrato)
        if str(projection.get("status_renovacao") or "") != Refinanciamento.Status.APTO_A_RENOVAR:
            continue
        apto_contracts.append(contrato)
        by_associado_status[str(getattr(contrato.associado, "status", "") or "sem_status")] += 1
        by_mensalidade_bucket[_mensalidade_bucket(contrato)] += 1
        by_small_value_origin[
            (
                "importado_retorno_30_50"
                if is_return_imported_small_value_contract(contrato)
                else "demais"
            )
        ] += 1

    return {
        "total": len(apto_contracts),
        "contract_ids": [contrato.id for contrato in apto_contracts],
        "by_associado_status": dict(sorted(by_associado_status.items())),
        "by_mensalidade_bucket": dict(sorted(by_mensalidade_bucket.items())),
        "by_small_value_origin": dict(sorted(by_small_value_origin.items())),
    }


def repair_small_value_return_renewal_block(*, apply: bool) -> dict[str, object]:
    contracts = list_return_imported_small_value_contracts()
    candidate_ids = [contrato.id for contrato in contracts]
    before_snapshot = collect_operational_apto_snapshot()
    before_candidate_apto_ids = [
        contrato.id
        for contrato in contracts
        if str(build_contract_cycle_projection(contrato).get("status_renovacao") or "")
        == Refinanciamento.Status.APTO_A_RENOVAR
    ]

    rebuild_reports: list[dict[str, object]] = []
    if apply and contracts:
        with transaction.atomic():
            for contrato in contracts:
                rebuild_reports.append(
                    rebuild_contract_cycle_state(contrato, execute=True).as_dict()
                )

    after_snapshot = collect_operational_apto_snapshot()
    after_candidate_apto_ids = [
        contrato.id
        for contrato in list_return_imported_small_value_contracts()
        if str(build_contract_cycle_projection(contrato).get("status_renovacao") or "")
        == Refinanciamento.Status.APTO_A_RENOVAR
    ]

    return {
        "mode": "apply" if apply else "dry-run",
        "candidate_contract_total": len(candidate_ids),
        "candidate_contract_ids": candidate_ids,
        "candidate_apto_before_total": len(before_candidate_apto_ids),
        "candidate_apto_before_ids": before_candidate_apto_ids,
        "candidate_apto_after_total": len(after_candidate_apto_ids),
        "candidate_apto_after_ids": after_candidate_apto_ids,
        "overall_apto_before": before_snapshot,
        "overall_apto_after": after_snapshot,
        "removed_from_apto_total": max(
            len(before_candidate_apto_ids) - len(after_candidate_apto_ids),
            0,
        ),
        "rebuild_summary": {
            "total_contracts": len(rebuild_reports),
            "ciclos_materializados": sum(
                item.get("ciclos_materializados", 0) for item in rebuild_reports
            ),
            "ciclos_invalidos_soft_deleted": sum(
                item.get("ciclos_invalidos_soft_deleted", 0)
                for item in rebuild_reports
            ),
            "parcelas_invalidas_soft_deleted": sum(
                item.get("parcelas_invalidas_soft_deleted", 0)
                for item in rebuild_reports
            ),
            "refinanciamentos_ajustados": sum(
                item.get("refinanciamentos_ajustados", 0)
                for item in rebuild_reports
            ),
            "refinanciamentos_soft_deleted": sum(
                item.get("refinanciamentos_soft_deleted", 0)
                for item in rebuild_reports
            ),
        },
    }
