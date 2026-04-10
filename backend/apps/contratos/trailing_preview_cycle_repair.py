from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.refinanciamento.models import Refinanciamento

from .cycle_rebuild import rebuild_contract_cycle_state, relink_contract_documents
from .models import Ciclo, Contrato, Parcela
from .special_references import is_forced_outside_cycle_reference
from .cycle_timeline import get_contract_cycle_size


APRIL_2026_REFERENCE = date(2026, 4, 1)
RESOLVED_CYCLE_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
    "quitada",
}


@dataclass
class TrailingPreviewCycleRepairReport:
    candidate_contracts: int = 0
    corrected_contracts: int = 0
    restored_approved_operational: int = 0
    restored_apto_operational: int = 0
    reparcelled_rows: int = 0
    cycles_soft_deleted: int = 0
    cycle_one_completed: int = 0
    remaining_candidates: int = 0

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _active_cycle_rows(ciclo: Ciclo) -> list[Parcela]:
    return list(
        Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "numero", "id")
    )


def _candidate_contracts() -> list[Contrato]:
    queryset = (
        Contrato.objects.select_related("associado")
        .filter(deleted_at__isnull=True)
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("id")
    )
    candidates: list[Contrato] = []
    for contrato in queryset.iterator():
        ciclos = list(
            contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id")
        )
        if len(ciclos) < 2:
            continue
        latest = ciclos[-1]
        latest_rows = _active_cycle_rows(latest)
        if not latest_rows:
            continue
        if any(row.referencia_mes != APRIL_2026_REFERENCE for row in latest_rows):
            continue
        if any(str(row.status) != Parcela.Status.EM_PREVISAO for row in latest_rows):
            continue
        candidates.append(contrato)
    return candidates


def _desired_operational_status(contrato: Contrato) -> str:
    soft_deleted = list(
        Refinanciamento.all_objects.filter(
            contrato_origem=contrato,
            deleted_at__isnull=False,
            legacy_refinanciamento_id__isnull=True,
            origem=Refinanciamento.Origem.OPERACIONAL,
        )
        .order_by("-updated_at", "-created_at", "-id")
    )
    if any(item.status == Refinanciamento.Status.APROVADO_PARA_RENOVACAO for item in soft_deleted):
        return Refinanciamento.Status.APROVADO_PARA_RENOVACAO
    return Refinanciamento.Status.APTO_A_RENOVAR


def _cycle_candidate_rows(contrato: Contrato) -> list[Parcela]:
    rows = list(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "ciclo__numero", "numero", "id")
    )
    return [
        row
        for row in rows
        if not is_forced_outside_cycle_reference(row.referencia_mes)
        and (
            str(row.status) in RESOLVED_CYCLE_STATUSES
            or str(row.status) == Parcela.Status.EM_PREVISAO
        )
    ]


