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


COMPLETED_CYCLE_STATUSES = {
    Ciclo.Status.CICLO_RENOVADO,
    Ciclo.Status.FECHADO,
}
RESOLVED_CYCLE_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
    "quitada",
}


@dataclass
class IncompleteCycleOneRepairReport:
    candidate_contracts: int = 0
    moved_contracts: int = 0
    downgraded_to_pending: int = 0
    moved_rows: int = 0
    reparcelled_rows: int = 0
    rebuilt_contracts: int = 0
    remaining_invalid_completed_cycle_one: int = 0

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _active_cycle_rows(ciclo: Ciclo) -> list[Parcela]:
    return list(
        Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "numero", "id")
    )


def _cycle_bucket_rows(ciclo: Ciclo) -> list[Parcela]:
    return [
        row
        for row in _active_cycle_rows(ciclo)
        if row.layout_bucket == Parcela.LayoutBucket.CYCLE
        and not is_forced_outside_cycle_reference(row.referencia_mes)
    ]


def _resolved_cycle_bucket_rows(ciclo: Ciclo) -> list[Parcela]:
    return [
        row
        for row in _cycle_bucket_rows(ciclo)
        if str(row.status) in RESOLVED_CYCLE_STATUSES
    ]


def _candidate_contracts() -> list[Contrato]:
    candidates: list[Contrato] = []
    queryset = (
        Contrato.objects.select_related("associado")
        .filter(deleted_at__isnull=True)
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("id")
    )
    for contrato in queryset.iterator():
        ciclo_1 = contrato.ciclos.filter(numero=1, deleted_at__isnull=True).first()
        if not ciclo_1 or ciclo_1.status not in COMPLETED_CYCLE_STATUSES:
            continue
        if len(_resolved_cycle_bucket_rows(ciclo_1)) >= 3:
            continue
        candidates.append(contrato)
    return candidates


def _desired_operational_status(contrato: Contrato) -> str:
    active_operational = (
        Refinanciamento.objects.filter(
            contrato_origem=contrato,
            origem=Refinanciamento.Origem.OPERACIONAL,
        )
        .order_by("-updated_at", "-created_at", "-id")
        .first()
    )
    if active_operational:
        return active_operational.status
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


def _temp_renumber_contract_rows(contrato: Contrato) -> None:
    rows = list(
        Parcela.all_objects.filter(ciclo__contrato=contrato)
        .order_by("ciclo__numero", "numero", "referencia_mes", "id")
    )
    existing_max = max((int(row.numero or 0) for row in rows), default=0)
    temp_base = existing_max + 1000
    for offset, row in enumerate(rows, start=1):
        temp_number = temp_base + offset
        if row.numero == temp_number:
            continue
        row.numero = temp_number
        row.save(update_fields=["numero", "updated_at"])


def _renumber_cycle(ciclo: Ciclo, *, cycle_count: int) -> int:
    all_rows = _active_cycle_rows(ciclo)
    cycle_rows = sorted(_cycle_bucket_rows(ciclo), key=lambda row: (row.referencia_mes, row.id))
    cycle_ids = {row.id for row in cycle_rows}
    remaining_rows = [row for row in all_rows if row.id not in cycle_ids]

    reparcelled_rows = 0
    for number, row in enumerate(cycle_rows, start=1):
        if row.numero == number:
            continue
        row.numero = number
        row.save(update_fields=["numero", "updated_at"])
        reparcelled_rows += 1

    next_number = len(cycle_rows) + 1
    for row in sorted(remaining_rows, key=lambda item: (item.referencia_mes, item.id)):
        if row.numero == next_number:
            next_number += 1
            continue
        row.numero = next_number
        row.save(update_fields=["numero", "updated_at"])
        reparcelled_rows += 1
        next_number += 1

    changed_fields: list[str] = []
    if cycle_rows:
        data_inicio = cycle_rows[0].referencia_mes
        data_fim = cycle_rows[-1].referencia_mes
        valor_total = sum((row.valor for row in cycle_rows), start=Decimal("0.00"))
        if ciclo.data_inicio != data_inicio:
            ciclo.data_inicio = data_inicio
            changed_fields.append("data_inicio")
        if ciclo.data_fim != data_fim:
            ciclo.data_fim = data_fim
            changed_fields.append("data_fim")
        if ciclo.valor_total != valor_total:
            ciclo.valor_total = valor_total
            changed_fields.append("valor_total")

    if ciclo.numero == 1:
        target_status = (
            Ciclo.Status.CICLO_RENOVADO if len(cycle_rows) >= 3 and cycle_count > 1 else
            Ciclo.Status.FECHADO if len(cycle_rows) >= 3 else
            Ciclo.Status.PENDENCIA
        )
        if ciclo.status != target_status:
            ciclo.status = target_status
            changed_fields.append("status")

    if changed_fields:
        ciclo.save(update_fields=[*changed_fields, "updated_at"])
    return reparcelled_rows


