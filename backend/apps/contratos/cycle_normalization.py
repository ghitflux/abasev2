from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Prefetch

from apps.importacao.models import ArquivoRetornoItem
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Confirmacao

from .models import Ciclo, Contrato, Parcela

CONTRACT_STATUS_PRIORITY = {
    Contrato.Status.ATIVO: 0,
    Contrato.Status.ENCERRADO: 1,
    Contrato.Status.EM_ANALISE: 2,
    Contrato.Status.RASCUNHO: 3,
    Contrato.Status.CANCELADO: 4,
}

CYCLE_STATUS_PRIORITY = {
    Ciclo.Status.ABERTO: 0,
    Ciclo.Status.APTO_A_RENOVAR: 1,
    Ciclo.Status.CICLO_RENOVADO: 2,
    Ciclo.Status.FUTURO: 3,
    Ciclo.Status.FECHADO: 4,
}


@dataclass(frozen=True)
class DuplicateCycleResolution:
    canonical_cycle_id: int
    duplicate_cycle_id: int
    canonical_contract_id: int
    duplicate_contract_id: int
    reassigned_return_items: int


@dataclass(frozen=True)
class RestoredNormalizedContractResolution:
    contract_id: int
    contract_code: str
    source_contract_id: int | None
    restored_cycles: int
    restored_parcelas: int


NORMALIZATION_NOTE_PREFIX = "Parcela duplicada normalizada."


def _append_note(base: str, note: str) -> str:
    if not base:
        return note
    if note in base:
        return base
    return f"{base}\n{note}"


def _base_cycles_queryset(*, cpf_cnpj: str | None = None):
    queryset = (
        Ciclo.objects.select_related("contrato", "contrato__associado")
        .exclude(contrato__status=Contrato.Status.CANCELADO)
        .prefetch_related(
            Prefetch(
                "parcelas",
                queryset=Parcela.objects.prefetch_related("itens_retorno").order_by(
                    "numero"
                ),
            )
        )
    )
    if cpf_cnpj:
        queryset = queryset.filter(contrato__associado__cpf_cnpj=cpf_cnpj)
    return queryset


def cycle_group_key(cycle: Ciclo) -> tuple[int, int, object, object]:
    return (
        cycle.contrato.associado_id,
        cycle.numero,
        cycle.data_inicio,
        cycle.data_fim,
    )


def cycle_sort_key(cycle: Ciclo) -> tuple[object, ...]:
    parcelas = list(cycle.parcelas.all())
    parcelas_pagas = sum(
        1 for parcela in parcelas if parcela.status == Parcela.Status.DESCONTADO
    )
    itens_retorno = sum(parcela.itens_retorno.count() for parcela in parcelas)
    latest_payment_ordinal = max(
        (
            parcela.data_pagamento.toordinal()
            for parcela in parcelas
            if parcela.data_pagamento is not None
        ),
        default=0,
    )
    return (
        CONTRACT_STATUS_PRIORITY.get(cycle.contrato.status, 99),
        CYCLE_STATUS_PRIORITY.get(cycle.status, 99),
        -parcelas_pagas,
        -itens_retorno,
        -latest_payment_ordinal,
        cycle.contrato.created_at,
        cycle.contrato_id,
        cycle.id,
    )


def dedupe_cycles_for_display(cycles: list[Ciclo]) -> list[Ciclo]:
    visible_cycles = [
        cycle
        for cycle in cycles
        if cycle.contrato.status != Contrato.Status.CANCELADO
    ]
    grouped: dict[tuple[int, int, object, object], list[Ciclo]] = defaultdict(list)
    for cycle in visible_cycles:
        grouped[cycle_group_key(cycle)].append(cycle)

    canonical_cycles = [
        sorted(group, key=cycle_sort_key)[0]
        for group in grouped.values()
    ]

    return sorted(
        canonical_cycles,
        key=lambda cycle: (cycle.numero, cycle.data_inicio, cycle.contrato_id),
        reverse=True,
    )

def _strip_normalization_note(base: str) -> str:
    if not base:
        return ""
    lines = [line for line in base.splitlines() if NORMALIZATION_NOTE_PREFIX not in line]
    return "\n".join(lines).strip()


def _sync_duplicate_parcelas(
    *,
    canonical_cycle: Ciclo,
    duplicate_cycle: Ciclo,
) -> int:
    canonical_parcelas = {
        (parcela.numero, parcela.referencia_mes): parcela
        for parcela in canonical_cycle.parcelas.all()
    }

    for parcela in duplicate_cycle.parcelas.all():
        target = canonical_parcelas.get((parcela.numero, parcela.referencia_mes))
        if not target:
            continue
        parcela.status = target.status
        parcela.data_pagamento = (
            target.data_pagamento
            if target.status == Parcela.Status.DESCONTADO
            else None
        )
        parcela.observacao = _strip_normalization_note(parcela.observacao)
        parcela.save(
            update_fields=[
                "status",
                "data_pagamento",
                "observacao",
                "competencia_lock",
                "updated_at",
            ]
        )

    return 0


def _reassign_related_records(
    *,
    canonical_cycle: Ciclo,
    duplicate_cycle: Ciclo,
) -> None:
    canonical_contract = canonical_cycle.contrato
    duplicate_contract = duplicate_cycle.contrato

    Refinanciamento.objects.filter(ciclo_origem=duplicate_cycle).update(
        ciclo_origem=canonical_cycle
    )

    if not hasattr(canonical_cycle, "refinanciamento_destino"):
        Refinanciamento.objects.filter(ciclo_destino=duplicate_cycle).update(
            ciclo_destino=canonical_cycle
        )

    Refinanciamento.objects.filter(contrato_origem=duplicate_contract).update(
        contrato_origem=canonical_contract
    )
    Comprovante.objects.filter(contrato=duplicate_contract).update(
        contrato=canonical_contract
    )
    Confirmacao.objects.filter(contrato=duplicate_contract).update(
        contrato=canonical_contract
    )


