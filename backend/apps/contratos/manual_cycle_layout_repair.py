from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.refinanciamento.models import Refinanciamento

from .cycle_rebuild import relink_contract_documents
from .models import Ciclo, Contrato, Parcela
from .special_references import is_forced_outside_cycle_reference

PROJECTION_STATUS_QUITADA = "quitada"
OUTSIDE_CYCLE_HINTS = (
    "fora do ciclo",
    "quitada manualmente",
)


@dataclass
class ManualCycleLayoutRepairReport:
    scanned_contracts: int = 0
    changed_contracts: int = 0
    parcelas_updated: int = 0
    parcelas_rebucketed: int = 0
    parcelas_status_fixed: int = 0
    parcelas_renumbered: int = 0
    refinanciamentos_relinked: int = 0
    documents_relinked: int = 0

    def as_dict(self) -> dict[str, int]:
        return self.__dict__.copy()


def _add_months(reference: date, months: int) -> date:
    month_index = reference.month - 1 + months
    year = reference.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _parse_cycle_key(value: str) -> list[date]:
    refs: list[date] = []
    for chunk in (value or "").split("|"):
        if not chunk:
            continue
        year, month = chunk.split("-", 1)
        refs.append(date(int(year), int(month), 1))
    return refs


def _cycle_range_refs(ciclo: Ciclo) -> list[date]:
    refs: list[date] = []
    current = ciclo.data_inicio.replace(day=1)
    end = ciclo.data_fim.replace(day=1)
    while current <= end:
        refs.append(current)
        current = _add_months(current, 1)
    return refs


def _desired_bucket_and_status(
    *,
    parcela: Parcela,
    latest_cycle_number: int,
    current_month: date,
) -> tuple[str, str]:
    bucket = str(parcela.layout_bucket or Parcela.LayoutBucket.CYCLE)
    status = str(parcela.status or "")
    observacao = (parcela.observacao or "").lower()
    forced_outside_cycle = is_forced_outside_cycle_reference(parcela.referencia_mes)

    if bucket != Parcela.LayoutBucket.CYCLE:
        return bucket, status

    if forced_outside_cycle:
        if status in {
            Parcela.Status.DESCONTADO,
            Parcela.Status.LIQUIDADA,
            PROJECTION_STATUS_QUITADA,
        }:
            return Parcela.LayoutBucket.UNPAID, PROJECTION_STATUS_QUITADA
        return Parcela.LayoutBucket.UNPAID, Parcela.Status.NAO_DESCONTADO

    if status in {Parcela.Status.NAO_DESCONTADO, PROJECTION_STATUS_QUITADA}:
        return Parcela.LayoutBucket.UNPAID, status

    if status == Parcela.Status.EM_PREVISAO and (
        parcela.referencia_mes.replace(day=1) < current_month
        or parcela.ciclo.numero < latest_cycle_number
        or parcela.ciclo.status == Ciclo.Status.CICLO_RENOVADO
    ):
        return Parcela.LayoutBucket.UNPAID, Parcela.Status.NAO_DESCONTADO

    if any(hint in observacao for hint in OUTSIDE_CYCLE_HINTS):
        if status in {
            Parcela.Status.DESCONTADO,
            Parcela.Status.LIQUIDADA,
            PROJECTION_STATUS_QUITADA,
        }:
            return Parcela.LayoutBucket.UNPAID, PROJECTION_STATUS_QUITADA

    return bucket, status


def _relink_refinanciamentos_for_contract(contrato: Contrato) -> int:
    updated = 0
    cycles = list(
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
    )
    if not cycles:
        return updated

    cycle_refs = {ciclo.id: _cycle_range_refs(ciclo) for ciclo in cycles}
    for refinanciamento in Refinanciamento.objects.filter(
        contrato_origem=contrato,
        deleted_at__isnull=True,
        ciclo_destino__isnull=True,
    ).order_by("id"):
        desired_refs = _parse_cycle_key(refinanciamento.cycle_key)
        if not desired_refs:
            continue
        match = next(
            (
                ciclo
                for ciclo in cycles
                if cycle_refs.get(ciclo.id) == desired_refs
            ),
            None,
        )
        if match is None:
            continue
        if Refinanciamento.objects.filter(
            ciclo_destino=match,
            deleted_at__isnull=True,
        ).exclude(pk=refinanciamento.pk).exists():
            continue
        refinanciamento.ciclo_destino = match
        refinanciamento.save(update_fields=["ciclo_destino", "updated_at"])
        updated += 1
    return updated