def _reassign_rows_to_cycles(contrato: Contrato) -> tuple[bool, int, int, int]:
    ciclos = list(
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
    )
    if len(ciclos) < 2:
        return False, 0, 0, 0

    latest = ciclos[-1]
    target_cycles = ciclos[:-1]
    if not target_cycles:
        return False, 0, 0, 0

    cycle_size = get_contract_cycle_size(contrato)
    rows = _cycle_candidate_rows(contrato)
    if not rows:
        return False, 0, 0, 0

    changed = False
    reparcelled_rows = 0
    cycle_one_completed = 0
    cycles_soft_deleted = 0
    row_to_target: dict[int, Ciclo] = {}
    for index, row in enumerate(rows):
        cycle_index = min(index // cycle_size, len(target_cycles) - 1)
        row_to_target[row.id] = target_cycles[cycle_index]

    existing_max = max((int(row.numero or 0) for row in rows), default=0)
    temp_base = existing_max + 1000
    for offset, row in enumerate(rows, start=1):
        temp_number = temp_base + offset
        if row.numero == temp_number:
            continue
        row.numero = temp_number
        row.save(update_fields=["numero", "updated_at"])
        changed = True

    for row in rows:
        target_cycle = row_to_target[row.id]
        changed_fields: list[str] = []
        if row.ciclo_id != target_cycle.id:
            row.ciclo = target_cycle
            changed_fields.append("ciclo")
        if row.layout_bucket != Parcela.LayoutBucket.CYCLE:
            row.layout_bucket = Parcela.LayoutBucket.CYCLE
            changed_fields.append("layout_bucket")
        if changed_fields:
            row.save(update_fields=[*changed_fields, "updated_at"])
            changed = True
            reparcelled_rows += 1

    for cycle in target_cycles:
        all_cycle_rows = _active_cycle_rows(cycle)
        cycle_rows = [
            row
            for row in all_cycle_rows
            if not is_forced_outside_cycle_reference(row.referencia_mes)
            and (
                str(row.status) in RESOLVED_CYCLE_STATUSES
                or str(row.status) == Parcela.Status.EM_PREVISAO
            )
        ]
        cycle_rows = sorted(cycle_rows, key=lambda row: (row.referencia_mes, row.id))
        remaining_rows = [row for row in all_cycle_rows if row.id not in {item.id for item in cycle_rows}]
        temp_cycle_base = max((int(row.numero or 0) for row in all_cycle_rows), default=0) + 1000
        for offset, row in enumerate(all_cycle_rows, start=1):
            temp_number = temp_cycle_base + offset
            if row.numero == temp_number:
                continue
            row.numero = temp_number
            row.save(update_fields=["numero", "updated_at"])
            changed = True
        for number, row in enumerate(cycle_rows, start=1):
            if row.numero == number:
                continue
            row.numero = number
            row.save(update_fields=["numero", "updated_at"])
            changed = True
            reparcelled_rows += 1
        next_number = len(cycle_rows) + 1
        for row in sorted(remaining_rows, key=lambda item: (item.referencia_mes, item.id)):
            if row.numero == next_number:
                next_number += 1
                continue
            row.numero = next_number
            row.save(update_fields=["numero", "updated_at"])
            changed = True
            next_number += 1

        if not cycle_rows:
            continue
        data_inicio = cycle_rows[0].referencia_mes
        data_fim = cycle_rows[-1].referencia_mes
        valor_total = sum((row.valor for row in cycle_rows), start=Decimal("0.00"))
        target_status = (
            Ciclo.Status.APTO_A_RENOVAR
            if cycle.id == target_cycles[-1].id
            else Ciclo.Status.CICLO_RENOVADO
        )
        changed_fields: list[str] = []
        if cycle.data_inicio != data_inicio:
            cycle.data_inicio = data_inicio
            changed_fields.append("data_inicio")
        if cycle.data_fim != data_fim:
            cycle.data_fim = data_fim
            changed_fields.append("data_fim")
        if cycle.valor_total != valor_total:
            cycle.valor_total = valor_total
            changed_fields.append("valor_total")
        if cycle.status != target_status:
            cycle.status = target_status
            changed_fields.append("status")
        if changed_fields:
            cycle.save(update_fields=[*changed_fields, "updated_at"])
            changed = True
        if cycle.numero == 1 and len(cycle_rows) >= cycle_size:
            cycle_one_completed = 1

    latest_rows = _active_cycle_rows(latest)
    if not latest_rows:
        latest.soft_delete()
        changed = True
        cycles_soft_deleted = 1
        return changed, reparcelled_rows, cycle_one_completed, cycles_soft_deleted

    return changed, reparcelled_rows, cycle_one_completed, cycles_soft_deleted


@transaction.atomic
def repair_trailing_preview_cycles(*, apply: bool) -> dict[str, object]:
    report = TrailingPreviewCycleRepairReport()
    candidates = _candidate_contracts()
    report.candidate_contracts = len(candidates)

    if not apply:
        report.remaining_candidates = report.candidate_contracts
        return report.as_dict()

    for contrato in candidates:
        desired_status = _desired_operational_status(contrato)
        changed, reparcelled_rows, cycle_one_completed, cycles_soft_deleted = _reassign_rows_to_cycles(contrato)
        if not changed:
            continue
        if not contrato.admin_manual_layout_enabled:
            contrato.admin_manual_layout_enabled = True
            contrato.admin_manual_layout_updated_at = timezone.now()
            contrato.save(
                update_fields=[
                    "admin_manual_layout_enabled",
                    "admin_manual_layout_updated_at",
                    "updated_at",
                ]
            )
        rebuild_contract_cycle_state(
            contrato,
            execute=True,
            force_active_operational_status=desired_status,
        )
        relink_contract_documents({contrato.id})
        report.corrected_contracts += 1
        report.reparcelled_rows += reparcelled_rows
        report.cycle_one_completed += cycle_one_completed
        report.cycles_soft_deleted += cycles_soft_deleted
        if desired_status == Refinanciamento.Status.APROVADO_PARA_RENOVACAO:
            report.restored_approved_operational += 1
        else:
            report.restored_apto_operational += 1

    report.remaining_candidates = len(_candidate_contracts())
    return report.as_dict()
