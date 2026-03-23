from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha1
from typing import Callable, Iterable, Sequence

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Prefetch
from rest_framework.exceptions import ValidationError

from apps.importacao.models import ArquivoRetornoItem
from apps.tesouraria.models import BaixaManual

from .cycle_timeline import (
    CICLO_TOTAL_PARCELAS,
    count_discounted_parcelas,
    get_contract_cycle_size,
    get_future_generation_threshold,
)
from .models import Ciclo, Contrato, Parcela

CONFLICT_DETAIL_MESSAGE = (
    "Uma ou mais competências já pertencem a outro contrato/ciclo do associado."
)

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
class CompetenciaOwnerResolution:
    status: str
    parcela: Parcela | None
    strategy: str
    conflicts: list[dict[str, object]]


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def list_month_references(start_reference: date, total: int) -> list[date]:
    return [add_months(start_reference, index) for index in range(total)]


def serialize_conflict_parcela(parcela: Parcela) -> dict[str, object]:
    contrato = parcela.ciclo.contrato
    return {
        "referencia_mes": parcela.referencia_mes.isoformat(),
        "contrato_id": contrato.id,
        "contrato_codigo": contrato.codigo,
        "ciclo_id": parcela.ciclo_id,
        "parcela_id": parcela.id,
        "status": parcela.status,
    }


def _parcelas_queryset():
    return Parcela.all_objects.filter(deleted_at__isnull=True).exclude(
        status=Parcela.Status.CANCELADO
    )


def _parcelas_with_context_queryset():
    return _parcelas_queryset().select_related(
        "associado",
        "ciclo",
        "ciclo__contrato",
    )


def _prefetch_conflict_context(queryset):
    return queryset.prefetch_related(
        Prefetch("itens_retorno"),
        Prefetch("ciclo__parcelas"),
    ).select_related("baixa_manual")


def _query_conflicting_parcelas(
    *,
    associado_id: int,
    referencias: Sequence[date],
    exclude_parcela_ids: Iterable[int] | None = None,
    for_update: bool = False,
) -> list[Parcela]:
    if not referencias:
        return []

    queryset = _parcelas_with_context_queryset().filter(
        associado_id=associado_id,
        referencia_mes__in=sorted(set(referencias)),
    )
    exclude_ids = [parcela_id for parcela_id in (exclude_parcela_ids or []) if parcela_id]
    if exclude_ids:
        queryset = queryset.exclude(pk__in=exclude_ids)
    if for_update:
        queryset = queryset.select_for_update()
    return list(
        queryset.order_by(
            "referencia_mes",
            "-ciclo__contrato__data_aprovacao",
            "-ciclo__contrato__created_at",
            "-ciclo__numero",
            "numero",
            "-id",
        )
    )


def collect_competencia_conflicts(
    *,
    associado_id: int,
    referencias: Sequence[date],
    exclude_parcela_ids: Iterable[int] | None = None,
    for_update: bool = False,
) -> list[dict[str, object]]:
    conflicts = _query_conflicting_parcelas(
        associado_id=associado_id,
        referencias=referencias,
        exclude_parcela_ids=exclude_parcela_ids,
        for_update=for_update,
    )
    return [serialize_conflict_parcela(parcela) for parcela in conflicts]


def raise_competencia_conflict(
    *,
    associado_id: int,
    referencias: Sequence[date],
    exclude_parcela_ids: Iterable[int] | None = None,
    for_update: bool = False,
) -> None:
    conflicts = collect_competencia_conflicts(
        associado_id=associado_id,
        referencias=referencias,
        exclude_parcela_ids=exclude_parcela_ids,
        for_update=for_update,
    )
    if conflicts:
        raise ValidationError(
            {
                "detail": CONFLICT_DETAIL_MESSAGE,
                "conflicts": conflicts,
            }
        )


def _itens_retorno_count(parcela: Parcela) -> int:
    prefetched = getattr(parcela, "_prefetched_objects_cache", {})
    if "itens_retorno" in prefetched:
        return len(prefetched["itens_retorno"])
    return parcela.itens_retorno.count()


def parcela_has_financial_evidence(parcela: Parcela) -> bool:
    if parcela.data_pagamento is not None:
        return True
    if parcela.status == Parcela.Status.DESCONTADO:
        return True
    if _itens_retorno_count(parcela) > 0:
        return True
    try:
        parcela.baixa_manual
    except ObjectDoesNotExist:
        return False
    return True


