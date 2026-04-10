from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.associados.models import Associado
from apps.importacao.models import ArquivoRetornoItem
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import BaixaManual, Confirmacao, Pagamento

from .cycle_projection import build_contract_cycle_projection
from .cycle_rebuild import (
    rebuild_contract_cycle_state,
    rebind_financial_links_by_reference,
    relink_contract_documents,
)
from .models import Ciclo, Contrato, Parcela
from .soft_delete import soft_delete_contract_tree


@dataclass(frozen=True)
class DuplicateBillingGroup:
    associado: Associado
    primary_contract: Contrato
    duplicate_contracts: list[Contrato]
    duplicate_month_rows: list[dict[str, object]]
    cross_contract_months: list[str]
    intra_contract_months: list[str]
    projected_overlap_months: list[str]
    auto_repairable: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "associado_id": self.associado.id,
            "cpf_cnpj": self.associado.cpf_cnpj,
            "nome_associado": self.associado.nome_completo,
            "primary_contract_id": self.primary_contract.id,
            "primary_contract_code": self.primary_contract.codigo,
            "duplicate_contract_ids": [item.id for item in self.duplicate_contracts],
            "duplicate_contract_codes": [item.codigo for item in self.duplicate_contracts],
            "duplicate_month_rows": self.duplicate_month_rows,
            "cross_contract_months": self.cross_contract_months,
            "intra_contract_months": self.intra_contract_months,
            "projected_overlap_months": self.projected_overlap_months,
            "auto_repairable": self.auto_repairable,
        }


@dataclass
class DuplicateBillingRepairSummary:
    associado_id: int
    cpf_cnpj: str
    nome_associado: str
    primary_contract_id: int
    primary_contract_code: str
    duplicate_contract_ids: list[int]
    duplicate_contract_codes: list[str]
    contracts_soft_deleted: int = 0
    cycles_soft_deleted: int = 0
    parcelas_soft_deleted: int = 0
    itens_retorno_reassociados: int = 0
    itens_retorno_orfaos: int = 0
    baixas_reassociadas: int = 0
    confirmacoes_reassigned: int = 0
    pagamentos_reassigned: int = 0
    refinanciamentos_reassigned: int = 0
    refinanciamentos_soft_deleted: int = 0
    comprovantes_reassigned: int = 0
    rebuilt_primary_contract: bool = False

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _active_contracts_queryset(*, cpf_cnpj: str | None = None):
    queryset = (
        Contrato.objects.select_related("associado", "agente")
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("associado__nome_completo", "id")
    )
    if cpf_cnpj:
        queryset = queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    return queryset


def _contract_seed_date(contrato: Contrato) -> date:
    return (
        contrato.auxilio_liberado_em
        or contrato.mes_averbacao
        or contrato.data_aprovacao
        or contrato.data_contrato
        or contrato.created_at.date()
    )


def _contract_is_effective(contrato: Contrato) -> bool:
    return bool(
        contrato.status in {Contrato.Status.ATIVO, Contrato.Status.ENCERRADO}
        or contrato.auxilio_liberado_em is not None
        or contrato.mes_averbacao is not None
    )


def _primary_contract_key(contrato: Contrato) -> tuple[object, ...]:
    return (
        0 if _contract_is_effective(contrato) else 1,
        _contract_seed_date(contrato),
        contrato.created_at,
        contrato.id,
    )


def _current_contract_references(contrato: Contrato) -> set[date]:
    return set(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .values_list("referencia_mes", flat=True)
    )


def _projected_contract_references(contrato: Contrato) -> set[date]:
    projection = build_contract_cycle_projection(contrato)
    return {
        parcela["referencia_mes"]
        for cycle in projection.get("cycles", [])
        for parcela in cycle.get("parcelas", [])
    }