def repair_manual_cycle_layouts(
    *,
    apply: bool,
    contrato_id: int | None = None,
    cpf: str | None = None,
) -> dict[str, int]:
    report = ManualCycleLayoutRepairReport()
    queryset = Contrato.objects.filter(
        admin_manual_layout_enabled=True,
        deleted_at__isnull=True,
    ).exclude(status=Contrato.Status.CANCELADO)
    if contrato_id is not None:
        queryset = queryset.filter(id=contrato_id)
    if cpf:
        queryset = queryset.filter(associado__cpf_cnpj=cpf)

    current_month = timezone.localdate().replace(day=1)
    affected_contract_ids: set[int] = set()

    for contrato in queryset.select_related("associado").order_by("id"):
        report.scanned_contracts += 1
        ciclos = list(
            Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
        )
        if not ciclos:
            continue
        latest_cycle_number = max(ciclo.numero for ciclo in ciclos)
        active_parcelas = list(
            Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .select_related("ciclo")
            .order_by("ciclo__numero", "numero", "id")
        )
        changed = False

        if apply:
            with transaction.atomic():
                for parcela in active_parcelas:
                    desired_bucket, desired_status = _desired_bucket_and_status(
                        parcela=parcela,
                        latest_cycle_number=latest_cycle_number,
                        current_month=current_month,
                    )
                    changed_fields: list[str] = []
                    if parcela.layout_bucket != desired_bucket:
                        parcela.layout_bucket = desired_bucket
                        changed_fields.append("layout_bucket")
                        report.parcelas_rebucketed += 1
                    if str(parcela.status) != desired_status:
                        parcela.status = desired_status
                        changed_fields.append("status")
                        report.parcelas_status_fixed += 1
                        if desired_status == Parcela.Status.NAO_DESCONTADO and parcela.data_pagamento is not None:
                            parcela.data_pagamento = None
                            changed_fields.append("data_pagamento")
                    if changed_fields:
                        parcela.save(update_fields=[*changed_fields, "updated_at"])
                        report.parcelas_updated += 1
                        changed = True

                for ciclo in ciclos:
                    cycle_parcelas = list(
                        Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
                        .exclude(status=Parcela.Status.CANCELADO)
                        .order_by("numero", "id")
                    )
                    all_cycle_parcelas = list(
                        Parcela.all_objects.filter(ciclo=ciclo).order_by("numero", "id")
                    )
                    ordered = sorted(
                        cycle_parcelas,
                        key=lambda parcela: (
                            0
                            if parcela.layout_bucket == Parcela.LayoutBucket.CYCLE
                            else 1
                            if parcela.layout_bucket == Parcela.LayoutBucket.UNPAID
                            else 2,
                            parcela.referencia_mes,
                            parcela.id,
                        ),
                    )
                    if not ordered:
                        continue
                    needs_renumber = any(
                        parcela.numero != final_number
                        for final_number, parcela in enumerate(ordered, start=1)
                    )
                    if not needs_renumber:
                        continue
                    temp_start = (
                        max((parcela.numero for parcela in all_cycle_parcelas), default=0)
                        + len(all_cycle_parcelas)
                        + 100
                    )
                    for offset, parcela in enumerate(all_cycle_parcelas, start=0):
                        parcela.numero = temp_start + offset
                        parcela.save(update_fields=["numero", "updated_at"])
                    for final_number, parcela in enumerate(ordered, start=1):
                        parcela.numero = final_number
                        parcela.save(update_fields=["numero", "updated_at"])
                        report.parcelas_renumbered += 1
                    changed = True

                relinked = _relink_refinanciamentos_for_contract(contrato)
                report.refinanciamentos_relinked += relinked
                relink_contract_documents({contrato.id})
                report.documents_relinked += 1

        else:
            for parcela in active_parcelas:
                desired_bucket, desired_status = _desired_bucket_and_status(
                    parcela=parcela,
                    latest_cycle_number=latest_cycle_number,
                    current_month=current_month,
                )
                if parcela.layout_bucket != desired_bucket or str(parcela.status) != desired_status:
                    changed = True
                    break

        if changed:
            report.changed_contracts += 1
            affected_contract_ids.add(contrato.id)

    return report.as_dict()