def _fallback_parcela_resolution_key(parcela: Parcela) -> tuple[object, ...]:
    contrato = parcela.ciclo.contrato
    return (
        contrato.data_aprovacao or contrato.data_contrato or date.min,
        contrato.created_at,
        -CONTRACT_STATUS_PRIORITY.get(contrato.status, 99),
        -CYCLE_STATUS_PRIORITY.get(parcela.ciclo.status, 99),
        parcela.ciclo.numero,
        parcela.numero,
        parcela.id,
    )


def _latest_status_parcela_key(parcela: Parcela) -> tuple[object, ...]:
    return (
        parcela.updated_at,
        parcela.created_at,
        parcela.id,
    )


def _cycle_resolution_key(cycle: Ciclo) -> tuple[object, ...]:
    parcelas = _iter_cycle_parcelas(cycle)
    parcelas_pagas = sum(
        1 for parcela in parcelas if parcela.status == Parcela.Status.DESCONTADO
    )
    itens_retorno = sum(_itens_retorno_count(parcela) for parcela in parcelas)
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


def resolve_month_parcela_conflict(parcelas: Sequence[Parcela]) -> CompetenciaOwnerResolution:
    if not parcelas:
        return CompetenciaOwnerResolution(
            status="not_found",
            parcela=None,
            strategy="not_found",
            conflicts=[],
        )

    conflicts = [serialize_conflict_parcela(parcela) for parcela in parcelas]
    if len(parcelas) == 1:
        return CompetenciaOwnerResolution(
            status="resolved",
            parcela=parcelas[0],
            strategy="single_match",
            conflicts=conflicts,
        )

    evidenced = [parcela for parcela in parcelas if parcela_has_financial_evidence(parcela)]
    if len(evidenced) > 1:
        return CompetenciaOwnerResolution(
            status="manual_required",
            parcela=None,
            strategy="manual_required",
            conflicts=conflicts,
        )
    if len(evidenced) == 1:
        return CompetenciaOwnerResolution(
            status="resolved",
            parcela=evidenced[0],
            strategy="financial_evidence",
            conflicts=conflicts,
        )
    winner = max(parcelas, key=_fallback_parcela_resolution_key)
    return CompetenciaOwnerResolution(
        status="resolved",
        parcela=winner,
        strategy="latest_approved_contract",
        conflicts=conflicts,
    )


def resolve_competencia_owner(
    *,
    associado_id: int,
    referencia_mes: date,
    for_update: bool = False,
) -> CompetenciaOwnerResolution:
    candidates = _query_conflicting_parcelas(
        associado_id=associado_id,
        referencias=[referencia_mes],
        for_update=for_update,
    )
    return resolve_month_parcela_conflict(candidates)


def resolve_processing_competencia_parcela(
    *,
    associado_id: int,
    referencia_mes: date,
    for_update: bool = False,
) -> Parcela | None:
    candidates = _query_conflicting_parcelas(
        associado_id=associado_id,
        referencias=[referencia_mes],
        for_update=for_update,
    )
    if not candidates:
        return None
    return max(candidates, key=_latest_status_parcela_key)


def _build_group_id(
    *,
    associado_id: int,
    cycle_ids: Sequence[int],
    months: Sequence[date],
) -> str:
    payload = "|".join(
        [
            str(associado_id),
            ",".join(str(cycle_id) for cycle_id in sorted(set(cycle_ids))),
            ",".join(month.strftime("%Y-%m") for month in sorted(set(months))),
        ]
    )
    return f"cg-{associado_id}-{sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def _cycle_active_references(cycle: Ciclo) -> tuple[date, ...]:
    parcelas = getattr(cycle, "_prefetched_objects_cache", {}).get("parcelas")
    if parcelas is None:
        parcelas = cycle.parcelas.all()
    return tuple(
        sorted(
            parcela.referencia_mes
            for parcela in parcelas
            if parcela.deleted_at is None and parcela.status != Parcela.Status.CANCELADO
        )
    )