def _duplicate_month_rows_for_associado(associado_id: int) -> list[dict[str, object]]:
    duplicate_keys = {
        (row["associado_id"], row["referencia_mes"])
        for row in (
            Parcela.all_objects.filter(
                associado_id=associado_id,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .values("associado_id", "referencia_mes")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
    }
    if not duplicate_keys:
        return []

    parcelas = list(
        Parcela.all_objects.select_related("ciclo", "ciclo__contrato")
        .filter(
            associado_id=associado_id,
            deleted_at__isnull=True,
            referencia_mes__in=[item[1] for item in duplicate_keys],
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "ciclo__contrato_id", "ciclo__numero", "numero", "id")
    )

    grouped: dict[date, list[Parcela]] = defaultdict(list)
    for parcela in parcelas:
        grouped[parcela.referencia_mes].append(parcela)

    rows: list[dict[str, object]] = []
    for referencia_mes, items in sorted(grouped.items()):
        contract_ids = sorted({item.ciclo.contrato_id for item in items})
        rows.append(
            {
                "referencia_mes": referencia_mes.isoformat(),
                "total": len(items),
                "cross_contract": len(contract_ids) > 1,
                "contract_ids": contract_ids,
                "contracts": [
                    {
                        "contrato_id": item.ciclo.contrato_id,
                        "contrato_codigo": item.ciclo.contrato.codigo,
                        "ciclo_id": item.ciclo_id,
                        "ciclo_numero": item.ciclo.numero,
                        "parcela_id": item.id,
                        "status": item.status,
                    }
                    for item in items
                ],
            }
        )
    return rows


def _build_duplicate_groups(*, cpf_cnpj: str | None = None) -> list[DuplicateBillingGroup]:
    contratos = list(_active_contracts_queryset(cpf_cnpj=cpf_cnpj))
    if not contratos:
        return []

    by_associado: dict[int, list[Contrato]] = defaultdict(list)
    for contrato in contratos:
        by_associado[contrato.associado_id].append(contrato)

    groups: list[DuplicateBillingGroup] = []
    for associado_id, associados_contratos in by_associado.items():
        associado = associados_contratos[0].associado
        sorted_contracts = sorted(associados_contratos, key=_primary_contract_key)
        primary = sorted_contracts[0]
        duplicate_rows = _duplicate_month_rows_for_associado(associado_id)
        cross_contract_months = [
            row["referencia_mes"] for row in duplicate_rows if row["cross_contract"]
        ]
        intra_contract_months = [
            row["referencia_mes"] for row in duplicate_rows if not row["cross_contract"]
        ]

        projected_primary_refs = _projected_contract_references(primary) | _current_contract_references(primary)
        duplicate_contracts: list[Contrato] = []
        projected_overlap_months: set[str] = set()
        for contrato in sorted_contracts[1:]:
            projected_refs = _projected_contract_references(contrato) | _current_contract_references(contrato)
            overlap = sorted(
                referencia.isoformat()
                for referencia in projected_primary_refs.intersection(projected_refs)
            )
            if overlap:
                duplicate_contracts.append(contrato)
                projected_overlap_months.update(overlap)

        if not duplicate_contracts and not duplicate_rows:
            continue

        groups.append(
            DuplicateBillingGroup(
                associado=associado,
                primary_contract=primary,
                duplicate_contracts=duplicate_contracts,
                duplicate_month_rows=duplicate_rows,
                cross_contract_months=cross_contract_months,
                intra_contract_months=intra_contract_months,
                projected_overlap_months=sorted(projected_overlap_months),
                auto_repairable=bool(duplicate_contracts or intra_contract_months),
            )
        )

    groups.sort(key=lambda item: (item.associado.nome_completo, item.associado.id))
    return groups


def audit_duplicate_billing_months(*, cpf_cnpj: str | None = None) -> dict[str, object]:
    groups = _build_duplicate_groups(cpf_cnpj=cpf_cnpj)
    duplicate_keys_queryset = Parcela.all_objects.filter(deleted_at__isnull=True).exclude(
        status=Parcela.Status.CANCELADO
    )
    if cpf_cnpj:
        duplicate_keys_queryset = duplicate_keys_queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    duplicate_keys_total = (
        duplicate_keys_queryset.values("associado_id", "referencia_mes")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    multi_contract_queryset = Contrato.objects.exclude(status=Contrato.Status.CANCELADO)
    if cpf_cnpj:
        multi_contract_queryset = multi_contract_queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    multi_contract_associados = (
        multi_contract_queryset.values("associado_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )

    return {
        "summary": {
            "groups": len(groups),
            "duplicate_keys": duplicate_keys_total.count(),
            "multi_contract_associados": multi_contract_associados.count(),
            "cross_contract_duplicate_groups": sum(
                1 for group in groups if group.cross_contract_months or group.duplicate_contracts
            ),
            "intra_contract_duplicate_groups": sum(
                1 for group in groups if group.intra_contract_months
            ),
        },
        "groups": [group.as_dict() for group in groups],
    }


def _synthetic_duplicate_refi(refinanciamento: Refinanciamento) -> bool:
    has_docs = Comprovante.all_objects.filter(
        refinanciamento=refinanciamento,
        deleted_at__isnull=True,
    ).exists()
    return bool(
        refinanciamento.legacy_refinanciamento_id is None
        and refinanciamento.origem == Refinanciamento.Origem.OPERACIONAL
        and refinanciamento.ciclo_destino_id is None
        and not refinanciamento.termo_antecipacao_path
        and not has_docs
    )


def _append_merge_note(base: str, note: str) -> str:
    if not base:
        return note
    if note in base:
        return base
    return f"{base}\n{note}"


def _primary_parcela_by_reference(contrato: Contrato) -> dict[date, Parcela]:
    return {
        parcela.referencia_mes: parcela
        for parcela in Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        ).exclude(status=Parcela.Status.CANCELADO)
    }


def _resolve_intra_contract_duplicate_rows(
    group: DuplicateBillingGroup,
    summary: DuplicateBillingRepairSummary,
) -> None:
    if not group.intra_contract_months:
        return

    duplicate_note_prefix = (
        f"Competência consolidada pela normalização de duplicidade em "
        f"{timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}."
    )

    for month in group.intra_contract_months:
        referencia = date.fromisoformat(month)
        parcelas = list(
            Parcela.all_objects.filter(
                associado=group.associado,
                ciclo__contrato=group.primary_contract,
                referencia_mes=referencia,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("created_at", "id")
        )
        if len(parcelas) <= 1:
            continue

        canonical = parcelas[0]
        canonical_changed_fields: list[str] = []
        canonical_note = _append_merge_note(
            canonical.observacao,
            duplicate_note_prefix,
        )
        if canonical_note != (canonical.observacao or ""):
            canonical.observacao = canonical_note
            canonical_changed_fields.append("observacao")

        for duplicate in parcelas[1:]:
            summary.itens_retorno_reassociados += ArquivoRetornoItem.objects.filter(
                parcela=duplicate
            ).update(parcela=canonical)

            duplicate_baixa = BaixaManual.objects.filter(parcela=duplicate).first()
            canonical_baixa = BaixaManual.objects.filter(parcela=canonical).first()
            if duplicate_baixa and canonical_baixa is None:
                duplicate_baixa.parcela = canonical
                duplicate_baixa.observacao = _append_merge_note(
                    duplicate_baixa.observacao,
                    f"Baixa migrada da parcela duplicada #{duplicate.id}.",
                )
                duplicate_baixa.save(update_fields=["parcela", "observacao", "updated_at"])
                summary.baixas_reassociadas += 1
                canonical_baixa = duplicate_baixa

            if (
                duplicate.status in {Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}
                and canonical.status not in {Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}
            ):
                canonical.status = duplicate.status
                canonical_changed_fields.append("status")
            if canonical.data_pagamento is None and duplicate.data_pagamento is not None:
                canonical.data_pagamento = duplicate.data_pagamento
                canonical_changed_fields.append("data_pagamento")

            duplicate.soft_delete()
            summary.parcelas_soft_deleted += 1

        if canonical_changed_fields:
            canonical.save(
                update_fields=[*sorted(set(canonical_changed_fields)), "updated_at"]
            )


@transaction.atomic
def _repair_group(
    group: DuplicateBillingGroup,
    *,
    execute: bool,
) -> DuplicateBillingRepairSummary:
    summary = DuplicateBillingRepairSummary(
        associado_id=group.associado.id,
        cpf_cnpj=group.associado.cpf_cnpj,
        nome_associado=group.associado.nome_completo,
        primary_contract_id=group.primary_contract.id,
        primary_contract_code=group.primary_contract.codigo,
        duplicate_contract_ids=[item.id for item in group.duplicate_contracts],
        duplicate_contract_codes=[item.codigo for item in group.duplicate_contracts],
    )
    if not execute:
        return summary

    duplicate_reference_map: dict[int, date] = {}
    refinanciamento_transfers: list[dict[str, int | None]] = []

    if not group.duplicate_contracts:
        _resolve_intra_contract_duplicate_rows(group, summary)

    for duplicate in group.duplicate_contracts:
        duplicate_note = (
            f"Contrato mesclado ao contrato canônico {group.primary_contract.codigo} "
            f"em {timezone.localtime().strftime('%Y-%m-%d %H:%M:%S')}."
        )
        for parcela in Parcela.all_objects.filter(
            ciclo__contrato=duplicate,
            deleted_at__isnull=True,
        ).exclude(status=Parcela.Status.CANCELADO):
            duplicate_reference_map[parcela.id] = parcela.referencia_mes

        summary.confirmacoes_reassigned += Confirmacao.all_objects.filter(
            contrato=duplicate,
            deleted_at__isnull=True,
        ).update(
            contrato=group.primary_contract,
            updated_at=timezone.now(),
        )

        for pagamento in Pagamento.all_objects.filter(
            cadastro=group.associado,
            contrato_codigo=duplicate.codigo,
            deleted_at__isnull=True,
        ).exclude(status=Pagamento.Status.CANCELADO):
            pagamento.contrato_codigo = group.primary_contract.codigo
            pagamento.notes = _append_merge_note(pagamento.notes, duplicate_note)
            pagamento.save(update_fields=["contrato_codigo", "notes", "updated_at"])
            summary.pagamentos_reassigned += 1

        for refinanciamento in Refinanciamento.all_objects.filter(
            contrato_origem=duplicate,
            deleted_at__isnull=True,
        ).select_related("ciclo_origem", "ciclo_destino"):
            if _synthetic_duplicate_refi(refinanciamento):
                refinanciamento.soft_delete()
                summary.refinanciamentos_soft_deleted += 1
                continue

            refinanciamento_transfers.append(
                {
                    "id": refinanciamento.id,
                    "ciclo_origem_numero": (
                        refinanciamento.ciclo_origem.numero if refinanciamento.ciclo_origem_id else None
                    ),
                    "ciclo_destino_numero": (
                        refinanciamento.ciclo_destino.numero if refinanciamento.ciclo_destino_id else None
                    ),
                }
            )
            refinanciamento.contrato_origem = group.primary_contract
            refinanciamento.contrato_codigo_origem = group.primary_contract.codigo
            refinanciamento.ciclo_origem = None
            refinanciamento.ciclo_destino = None
            refinanciamento.observacao = _append_merge_note(
                refinanciamento.observacao,
                duplicate_note,
            )
            refinanciamento.save(
                update_fields=[
                    "contrato_origem",
                    "contrato_codigo_origem",
                    "ciclo_origem",
                    "ciclo_destino",
                    "observacao",
                    "updated_at",
                ]
            )
            summary.refinanciamentos_reassigned += 1

        delete_summary = soft_delete_contract_tree(duplicate)
        summary.contracts_soft_deleted += delete_summary["contracts_soft_deleted"]
        summary.cycles_soft_deleted += delete_summary["cycles_soft_deleted"]
        summary.parcelas_soft_deleted += delete_summary["parcelas_soft_deleted"]

    if group.duplicate_contracts:
        rebuild_report = rebuild_contract_cycle_state(
            group.primary_contract,
            execute=True,
            extra_reference_by_parcela_id=duplicate_reference_map,
        )
        summary.rebuilt_primary_contract = True
        summary.itens_retorno_reassociados += rebuild_report.itens_retorno_reassociados
        summary.itens_retorno_orfaos += rebuild_report.itens_retorno_orfaos
        summary.baixas_reassociadas += rebuild_report.baixas_reassociadas
        summary.refinanciamentos_soft_deleted += rebuild_report.refinanciamentos_soft_deleted
        summary.refinanciamentos_reassigned += rebuild_report.refinanciamentos_ajustados
        summary.cycles_soft_deleted += rebuild_report.ciclos_invalidos_soft_deleted
        summary.parcelas_soft_deleted += rebuild_report.parcelas_invalidas_soft_deleted

    primary_cycles = {
        ciclo.numero: ciclo
        for ciclo in Ciclo.all_objects.filter(
            contrato=group.primary_contract,
            deleted_at__isnull=True,
        )
    }
    primary_parcelas_by_reference = _primary_parcela_by_reference(group.primary_contract)
    external_rebind = rebind_financial_links_by_reference(
        duplicate_reference_map,
        primary_parcelas_by_reference,
    )
    summary.itens_retorno_reassociados += external_rebind["itens_retorno_reassociados"]
    summary.itens_retorno_orfaos += external_rebind["itens_retorno_orfaos"]
    summary.baixas_reassociadas += external_rebind["baixas_reassociadas"]

    for transfer in refinanciamento_transfers:
        refinanciamento = Refinanciamento.all_objects.get(pk=transfer["id"])
        changed_fields: list[str] = []
        ciclo_origem = primary_cycles.get(transfer["ciclo_origem_numero"] or 0)
        ciclo_destino = primary_cycles.get(transfer["ciclo_destino_numero"] or 0)
        if refinanciamento.ciclo_origem_id != getattr(ciclo_origem, "id", None):
            refinanciamento.ciclo_origem = ciclo_origem
            changed_fields.append("ciclo_origem")
        if ciclo_destino is not None:
            conflicting_destino = (
                Refinanciamento.all_objects.filter(
                    ciclo_destino=ciclo_destino,
                    deleted_at__isnull=True,
                )
                .exclude(pk=refinanciamento.pk)
                .exists()
            )
            if conflicting_destino:
                refinanciamento.soft_delete()
                summary.refinanciamentos_soft_deleted += 1
                continue
        if refinanciamento.ciclo_destino_id != getattr(ciclo_destino, "id", None):
            refinanciamento.ciclo_destino = ciclo_destino
            changed_fields.append("ciclo_destino")
        if changed_fields:
            refinanciamento.save(update_fields=[*changed_fields, "updated_at"])

    for comprovante in Comprovante.all_objects.filter(
        Q(contrato_id__in=summary.duplicate_contract_ids)
        | Q(refinanciamento_id__in=[item["id"] for item in refinanciamento_transfers]),
        deleted_at__isnull=True,
    ).select_related("ciclo"):
        changed_fields = []
        if comprovante.contrato_id != group.primary_contract.id:
            comprovante.contrato = group.primary_contract
            changed_fields.append("contrato")
        if comprovante.ciclo_id:
            target_cycle = primary_cycles.get(comprovante.ciclo.numero)
            if target_cycle and comprovante.ciclo_id != target_cycle.id:
                comprovante.ciclo = target_cycle
                changed_fields.append("ciclo")
        if changed_fields:
            comprovante.save(update_fields=[*changed_fields, "updated_at"])
            summary.comprovantes_reassigned += 1

    relink_contract_documents({group.primary_contract.id})
    return summary


def repair_duplicate_billing_months(
    *,
    cpf_cnpj: str | None = None,
    execute: bool = False,
) -> dict[str, object]:
    groups = _build_duplicate_groups(cpf_cnpj=cpf_cnpj)
    reports = [
        _repair_group(group, execute=execute)
        for group in groups
        if group.auto_repairable
    ]

    target_contracts = list(_active_contracts_queryset(cpf_cnpj=cpf_cnpj))
    handled_contract_ids = {report.primary_contract_id for report in reports}
    rebuild_reports = []
    if execute:
        for contrato in target_contracts:
            if contrato.id in handled_contract_ids:
                continue
            rebuild_reports.append(rebuild_contract_cycle_state(contrato, execute=True).as_dict())

    post_audit = audit_duplicate_billing_months(cpf_cnpj=cpf_cnpj)
    return {
        "summary": {
            "mode": "execute" if execute else "dry-run",
            "groups": len(groups),
            "auto_repairable_groups": sum(1 for group in groups if group.auto_repairable),
            "reports": len(reports),
            "merged_contracts": sum(len(report.duplicate_contract_ids) for report in reports),
            "contracts_soft_deleted": sum(report.contracts_soft_deleted for report in reports),
            "cycles_soft_deleted": sum(report.cycles_soft_deleted for report in reports),
            "parcelas_soft_deleted": sum(report.parcelas_soft_deleted for report in reports),
            "itens_retorno_reassociados": sum(
                report.itens_retorno_reassociados for report in reports
            ),
            "itens_retorno_orfaos": sum(report.itens_retorno_orfaos for report in reports),
            "baixas_reassociadas": sum(report.baixas_reassociadas for report in reports),
            "confirmacoes_reassigned": sum(report.confirmacoes_reassigned for report in reports),
            "pagamentos_reassigned": sum(report.pagamentos_reassigned for report in reports),
            "refinanciamentos_reassigned": sum(
                report.refinanciamentos_reassigned for report in reports
            ),
            "refinanciamentos_soft_deleted": sum(
                report.refinanciamentos_soft_deleted for report in reports
            ),
            "comprovantes_reassigned": sum(report.comprovantes_reassigned for report in reports),
            "rebuilt_contracts": len(rebuild_reports) + sum(
                1 for report in reports if report.rebuilt_primary_contract
            ),
            "remaining_duplicate_keys": post_audit["summary"]["duplicate_keys"],
            "remaining_multi_contract_associados": post_audit["summary"][
                "multi_contract_associados"
            ],
        },
        "groups": [group.as_dict() for group in groups],
        "repairs": [report.as_dict() for report in reports],
        "post_audit": post_audit,
    }
