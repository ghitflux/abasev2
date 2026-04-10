from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.associados.models import Associado, only_digits
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.manual_cycle_layout_repair import repair_manual_cycle_layouts
from apps.contratos.models import Contrato, Parcela
from apps.contratos.special_references import NOVEMBER_2025_REFERENCE

from .financeiro import build_financeiro_resumo
from .models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade

VALID_PAID_STATUS = "quitada"
INVALID_UNPAID_OBSERVATION = (
    "Competência 11/2025 não descontada e mantida fora do ciclo."
)
VALID_PAID_OBSERVATION = (
    "Competência 11/2025 quitada manualmente e mantida fora do ciclo."
)


@dataclass
class NovemberOutsideCycleRepairReport:
    pagamentos_validos_mantidos: int = 0
    pagamentos_invalidos_limpos: int = 0
    parcelas_atualizadas: int = 0
    contratos_rebuildados: int = 0
    contratos_manuais_reparados: int = 0
    arquivos_financeiro_atualizados: int = 0
    associados_afetados: int = 0
    financeiro_ok_total: int = 0
    financeiro_recebido_total: str = "0.00"

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _valid_manual_payment(pagamento: PagamentoMensalidade) -> bool:
    return (
        pagamento.referencia_month == NOVEMBER_2025_REFERENCE
        and pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
        and pagamento.manual_by_id is None
    )


def _clear_invalid_manual_payment(pagamento: PagamentoMensalidade) -> bool:
    if (
        pagamento.referencia_month != NOVEMBER_2025_REFERENCE
        or pagamento.manual_status != PagamentoMensalidade.ManualStatus.PAGO
        or pagamento.manual_by_id is None
    ):
        return False

    changed_fields: list[str] = []
    if pagamento.manual_status is not None:
        pagamento.manual_status = None
        changed_fields.append("manual_status")
    if pagamento.manual_paid_at is not None:
        pagamento.manual_paid_at = None
        changed_fields.append("manual_paid_at")
    if pagamento.manual_forma_pagamento:
        pagamento.manual_forma_pagamento = ""
        changed_fields.append("manual_forma_pagamento")
    if pagamento.manual_comprovante_path:
        pagamento.manual_comprovante_path = ""
        changed_fields.append("manual_comprovante_path")
    if pagamento.recebido_manual is not None:
        pagamento.recebido_manual = None
        changed_fields.append("recebido_manual")
    if pagamento.esperado_manual is not None:
        pagamento.esperado_manual = None
        changed_fields.append("esperado_manual")
    if pagamento.manual_by_id is not None:
        pagamento.manual_by = None
        changed_fields.append("manual_by")

    if not changed_fields:
        return False
    pagamento.save(update_fields=[*changed_fields, "updated_at"])
    return True


def _valid_payment_key(
    pagamento: PagamentoMensalidade,
    *,
    cpf_to_associado_id: dict[str, int],
) -> tuple[int | None, str]:
    normalized_cpf = only_digits(pagamento.cpf_cnpj)
    associado_id = pagamento.associado_id or cpf_to_associado_id.get(normalized_cpf)
    return associado_id, normalized_cpf


def _resolve_valid_paid_maps(
    *,
    pagamentos: list[PagamentoMensalidade],
    cpf_to_associado_id: dict[str, int],
) -> tuple[dict[int, date], dict[str, date], Counter[str]]:
    by_associado: dict[int, date] = {}
    by_cpf: dict[str, date] = {}
    stats = Counter()
    for pagamento in pagamentos:
        if not _valid_manual_payment(pagamento):
            continue
        associado_id, normalized_cpf = _valid_payment_key(
            pagamento,
            cpf_to_associado_id=cpf_to_associado_id,
        )
        paid_at = (
            pagamento.manual_paid_at.date()
            if pagamento.manual_paid_at is not None
            else NOVEMBER_2025_REFERENCE
        )
        if associado_id is not None:
            current = by_associado.get(associado_id)
            if current is None or paid_at > current:
                by_associado[associado_id] = paid_at
        if normalized_cpf:
            current_cpf = by_cpf.get(normalized_cpf)
            if current_cpf is None or paid_at > current_cpf:
                by_cpf[normalized_cpf] = paid_at
        stats["pagamentos_validos_mantidos"] += 1
    return by_associado, by_cpf, stats


def _update_november_parcela(
    parcela: Parcela,
    *,
    valid_paid_dates_by_associado: dict[int, date],
    valid_paid_dates_by_cpf: dict[str, date],
) -> bool:
    normalized_cpf = only_digits(parcela.associado.cpf_cnpj)
    paid_date = valid_paid_dates_by_associado.get(parcela.associado_id) or valid_paid_dates_by_cpf.get(
        normalized_cpf
    )
    target_status = VALID_PAID_STATUS if paid_date else Parcela.Status.NAO_DESCONTADO
    target_payment_date = paid_date if paid_date else None
    target_observacao = VALID_PAID_OBSERVATION if paid_date else INVALID_UNPAID_OBSERVATION

    changed_fields: list[str] = []
    if parcela.layout_bucket != Parcela.LayoutBucket.UNPAID:
        parcela.layout_bucket = Parcela.LayoutBucket.UNPAID
        changed_fields.append("layout_bucket")
    if str(parcela.status) != target_status:
        parcela.status = target_status
        changed_fields.append("status")
    if parcela.data_pagamento != target_payment_date:
        parcela.data_pagamento = target_payment_date
        changed_fields.append("data_pagamento")
    if parcela.observacao != target_observacao:
        parcela.observacao = target_observacao
        changed_fields.append("observacao")

    if not changed_fields:
        return False
    parcela.save(update_fields=[*changed_fields, "updated_at"])
    return True