def _build_conflict_groups_from_parcelas(parcelas: Sequence[Parcela]) -> list[dict[str, object]]:
    month_buckets: dict[tuple[int, date], list[Parcela]] = defaultdict(list)
    cycle_by_id: dict[int, Ciclo] = {}
    associado_payload: dict[int, tuple[str, str]] = {}

    for parcela in parcelas:
        if parcela.deleted_at is not None or parcela.status == Parcela.Status.CANCELADO:
            continue
        month_buckets[(parcela.associado_id, parcela.referencia_mes)].append(parcela)
        cycle_by_id[parcela.ciclo_id] = parcela.ciclo
        associado_payload[parcela.associado_id] = (
            getattr(parcela.associado, "cpf_cnpj", ""),
            getattr(parcela.associado, "nome_completo", ""),
        )

    conflict_buckets = {
        key: bucket for key, bucket in month_buckets.items() if len(bucket) > 1
    }
    if not conflict_buckets:
        return []

    conflict_buckets_by_associado: dict[int, list[tuple[date, list[Parcela]]]] = defaultdict(list)
    for (associado_id, referencia_mes), bucket in conflict_buckets.items():
        conflict_buckets_by_associado[associado_id].append((referencia_mes, bucket))

    groups: list[dict[str, object]] = []

    for associado_id, buckets in conflict_buckets_by_associado.items():
        adjacency: dict[int, set[int]] = defaultdict(set)
        component_cycle_ids: set[int] = set()

        for _referencia_mes, bucket in buckets:
            cycle_ids = sorted({parcela.ciclo_id for parcela in bucket})
            if not cycle_ids:
                continue
            component_cycle_ids.update(cycle_ids)
            if len(cycle_ids) == 1:
                adjacency[cycle_ids[0]]
                continue
            head = cycle_ids[0]
            for cycle_id in cycle_ids[1:]:
                adjacency[head].add(cycle_id)
                adjacency[cycle_id].add(head)

        pending = deque(sorted(component_cycle_ids))
        visited: set[int] = set()

        while pending:
            cycle_id = pending.popleft()
            if cycle_id in visited:
                continue
            component = set([cycle_id])
            queue = deque([cycle_id])

            while queue:
                current = queue.popleft()
                if current in visited:
                    continue
                visited.add(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in component:
                        component.add(neighbor)
                        queue.append(neighbor)

            component_buckets = []
            for referencia_mes, bucket in buckets:
                relevant = [parcela for parcela in bucket if parcela.ciclo_id in component]
                if relevant:
                    component_buckets.append((referencia_mes, relevant))

            component_cycles = [cycle_by_id[item_id] for item_id in sorted(component)]
            month_resolutions = []
            canonical_cycle_ids = set()
            for referencia_mes, relevant in sorted(component_buckets, key=lambda item: item[0]):
                resolution = resolve_month_parcela_conflict(relevant)
                canonical_cycle_id = resolution.parcela.ciclo_id if resolution.parcela else None
                if canonical_cycle_id:
                    canonical_cycle_ids.add(canonical_cycle_id)
                month_resolutions.append(
                    {
                        "referencia_mes": referencia_mes.isoformat(),
                        "status": resolution.status,
                        "strategy": resolution.strategy,
                        "canonical_contrato_id": (
                            resolution.parcela.ciclo.contrato_id if resolution.parcela else None
                        ),
                        "canonical_ciclo_id": canonical_cycle_id,
                        "canonical_parcela_id": resolution.parcela.id if resolution.parcela else None,
                        "conflicts": resolution.conflicts,
                    }
                )

            signatures = {
                (
                    cycle.numero,
                    cycle.data_inicio,
                    cycle.data_fim,
                    _cycle_active_references(cycle),
                )
                for cycle in component_cycles
            }
            is_exact_duplicate = len(component_cycles) > 1 and len(signatures) == 1

            if any(item["status"] == "manual_required" for item in month_resolutions):
                classification = "manual_required"
            else:
                classification = "exact_duplicate_cycle" if is_exact_duplicate else "partial_overlap"

            manual_reasons = []
            canonical_cycle_id = None
            auto_repairable = False
            if classification == "manual_required":
                manual_reasons.append(
                    "Mais de uma parcela com evidência financeira real foi encontrada no mesmo mês."
                )
            elif is_exact_duplicate:
                canonical_cycle_id = sorted(component_cycles, key=_cycle_resolution_key)[0].id
                auto_repairable = True
            elif len(canonical_cycle_ids) != 1:
                manual_reasons.append(
                    "Os meses conflitantes não convergem para um único ciclo canônico."
                )
            elif len(component_cycles) <= 1:
                manual_reasons.append(
                    "O conflito está restrito ao mesmo ciclo e requer análise manual."
                )
            else:
                canonical_cycle_id = next(iter(canonical_cycle_ids))
                auto_repairable = True

            cpf_cnpj, nome_associado = associado_payload.get(associado_id, ("", ""))
            groups.append(
                {
                    "group_id": _build_group_id(
                        associado_id=associado_id,
                        cycle_ids=[cycle.id for cycle in component_cycles],
                        months=[
                            date.fromisoformat(item["referencia_mes"])
                            for item in month_resolutions
                        ],
                    ),
                    "associado_id": associado_id,
                    "cpf_cnpj": cpf_cnpj,
                    "nome_associado": nome_associado,
                    "classification": classification,
                    "auto_repairable": auto_repairable,
                    "canonical_cycle_id": canonical_cycle_id,
                    "canonical_contract_id": (
                        cycle_by_id[canonical_cycle_id].contrato_id if canonical_cycle_id else None
                    ),
                    "cycle_ids": [cycle.id for cycle in component_cycles],
                    "contract_ids": sorted({cycle.contrato_id for cycle in component_cycles}),
                    "months": [item["referencia_mes"] for item in month_resolutions],
                    "month_resolutions": month_resolutions,
                    "manual_reasons": manual_reasons,
                }
            )

    return sorted(groups, key=lambda item: (item["associado_id"], item["group_id"]))


def resolve_noncanonical_cycle_ids(cycles: Sequence[Ciclo]) -> set[int]:
    if not cycles:
        return set()

    active_parcelas: list[Parcela] = []
    for cycle in cycles:
        prefetched = getattr(cycle, "_prefetched_objects_cache", {}).get("parcelas")
        parcelas = list(prefetched) if prefetched is not None else list(cycle.parcelas.all())
        for parcela in parcelas:
            if not getattr(parcela, "ciclo_id", None):
                parcela.ciclo = cycle
                parcela.ciclo_id = cycle.id
            if not getattr(parcela, "associado_id", None):
                parcela.associado = cycle.contrato.associado
                parcela.associado_id = cycle.contrato.associado_id
            active_parcelas.append(parcela)

    losing_cycle_ids: set[int] = set()
    for group in _build_conflict_groups_from_parcelas(active_parcelas):
        canonical_cycle_id = group.get("canonical_cycle_id")
        if group.get("auto_repairable") and canonical_cycle_id:
            losing_cycle_ids.update(
                cycle_id
                for cycle_id in group["cycle_ids"]
                if cycle_id != canonical_cycle_id
            )
    return losing_cycle_ids


def find_competencia_conflict_groups(
    *,
    associado_id: int | None = None,
    cpf_cnpj: str | None = None,
) -> list[dict[str, object]]:
    queryset = _prefetch_conflict_context(_parcelas_with_context_queryset())
    if associado_id:
        queryset = queryset.filter(associado_id=associado_id)
    if cpf_cnpj:
        queryset = queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    return _build_conflict_groups_from_parcelas(list(queryset))


def validate_existing_cycle_competencias(ciclo: Ciclo) -> list[dict[str, object]]:
    parcelas = list(ciclo.parcelas.exclude(status=Parcela.Status.CANCELADO))
    return collect_competencia_conflicts(
        associado_id=ciclo.contrato.associado_id,
        referencias=[parcela.referencia_mes for parcela in parcelas],
        exclude_parcela_ids=[parcela.id for parcela in parcelas],
    )


def sync_competencia_locks_for_references(
    *,
    associado_id: int,
    referencias: Sequence[date],
) -> None:
    for referencia_mes in sorted(set(referencias)):
        Parcela.sync_group_locks(
            associado_id=associado_id,
            referencia_mes=referencia_mes,
        )


def propagate_competencia_status(source_parcela: Parcela) -> int:
    if (
        not source_parcela.associado_id
        or not source_parcela.referencia_mes
        or source_parcela.deleted_at is not None
        or source_parcela.status == Parcela.Status.CANCELADO
    ):
        return 0

    data_pagamento = (
        source_parcela.data_pagamento
        if source_parcela.status in {Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}
        else None
    )
    synchronized = (
        Parcela.all_objects.filter(
            associado_id=source_parcela.associado_id,
            referencia_mes=source_parcela.referencia_mes,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .exclude(pk=source_parcela.pk)
        .update(
            status=source_parcela.status,
            data_pagamento=data_pagamento,
        )
    )
    Parcela.sync_group_locks(
        associado_id=source_parcela.associado_id,
        referencia_mes=source_parcela.referencia_mes,
    )
    return synchronized


def create_cycle_with_parcelas(
    *,
    contrato: Contrato,
    numero: int,
    competencia_inicial: date,
    parcelas_total: int,
    ciclo_status: str,
    parcela_status: str,
    data_vencimento_fn: Callable[[date], date] | None = None,
    valor_mensalidade: Decimal | None = None,
    valor_total: Decimal | None = None,
) -> tuple[Ciclo, list[Parcela]]:
    referencias = list_month_references(competencia_inicial, parcelas_total)

    mensalidade = valor_mensalidade or contrato.valor_mensalidade
    total = valor_total or (mensalidade * Decimal(parcelas_total)).quantize(Decimal("0.01"))
    ciclo = Ciclo.objects.create(
        contrato=contrato,
        numero=numero,
        data_inicio=competencia_inicial,
        data_fim=referencias[-1],
        status=ciclo_status,
        valor_total=total,
    )

    parcelas = [
        Parcela(
            ciclo=ciclo,
            associado=contrato.associado,
            numero=index + 1,
            referencia_mes=referencia,
            valor=mensalidade,
            data_vencimento=(
                data_vencimento_fn(referencia) if data_vencimento_fn else referencia
            ),
            status=parcela_status,
        )
        for index, referencia in enumerate(referencias)
    ]
    Parcela.objects.bulk_create(parcelas)
    sync_competencia_locks_for_references(
        associado_id=contrato.associado_id,
        referencias=referencias,
    )
    return ciclo, list(ciclo.parcelas.order_by("numero"))


def ensure_future_cycle_for_renewal(
    ciclo: Ciclo,
    *,
    parcelas_minimas: int | None = None,
) -> tuple[Ciclo | None, bool]:
    if ciclo.status == Ciclo.Status.FUTURO:
        return ciclo, False

    if parcelas_minimas is None:
        parcelas_minimas = get_future_generation_threshold(ciclo)

    parcelas_pagas = count_discounted_parcelas(ciclo)
    if parcelas_pagas < parcelas_minimas:
        return None, False

    proximo_ciclo = ciclo.contrato.ciclos.filter(numero=ciclo.numero + 1).first()
    if proximo_ciclo is not None:
        return proximo_ciclo, False

    cycle_size = get_contract_cycle_size(ciclo)
    competencia_inicial = add_months(ciclo.data_fim.replace(day=1), 1)
    novo_ciclo, _parcelas = create_cycle_with_parcelas(
        contrato=ciclo.contrato,
        numero=ciclo.numero + 1,
        competencia_inicial=competencia_inicial,
        parcelas_total=cycle_size,
        ciclo_status=Ciclo.Status.FUTURO,
        parcela_status=Parcela.Status.FUTURO,
        valor_mensalidade=ciclo.contrato.valor_mensalidade,
        valor_total=(
            ciclo.contrato.valor_mensalidade * Decimal(str(cycle_size))
        ).quantize(Decimal("0.01")),
    )
    return novo_ciclo, True


def ativar_ciclo_futuro(ciclo: Ciclo, parcela_ja_descontada: Parcela | None = None) -> bool:
    """
    Ativa um ciclo FUTURO na primeira parcela paga.
    - Sets ciclo.status = ABERTO
    - Sets all FUTURO parcelas (exceto a já DESCONTADA) to EM_ABERTO
    - Returns True se ativou, False se já estava ativo.
    """
    if ciclo.status != Ciclo.Status.FUTURO:
        return False

    ciclo.status = Ciclo.Status.ABERTO
    ciclo.save(update_fields=["status", "updated_at"])

    qs = ciclo.parcelas.filter(status=Parcela.Status.FUTURO)
    if parcela_ja_descontada:
        qs = qs.exclude(pk=parcela_ja_descontada.pk)

    qs.update(status=Parcela.Status.EM_ABERTO)
    return True


def flatten_conflict_groups(groups: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for group in groups:
        for month_resolution in group["month_resolutions"]:
            for conflict in month_resolution["conflicts"]:
                rows.append(
                    {
                        "group_id": group["group_id"],
                        "associado_id": group["associado_id"],
                        "cpf_cnpj": group["cpf_cnpj"],
                        "nome_associado": group["nome_associado"],
                        "classification": group["classification"],
                        "auto_repairable": group["auto_repairable"],
                        "canonical_cycle_id": month_resolution["canonical_ciclo_id"],
                        "canonical_contract_id": month_resolution["canonical_contrato_id"],
                        "strategy": month_resolution["strategy"],
                        "resolution_status": month_resolution["status"],
                        **conflict,
                    }
                )
    return rows


def _repair_group_summary(group: dict[str, object]) -> dict[str, object]:
    canonical_cycle_id = group.get("canonical_cycle_id")
    return {
        "group_id": group["group_id"],
        "classification": group["classification"],
        "auto_repairable": group["auto_repairable"],
        "canonical_cycle_id": canonical_cycle_id,
        "losing_cycle_ids": [
            cycle_id for cycle_id in group["cycle_ids"] if cycle_id != canonical_cycle_id
        ],
        "manual_actions": [],
        "reassigned_return_items": 0,
        "reassigned_baixas_manuais": 0,
        "reassigned_confirmacoes": 0,
        "reassigned_refinanciamentos": 0,
        "reassigned_comprovantes": 0,
        "cancelled_cycles": 0,
        "cancelled_contracts": 0,
    }


def _iter_cycle_parcelas(cycle: Ciclo) -> list[Parcela]:
    prefetched = getattr(cycle, "_prefetched_objects_cache", {}).get("parcelas")
    return list(prefetched) if prefetched is not None else list(cycle.parcelas.all())


def _record_manual_action(summary: dict[str, object], message: str) -> None:
    manual_actions = summary.setdefault("manual_actions", [])
    if message not in manual_actions:
        manual_actions.append(message)


@transaction.atomic
def repair_conflict_group(
    *,
    group_id: str,
    execute: bool = False,
) -> dict[str, object]:
    groups = {group["group_id"]: group for group in find_competencia_conflict_groups()}
    if group_id not in groups:
        raise ValidationError({"detail": f"Grupo de conflito não encontrado: {group_id}"})

    group = groups[group_id]
    summary = _repair_group_summary(group)
    if not group["auto_repairable"]:
        raise ValidationError(
            {
                "detail": "O grupo selecionado exige revisão manual antes do reparo.",
                "manual_reasons": group["manual_reasons"],
            }
        )

    canonical_cycle = (
        Ciclo.objects.select_related("contrato", "contrato__associado")
        .prefetch_related("parcelas")
        .get(pk=group["canonical_cycle_id"])
    )
    canonical_parcelas = {
        parcela.referencia_mes: parcela
        for parcela in _iter_cycle_parcelas(canonical_cycle)
        if parcela.deleted_at is None and parcela.status != Parcela.Status.CANCELADO
    }
    losing_cycles = list(
        Ciclo.objects.select_related("contrato")
        .prefetch_related("parcelas")
        .filter(pk__in=summary["losing_cycle_ids"])
    )

    for losing_cycle in losing_cycles:
        for parcela in _iter_cycle_parcelas(losing_cycle):
            target = canonical_parcelas.get(parcela.referencia_mes)
            if target is None and ArquivoRetornoItem.objects.filter(parcela=parcela).exists():
                _record_manual_action(
                    summary,
                    (
                        f"ArquivoRetornoItem vinculado à parcela {parcela.id} não possui "
                        f"destino canônico para {parcela.referencia_mes:%Y-%m}."
                    ),
                )

            try:
                baixa_manual = parcela.baixa_manual
            except ObjectDoesNotExist:
                baixa_manual = None

            if baixa_manual:
                if target is None:
                    _record_manual_action(
                        summary,
                        f"BaixaManual {baixa_manual.id} da parcela {parcela.id} exige revisão manual.",
                    )
                else:
                    try:
                        target.baixa_manual
                    except ObjectDoesNotExist:
                        if execute:
                            baixa_manual.parcela = target
                            baixa_manual.save(update_fields=["parcela", "updated_at"])
                        summary["reassigned_baixas_manuais"] += 1
                    else:
                        _record_manual_action(
                            summary,
                            (
                                f"BaixaManual da parcela {parcela.id} conflita com "
                                f"outra baixa já existente na parcela {target.id}."
                            ),
                        )

            if execute and target:
                parcela.status = target.status
                parcela.data_pagamento = (
                    target.data_pagamento
                    if target.status in {Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}
                    else None
                )
                parcela.save(
                    update_fields=[
                        "status",
                        "data_pagamento",
                        "competencia_lock",
                        "updated_at",
                    ]
                )

    return summary