def _repair_contract(contrato: Contrato) -> tuple[bool, bool, int, int]:
    ciclos = list(Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id"))
    ciclo_1 = next((ciclo for ciclo in ciclos if ciclo.numero == 1), None)
    if not ciclo_1:
        return False, False, 0, 0

    current_cycle_rows = _cycle_bucket_rows(ciclo_1)
    unresolved_cycle_rows = [
        row for row in current_cycle_rows if str(row.status) not in RESOLVED_CYCLE_STATUSES
    ]
    for row in unresolved_cycle_rows:
        row.layout_bucket = Parcela.LayoutBucket.UNPAID
        if not row.observacao:
            row.observacao = (
                "Competência removida do ciclo 1 por estar não resolvida "
                "durante a correção de ciclo concluído."
            )
            row.save(update_fields=["layout_bucket", "observacao", "updated_at"])
        else:
            row.save(update_fields=["layout_bucket", "updated_at"])

    shortage = max(0, 3 - len(_resolved_cycle_bucket_rows(ciclo_1)))
    moved_rows = 0
    moved_any = bool(unresolved_cycle_rows)

    later_resolved_rows: list[Parcela] = []
    for ciclo in ciclos:
        if ciclo.numero <= 1:
            continue
        for row in _cycle_bucket_rows(ciclo):
            if str(row.status) not in RESOLVED_CYCLE_STATUSES:
                continue
            later_resolved_rows.append(row)
    later_resolved_rows.sort(key=lambda row: (row.referencia_mes, row.ciclo.numero, row.id))

    if shortage and later_resolved_rows:
        _temp_renumber_contract_rows(contrato)
        for row in later_resolved_rows[:shortage]:
            row.ciclo = ciclo_1
            row.layout_bucket = Parcela.LayoutBucket.CYCLE
            row.save(update_fields=["ciclo", "layout_bucket", "updated_at"])
            moved_rows += 1
            moved_any = True

        reparcelled_rows = 0
        for ciclo in ciclos:
            reparcelled_rows += _renumber_cycle(ciclo, cycle_count=len(ciclos))
        return moved_any, False, moved_rows, reparcelled_rows

    if ciclo_1.status != Ciclo.Status.PENDENCIA:
        ciclo_1.status = Ciclo.Status.PENDENCIA
        ciclo_1.save(update_fields=["status", "updated_at"])
        return False, True, 0, 0

    return False, False, 0, 0


@transaction.atomic
def repair_incomplete_cycle_one(*, apply: bool) -> dict[str, object]:
    report = IncompleteCycleOneRepairReport()
    candidates = _candidate_contracts()
    report.candidate_contracts = len(candidates)

    if not apply:
        report.remaining_invalid_completed_cycle_one = report.candidate_contracts
        return report.as_dict()

    for contrato in candidates:
        moved_any, downgraded, moved_rows, reparcelled_rows = _repair_contract(contrato)
        if not moved_any and not downgraded:
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
        report.reparcelled_rows += reparcelled_rows
        if moved_any:
            desired_status = _desired_operational_status(contrato)
            rebuild_contract_cycle_state(
                contrato,
                execute=True,
                force_active_operational_status=desired_status,
            )
            relink_contract_documents({contrato.id})
            report.moved_contracts += 1
            report.moved_rows += moved_rows
            report.rebuilt_contracts += 1
        if downgraded:
            report.downgraded_to_pending += 1

    report.remaining_invalid_completed_cycle_one = len(_candidate_contracts())
    return report.as_dict()