def find_duplicate_cycle_groups(*, cpf_cnpj: str | None = None) -> list[list[Ciclo]]:
    grouped: dict[tuple[int, int, object, object], list[Ciclo]] = defaultdict(list)
    for cycle in _base_cycles_queryset(cpf_cnpj=cpf_cnpj):
        grouped[cycle_group_key(cycle)].append(cycle)
    return [
        sorted(group, key=cycle_sort_key)
        for group in grouped.values()
        if len(group) > 1
    ]


@transaction.atomic
def normalize_duplicate_cycles(
    *,
    cpf_cnpj: str | None = None,
    execute: bool = False,
) -> dict[str, object]:
    groups = find_duplicate_cycle_groups(cpf_cnpj=cpf_cnpj)
    resolutions: list[DuplicateCycleResolution] = []

    for group in groups:
        canonical_cycle = group[0]
        for duplicate_cycle in group[1:]:
            reassigned_return_items = 0
            if execute:
                reassigned_return_items = _sync_duplicate_parcelas(
                    canonical_cycle=canonical_cycle,
                    duplicate_cycle=duplicate_cycle,
                )
                duplicate_cycle.status = canonical_cycle.status
                duplicate_cycle.save(update_fields=["status", "updated_at"])
                duplicate_contract = duplicate_cycle.contrato
                if duplicate_contract.status == Contrato.Status.CANCELADO:
                    duplicate_contract.status = canonical_cycle.contrato.status
                    duplicate_contract.save(update_fields=["status", "updated_at"])

            resolutions.append(
                DuplicateCycleResolution(
                    canonical_cycle_id=canonical_cycle.id,
                    duplicate_cycle_id=duplicate_cycle.id,
                    canonical_contract_id=canonical_cycle.contrato_id,
                    duplicate_contract_id=duplicate_cycle.contrato_id,
                    reassigned_return_items=reassigned_return_items,
                )
            )

    return {
        "groups": len(groups),
        "duplicate_cycles": len(resolutions),
        "reassigned_return_items": sum(
            resolution.reassigned_return_items for resolution in resolutions
        ),
        "resolutions": resolutions,
    }


def _normalized_cancelled_contracts_queryset(*, cpf_cnpj: str | None = None):
    queryset = (
        Contrato.objects.select_related("associado")
        .filter(
            status=Contrato.Status.CANCELADO,
            ciclos__parcelas__observacao__icontains=NORMALIZATION_NOTE_PREFIX,
        )
        .distinct()
        .prefetch_related(
            Prefetch(
                "ciclos",
                queryset=Ciclo.objects.prefetch_related(
                    Prefetch("parcelas", queryset=Parcela.all_objects.order_by("numero"))
                ),
            )
        )
    )
    if cpf_cnpj:
        queryset = queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    return queryset


def _counterpart_parcela(parcela: Parcela) -> Parcela | None:
    return (
        Parcela.objects.select_related("ciclo", "ciclo__contrato")
        .filter(
            associado_id=parcela.associado_id,
            referencia_mes=parcela.referencia_mes,
        )
        .exclude(ciclo__contrato_id=parcela.ciclo.contrato_id)
        .order_by("-updated_at", "-created_at", "-id")
        .first()
    )


@transaction.atomic
def restore_normalized_duplicate_contracts(
    *,
    cpf_cnpj: str | None = None,
    execute: bool = False,
) -> dict[str, object]:
    contracts = list(_normalized_cancelled_contracts_queryset(cpf_cnpj=cpf_cnpj))
    resolutions: list[RestoredNormalizedContractResolution] = []

    for contract in contracts:
        source_contract: Contrato | None = None
        restored_cycles = 0
        restored_parcelas = 0

        for cycle in contract.ciclos.all():
            source_cycle: Ciclo | None = None
            cycle_restored = False
            for parcela in cycle.parcelas.all():
                if NORMALIZATION_NOTE_PREFIX not in (parcela.observacao or ""):
                    continue
                counterpart = _counterpart_parcela(parcela)
                if not counterpart:
                    continue
                source_contract = source_contract or counterpart.ciclo.contrato
                source_cycle = source_cycle or counterpart.ciclo
                if execute:
                    parcela.status = counterpart.status
                    parcela.data_pagamento = (
                        counterpart.data_pagamento
                        if counterpart.status == Parcela.Status.DESCONTADO
                        else None
                    )
                    parcela.observacao = _strip_normalization_note(parcela.observacao)
                    parcela.save(
                        update_fields=[
                            "status",
                            "data_pagamento",
                            "observacao",
                            "competencia_lock",
                            "updated_at",
                        ]
                    )
                restored_parcelas += 1
                cycle_restored = True

            if source_cycle and cycle_restored:
                if execute:
                    cycle.status = source_cycle.status
                    cycle.save(update_fields=["status", "updated_at"])
                restored_cycles += 1

        if execute and source_contract:
            contract.status = source_contract.status
            contract.save(update_fields=["status", "updated_at"])

        resolutions.append(
            RestoredNormalizedContractResolution(
                contract_id=contract.id,
                contract_code=contract.codigo,
                source_contract_id=source_contract.id if source_contract else None,
                restored_cycles=restored_cycles,
                restored_parcelas=restored_parcelas,
            )
        )

    return {
        "contracts": len(contracts),
        "restored_cycles": sum(item.restored_cycles for item in resolutions),
        "restored_parcelas": sum(item.restored_parcelas for item in resolutions),
        "resolutions": resolutions,
    }