def _refresh_cached_financeiro_summary() -> int:
    financeiro = build_financeiro_resumo(competencia=NOVEMBER_2025_REFERENCE)
    updated = 0
    for arquivo in ArquivoRetorno.objects.filter(
        competencia=NOVEMBER_2025_REFERENCE,
        status=ArquivoRetorno.Status.CONCLUIDO,
    ).order_by("id"):
        payload = dict(arquivo.resultado_resumo or {})
        if payload.get("financeiro") == financeiro:
            continue
        payload["financeiro"] = financeiro
        arquivo.resultado_resumo = payload
        arquivo.save(update_fields=["resultado_resumo", "updated_at"])
        updated += 1
    return updated


def repair_november_2025_outside_cycles(*, apply: bool) -> dict[str, object]:
    report = NovemberOutsideCycleRepairReport()

    cpf_to_associado_id = {
        only_digits(cpf): associado_id
        for associado_id, cpf in Associado.objects.filter(deleted_at__isnull=True).values_list(
            "id",
            "cpf_cnpj",
        )
    }
    pagamentos = list(
        PagamentoMensalidade.objects.filter(referencia_month=NOVEMBER_2025_REFERENCE)
        .select_related("associado")
        .order_by("id")
    )
    valid_paid_dates_by_associado, valid_paid_dates_by_cpf, valid_stats = _resolve_valid_paid_maps(
        pagamentos=pagamentos,
        cpf_to_associado_id=cpf_to_associado_id,
    )
    report.pagamentos_validos_mantidos = valid_stats["pagamentos_validos_mantidos"]

    affected_associado_ids: set[int] = set(valid_paid_dates_by_associado.keys())
    for normalized_cpf in valid_paid_dates_by_cpf:
        associado_id = cpf_to_associado_id.get(normalized_cpf)
        if associado_id is not None:
            affected_associado_ids.add(associado_id)

    parcelas_novembro = list(
        Parcela.all_objects.select_related("associado", "ciclo__contrato")
        .filter(
            referencia_mes=NOVEMBER_2025_REFERENCE,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("ciclo__contrato_id", "numero", "id")
    )
    for parcela in parcelas_novembro:
        affected_associado_ids.add(parcela.associado_id)

    for pagamento in pagamentos:
        normalized_cpf = only_digits(pagamento.cpf_cnpj)
        associado_id = pagamento.associado_id or cpf_to_associado_id.get(normalized_cpf)
        if associado_id is not None:
            affected_associado_ids.add(associado_id)

    for associado_id in ArquivoRetornoItem.objects.filter(
        arquivo_retorno__competencia=NOVEMBER_2025_REFERENCE,
        associado_id__isnull=False,
    ).values_list("associado_id", flat=True):
        affected_associado_ids.add(int(associado_id))
    for cpf in ArquivoRetornoItem.objects.filter(
        arquivo_retorno__competencia=NOVEMBER_2025_REFERENCE,
        associado_id__isnull=True,
    ).values_list("cpf_cnpj", flat=True):
        associado_id = cpf_to_associado_id.get(only_digits(cpf))
        if associado_id is not None:
            affected_associado_ids.add(associado_id)

    affected_contracts = list(
        Contrato.objects.select_related("associado")
        .filter(
            associado_id__in=sorted(affected_associado_ids),
            deleted_at__isnull=True,
        )
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("id")
    )
    report.associados_afetados = len(affected_associado_ids)

    if not apply:
        report.contratos_rebuildados = len(affected_contracts)
        report.contratos_manuais_reparados = sum(
            1 for contrato in affected_contracts if contrato.admin_manual_layout_enabled
        )
        financeiro = build_financeiro_resumo(competencia=NOVEMBER_2025_REFERENCE)
        report.financeiro_ok_total = int(financeiro.get("ok") or 0)
        report.financeiro_recebido_total = str(financeiro.get("recebido") or "0.00")
        return report.as_dict()

    with transaction.atomic():
        for pagamento in pagamentos:
            if _clear_invalid_manual_payment(pagamento):
                report.pagamentos_invalidos_limpos += 1

        for parcela in parcelas_novembro:
            if _update_november_parcela(
                parcela,
                valid_paid_dates_by_associado=valid_paid_dates_by_associado,
                valid_paid_dates_by_cpf=valid_paid_dates_by_cpf,
            ):
                report.parcelas_atualizadas += 1

        for contrato in affected_contracts:
            if contrato.admin_manual_layout_enabled:
                repair_report = repair_manual_cycle_layouts(
                    apply=True,
                    contrato_id=contrato.id,
                )
                if int(repair_report.get("changed_contracts") or 0) > 0:
                    report.contratos_manuais_reparados += 1
            rebuild_contract_cycle_state(contrato, execute=True)
            report.contratos_rebuildados += 1

        report.arquivos_financeiro_atualizados = _refresh_cached_financeiro_summary()

    financeiro = build_financeiro_resumo(competencia=NOVEMBER_2025_REFERENCE)
    report.financeiro_ok_total = int(financeiro.get("ok") or 0)
    report.financeiro_recebido_total = str(financeiro.get("recebido") or "0.00")
    return report.as_dict()
