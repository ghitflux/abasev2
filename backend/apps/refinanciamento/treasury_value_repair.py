from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.contratos.models import Contrato, Parcela

from .models import Refinanciamento


TARGET_STATUSES = {
    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
    Refinanciamento.Status.EFETIVADO,
}


@dataclass
class TreasuryRefinanciamentoValueRepairReport:
    candidate_rows: int = 0
    updated_rows: int = 0
    linked_contract_rows: int = 0
    updated_contract_code_rows: int = 0
    updated_valor_rows: int = 0
    updated_repasse_rows: int = 0

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _parse_cycle_key(value: str) -> list[date]:
    refs: list[date] = []
    for chunk in (value or "").split("|"):
        if not chunk or "-" not in chunk:
            continue
        year, month = chunk.split("-", 1)
        refs.append(date(int(year), int(month), 1))
    return refs


def _contract_status_priority(contrato: Contrato) -> int:
    if contrato.status == Contrato.Status.ATIVO:
        return 0
    if contrato.status == Contrato.Status.ENCERRADO:
        return 1
    if contrato.status == Contrato.Status.EM_ANALISE:
        return 2
    if contrato.status == Contrato.Status.RASCUNHO:
        return 3
    return 4


def _resolve_contrato_by_associado(refinanciamento: Refinanciamento) -> Contrato | None:
    if refinanciamento.associado_id is None:
        return None
    candidates = list(
        Contrato.objects.filter(
            associado_id=refinanciamento.associado_id,
            deleted_at__isnull=True,
        )
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("id")
    )
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    desired_refs = set(_parse_cycle_key(refinanciamento.cycle_key))
    scored: list[tuple[int, int, date, int, Contrato]] = []
    for contrato in candidates:
        contract_refs = set(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .values_list("referencia_mes", flat=True)
        )
        matched_refs = len(contract_refs & desired_refs) if desired_refs else 0
        scored.append(
            (
                matched_refs,
                -_contract_status_priority(contrato),
                contrato.data_contrato or date.min,
                contrato.id,
                contrato,
            )
        )
    scored.sort(reverse=True)
    best = scored[0]
    if len(scored) == 1:
        return best[-1]
    if best[0] > 0 and best[:4] != scored[1][:4]:
        return best[-1]
    return None


def _resolve_contrato(refinanciamento: Refinanciamento) -> Contrato | None:
    if refinanciamento.contrato_origem is not None:
        return refinanciamento.contrato_origem
    contrato_codigo = str(refinanciamento.contrato_codigo_origem or "").strip()
    if not contrato_codigo:
        return _resolve_contrato_by_associado(refinanciamento)
    contrato = (
        Contrato.objects.filter(
            codigo=contrato_codigo,
            deleted_at__isnull=True,
        )
        .order_by("id")
        .first()
    )
    return contrato or _resolve_contrato_by_associado(refinanciamento)


def repair_treasury_refinanciamento_values(*, apply: bool) -> dict[str, object]:
    report = TreasuryRefinanciamentoValueRepairReport()
    queryset = (
        Refinanciamento.objects.select_related("contrato_origem")
        .filter(
            deleted_at__isnull=True,
            status__in=sorted(TARGET_STATUSES),
        )
        .order_by("id")
    )
    zero = Decimal("0.00")
    for refinanciamento in queryset.iterator():
        contrato = _resolve_contrato(refinanciamento)
        if contrato is None:
            continue
        target_valor = (
            contrato.margem_disponivel
            or refinanciamento.valor_refinanciamento
            or contrato.valor_liquido
            or contrato.valor_total_antecipacao
            or contrato.valor_mensalidade
            or zero
        )
        target_repasse = (
            refinanciamento.repasse_agente
            if refinanciamento.repasse_agente and refinanciamento.repasse_agente > 0
            else contrato.comissao_agente or zero
        )
        needs_contract = refinanciamento.contrato_origem_id is None
        needs_contract_code = (
            not str(refinanciamento.contrato_codigo_origem or "").strip()
            and bool(contrato.codigo)
        )
        needs_valor = (
            (refinanciamento.valor_refinanciamento or zero) <= 0
            and target_valor > 0
        )
        needs_repasse = (
            (refinanciamento.repasse_agente or zero) <= 0
            and target_repasse > 0
        )
        if not (needs_contract or needs_contract_code or needs_valor or needs_repasse):
            continue
        report.candidate_rows += 1
        if not apply:
            continue
        changed_fields: list[str] = []
        if needs_contract:
            refinanciamento.contrato_origem = contrato
            changed_fields.append("contrato_origem")
            report.linked_contract_rows += 1
        if needs_contract_code:
            refinanciamento.contrato_codigo_origem = contrato.codigo
            changed_fields.append("contrato_codigo_origem")
            report.updated_contract_code_rows += 1
        if needs_valor:
            refinanciamento.valor_refinanciamento = target_valor
            changed_fields.append("valor_refinanciamento")
            report.updated_valor_rows += 1
        if needs_repasse:
            refinanciamento.repasse_agente = target_repasse
            changed_fields.append("repasse_agente")
            report.updated_repasse_rows += 1
        if changed_fields:
            refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
            report.updated_rows += 1
    return report.as_dict()
