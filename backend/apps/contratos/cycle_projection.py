from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.associados.models import Associado
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import BaixaManual, Pagamento

from .cycle_timeline import get_contract_activation_payload, get_contract_cycle_size
from .models import Ciclo, Contrato, Parcela

PAID_STATUS_CODES = {"1", "4"}
ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES = {
    Refinanciamento.Status.APTO_A_RENOVAR,
    Refinanciamento.Status.EM_ANALISE_RENOVACAO,
    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
    Refinanciamento.Status.PENDENTE_APTO,
    Refinanciamento.Status.SOLICITADO,
    Refinanciamento.Status.EM_ANALISE,
    Refinanciamento.Status.APROVADO,
    Refinanciamento.Status.BLOQUEADO,
    Refinanciamento.Status.DESATIVADO,
}
EFFECTIVE_REFINANCIAMENTO_STATUSES = {
    Refinanciamento.Status.EFETIVADO,
    Refinanciamento.Status.CONCLUIDO,
}
STATUS_VISUAL_PHASE_LABELS = {
    "em_analise": "Em Análise",
    "ciclo_aberto": "Ativo",
    "apto_a_renovar": "Apto para Renovação",
    "renovacao_em_analise": "Renovação em Análise",
    "aprovado_para_renovacao": "Aguardando Pagamento",
    "ciclo_renovado": "Renovado",
    "contrato_desativado": "Inativo",
    "contrato_encerrado": "Encerrado",
}
STATUS_VISUAL_FINANCIAL_LABELS = {
    "ciclo_em_dia": "Em Dia",
    "ciclo_com_pendencia": "Com Pendência",
    "ciclo_inadimplente": "Inadimplente",
    "ciclo_desativado": "Desativado",
}
STATUS_VISUAL_SINGLE_LABELS = {
    "em_analise",
    "contrato_desativado",
    "contrato_encerrado",
}
STATUS_VISUAL_FINANCIAL_PRIORITY = {
    "ciclo_inadimplente": 3,
    "ciclo_com_pendencia": 2,
    "ciclo_em_dia": 1,
    "ciclo_desativado": 0,
}
STATUS_VISUAL_PHASE_PRIORITY = {
    "aprovado_para_renovacao": 5,
    "renovacao_em_analise": 4,
    "apto_a_renovar": 3,
    "ciclo_aberto": 2,
    "ciclo_renovado": 1,
    "em_analise": 0,
    "contrato_desativado": -1,
    "contrato_encerrado": -2,
}
OPERATIONAL_STATUS_TO_VISUAL_PHASE = {
    Refinanciamento.Status.APTO_A_RENOVAR: "apto_a_renovar",
    Refinanciamento.Status.EM_ANALISE_RENOVACAO: "renovacao_em_analise",
    Refinanciamento.Status.APROVADO_PARA_RENOVACAO: "aprovado_para_renovacao",
    Refinanciamento.Status.DESATIVADO: "contrato_desativado",
    Refinanciamento.Status.BLOQUEADO: "renovacao_em_analise",
    Refinanciamento.Status.REJEITADO: "renovacao_em_analise",
}


@dataclass(frozen=True)
class FinancialReference:
    referencia_mes: date
    status: str
    data_pagamento: date | None
    valor: Decimal
    observacao: str = ""
    source: str = ""


@dataclass(frozen=True)
class EffectiveRenewal:
    refinanciamento: Refinanciamento
    activated_at: datetime
    first_reference: date


def _compose_visual_status(
    *,
    phase_slug: str,
    financial_slug: str | None = None,
) -> dict[str, str]:
    phase_label = STATUS_VISUAL_PHASE_LABELS[phase_slug]
    if phase_slug in STATUS_VISUAL_SINGLE_LABELS or financial_slug is None:
        return {
            "status_visual_slug": phase_slug,
            "status_visual_label": phase_label,
        }

    simplified_labels = {
        ("ciclo_aberto", "ciclo_em_dia"): "Ativo",
        ("ciclo_aberto", "ciclo_com_pendencia"): "Ativo com Pendência",
        ("ciclo_aberto", "ciclo_inadimplente"): "Inadimplente",
        ("apto_a_renovar", "ciclo_em_dia"): "Apto para Renovação",
        ("apto_a_renovar", "ciclo_com_pendencia"): "Apto para Renovação com Pendência",
        ("apto_a_renovar", "ciclo_inadimplente"): "Apto para Renovação com Inadimplência",
        ("renovacao_em_analise", "ciclo_em_dia"): "Renovação em Análise",
        ("renovacao_em_analise", "ciclo_com_pendencia"): "Renovação em Análise com Pendência",
        ("renovacao_em_analise", "ciclo_inadimplente"): "Renovação em Análise com Inadimplência",
        ("aprovado_para_renovacao", "ciclo_em_dia"): "Aguardando Pagamento",
        ("aprovado_para_renovacao", "ciclo_com_pendencia"): "Aguardando Pagamento com Pendência",
        ("aprovado_para_renovacao", "ciclo_inadimplente"): "Aguardando Pagamento com Inadimplência",
        ("ciclo_renovado", "ciclo_em_dia"): "Renovado",
        ("ciclo_renovado", "ciclo_com_pendencia"): "Renovado com Pendência",
        ("ciclo_renovado", "ciclo_inadimplente"): "Renovado com Inadimplência",
    }
    simplified = simplified_labels.get((phase_slug, financial_slug))
    if simplified is not None:
        return {
            "status_visual_slug": f"{phase_slug}__{financial_slug}",
            "status_visual_label": simplified,
        }

    financial_label = STATUS_VISUAL_FINANCIAL_LABELS[financial_slug]
    return {
        "status_visual_slug": f"{phase_slug}__{financial_slug}",
        "status_visual_label": f"{phase_label} + {financial_label}",
    }


def _cycle_financial_status(
    *,
    contrato: Contrato,
    parcelas: list[dict[str, object]],
) -> str:
    associado_status = getattr(contrato.associado, "status", "")
    paid_count = sum(
        1 for parcela in parcelas if parcela["status"] == Parcela.Status.DESCONTADO
    )
    if associado_status == Associado.Status.INATIVO or contrato.status == Contrato.Status.CANCELADO:
        return "ciclo_desativado"
    if any(parcela["status"] == Parcela.Status.NAO_DESCONTADO for parcela in parcelas):
        return "ciclo_com_pendencia"
    if associado_status == Associado.Status.INADIMPLENTE and paid_count == 0:
        return "ciclo_inadimplente"
    return "ciclo_em_dia"


def _cycle_phase_status(
    *,
    contrato: Contrato,
    cycle_status: str,
    next_renewal: EffectiveRenewal | None,
    refinanciamento_operacional: Refinanciamento | None,
) -> str:
    associado_status = getattr(contrato.associado, "status", "")
    if associado_status == Associado.Status.INATIVO or contrato.status == Contrato.Status.CANCELADO:
        return "contrato_desativado"
    if contrato.status == Contrato.Status.ENCERRADO:
        return "contrato_encerrado"
    if refinanciamento_operacional is not None:
        normalized = _normalize_operational_status(refinanciamento_operacional.status)
        if normalized in OPERATIONAL_STATUS_TO_VISUAL_PHASE:
            return OPERATIONAL_STATUS_TO_VISUAL_PHASE[normalized]
    if next_renewal is not None:
        return "ciclo_renovado"
    if cycle_status == Ciclo.Status.APTO_A_RENOVAR:
        return "apto_a_renovar"
    return "ciclo_aberto"


def _cycle_visual_rank(cycle: dict[str, object]) -> tuple[int, int, int]:
    financial_slug = str(cycle.get("situacao_financeira") or "")
    phase_slug = str(cycle.get("fase_ciclo") or "")
    return (
        STATUS_VISUAL_FINANCIAL_PRIORITY.get(financial_slug, -1),
        STATUS_VISUAL_PHASE_PRIORITY.get(phase_slug, -1),
        int(cycle.get("numero") or 0),
    )


def _fallback_visual_status_from_models(
    *,
    associado_status: str,
    contrato_status: str,
) -> dict[str, str]:
    if associado_status == Associado.Status.INATIVO or contrato_status == Contrato.Status.CANCELADO:
        return _compose_visual_status(phase_slug="contrato_desativado")
    if contrato_status == Contrato.Status.ENCERRADO:
        return _compose_visual_status(phase_slug="contrato_encerrado")
    if associado_status == Associado.Status.INADIMPLENTE:
        return _compose_visual_status(
            phase_slug="ciclo_aberto",
            financial_slug="ciclo_inadimplente",
        )
    return _compose_visual_status(phase_slug="em_analise")


def _month_start(value: date | None) -> date | None:
    if value is None:
        return None
    return value.replace(day=1)


def _add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _projection_id(*, contrato_id: int, cycle_number: int, slot: int) -> int:
    return -((contrato_id * 1000) + (cycle_number * 10) + slot)


def _projection_cycle_id(*, contrato_id: int, cycle_number: int) -> int:
    return -((contrato_id * 100) + cycle_number)


def _normalize_document(value: str | None) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def _is_paid_pagamento(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip() in PAID_STATUS_CODES
        or pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
    )


def _pagamento_record_key(pagamento: PagamentoMensalidade) -> tuple[object, ...]:
    return (
        _month_start(pagamento.referencia_month),
        pagamento.manual_paid_at or pagamento.updated_at or pagamento.created_at,
        pagamento.id,
    )


def _prefetched_pagamentos(contrato: Contrato) -> list[PagamentoMensalidade] | None:
    prefetched = getattr(contrato.associado, "_prefetched_objects_cache", {})
    pagamentos = prefetched.get("pagamentos_mensalidades")
    if pagamentos is None:
        return None
    return list(pagamentos)


def _query_pagamentos(contrato: Contrato) -> list[PagamentoMensalidade]:
    cpf_cnpj = _normalize_document(contrato.associado.cpf_cnpj)
    return list(
        PagamentoMensalidade.objects.filter(associado=contrato.associado)
        .union(
            PagamentoMensalidade.objects.filter(cpf_cnpj=cpf_cnpj),
            all=True,
        )
        .order_by("referencia_month", "id")
    )


def _query_baixas(contrato: Contrato) -> list[BaixaManual]:
    return list(
        BaixaManual.objects.select_related("parcela")
        .filter(parcela__associado=contrato.associado)
        .order_by("data_baixa", "id")
    )


def _query_current_parcelas(contrato: Contrato) -> list[Parcela]:
    prefetched_cycles = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
    if prefetched_cycles is not None:
        parcelas: list[Parcela] = []
        for ciclo in prefetched_cycles:
            prefetched_parcelas = getattr(ciclo, "_prefetched_objects_cache", {}).get(
                "parcelas"
            )
            if prefetched_parcelas is not None:
                parcelas.extend(list(prefetched_parcelas))
            else:
                parcelas.extend(list(ciclo.parcelas.all()))
        return parcelas
    return list(
        Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo")
    )


def _renewal_origin_refs(refinanciamento: Refinanciamento) -> list[date]:
    return sorted(
        reference
        for reference in [
            refinanciamento.ref1,
            refinanciamento.ref2,
            refinanciamento.ref3,
            refinanciamento.ref4,
        ]
        if reference is not None
    )


def get_contract_baseline_reference(
    contrato: Contrato,
    *,
    refs: list[FinancialReference] | None = None,
) -> date | None:
    if refs is None:
        paid, unpaid = _merge_financial_references(contrato)
        refs = [*paid, *unpaid]

    candidates: list[date] = []
    if refs:
        candidates.append(refs[0].referencia_mes)
    for raw_value in [
        contrato.mes_averbacao,
        contrato.auxilio_liberado_em,
        contrato.data_primeira_mensalidade,
    ]:
        month_value = _month_start(raw_value)
        if month_value is not None:
            candidates.append(month_value)
    if contrato.data_aprovacao:
        candidates.append(_month_start(contrato.data_aprovacao))
    return min(candidates) if candidates else None


def refinanciamento_matches_contract_timeline(
    contrato: Contrato,
    refinanciamento: Refinanciamento,
    *,
    refs: list[FinancialReference] | None = None,
) -> bool:
    if refinanciamento.legacy_refinanciamento_id is None:
        return True
    if (refinanciamento.contrato_codigo_origem or "").strip():
        return True
    origin_refs = _renewal_origin_refs(refinanciamento)
    if not origin_refs:
        return True
    baseline = get_contract_baseline_reference(contrato, refs=refs)
    if baseline is None:
        return True
    if origin_refs[0].replace(day=1) >= baseline:
        return True
    return _legacy_renewal_has_treasury_payment_proof(
        contrato,
        refinanciamento,
    )


def _reference_sort_key(item: FinancialReference) -> tuple[date, date | None]:
    return item.referencia_mes, item.data_pagamento


def _merge_financial_references(
    contrato: Contrato,
) -> tuple[list[FinancialReference], list[FinancialReference]]:
    pagamentos = _prefetched_pagamentos(contrato)
    if pagamentos is None:
        pagamentos = _query_pagamentos(contrato)
    baixas = _query_baixas(contrato)
    fallback_parcelas = _query_current_parcelas(contrato)

    paid_by_reference: dict[date, FinancialReference] = {}
    unpaid_by_reference: dict[date, FinancialReference] = {}

    for pagamento in sorted(pagamentos, key=_pagamento_record_key):
        referencia = _month_start(pagamento.referencia_month)
        if referencia is None:
            continue
        if _is_paid_pagamento(pagamento):
            paid_at = (
                pagamento.manual_paid_at.date()
                if pagamento.manual_paid_at
                else (pagamento.created_at or timezone.now()).date()
            )
            paid_by_reference[referencia] = FinancialReference(
                referencia_mes=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=paid_at,
                valor=pagamento.valor or contrato.valor_mensalidade,
                observacao="Quitado via importação/ajuste manual.",
                source="pagamento_mensalidade",
            )
            unpaid_by_reference.pop(referencia, None)
            continue

        if referencia in paid_by_reference:
            continue
        unpaid_by_reference[referencia] = FinancialReference(
            referencia_mes=referencia,
            status=Parcela.Status.NAO_DESCONTADO,
            data_pagamento=None,
            valor=pagamento.valor or contrato.valor_mensalidade,
            observacao="Competência não quitada no retorno.",
            source="pagamento_mensalidade",
        )

    for baixa in baixas:
        referencia = _month_start(getattr(baixa.parcela, "referencia_mes", None))
        if referencia is None:
            continue
        paid_by_reference[referencia] = FinancialReference(
            referencia_mes=referencia,
            status=Parcela.Status.DESCONTADO,
            data_pagamento=baixa.data_baixa,
            valor=baixa.valor_pago or contrato.valor_mensalidade,
            observacao=baixa.observacao or "Quitado por baixa manual.",
            source="baixa_manual",
        )
        unpaid_by_reference.pop(referencia, None)

    for parcela in fallback_parcelas:
        referencia = _month_start(parcela.referencia_mes)
        if referencia is None or referencia in paid_by_reference or referencia in unpaid_by_reference:
            continue
        if parcela.status == Parcela.Status.NAO_DESCONTADO:
            unpaid_by_reference[referencia] = FinancialReference(
                referencia_mes=referencia,
                status=Parcela.Status.NAO_DESCONTADO,
                data_pagamento=None,
                valor=parcela.valor,
                observacao=parcela.observacao,
                source="parcela_fallback",
            )
        elif parcela.status == Parcela.Status.DESCONTADO:
            paid_by_reference[referencia] = FinancialReference(
                referencia_mes=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=parcela.data_pagamento,
                valor=parcela.valor,
                observacao=parcela.observacao,
                source="parcela_fallback",
            )

    paid = sorted(paid_by_reference.values(), key=_reference_sort_key)
    unpaid = sorted(unpaid_by_reference.values(), key=_reference_sort_key)
    return paid, unpaid


def _seed_reference(
    contrato: Contrato,
    refs: list[FinancialReference],
    renewals: list[EffectiveRenewal],
) -> date:
    candidates: list[date] = []
    if refs:
        candidates.append(refs[0].referencia_mes)
    baseline = get_contract_baseline_reference(contrato, refs=refs)
    renewal_origin_refs = sorted(
        reference
        for renewal in renewals
        for reference in _renewal_origin_refs(renewal.refinanciamento)
        if baseline is None or reference.replace(day=1) >= baseline
    )
    if renewal_origin_refs:
        candidates.append(renewal_origin_refs[0].replace(day=1))
    if contrato.mes_averbacao:
        candidates.append(contrato.mes_averbacao.replace(day=1))
    if contrato.data_primeira_mensalidade:
        candidates.append(contrato.data_primeira_mensalidade.replace(day=1))
    if contrato.data_aprovacao:
        candidates.append(_add_months(contrato.data_aprovacao.replace(day=1), 1))
    if candidates:
        return min(candidates)
    return timezone.localdate().replace(day=1)


def _contract_is_activated(contrato: Contrato, refs: list[FinancialReference]) -> bool:
    payload = get_contract_activation_payload(contrato)
    if payload["data_primeiro_ciclo_ativado"] is not None:
        return True
    if contrato.auxilio_liberado_em is not None:
        return True
    if contrato.status in {Contrato.Status.ATIVO, Contrato.Status.ENCERRADO}:
        return True
    return bool(refs)


def _effective_renewal_activation(refinanciamento: Refinanciamento) -> datetime | None:
    return (
        refinanciamento.data_ativacao_ciclo
        or refinanciamento.executado_em
        or (refinanciamento.created_at if refinanciamento.legacy_refinanciamento_id else None)
    )


def _prefetched_tesouraria_pagamentos(contrato: Contrato) -> list[Pagamento] | None:
    prefetched = getattr(contrato.associado, "_prefetched_objects_cache", {})
    pagamentos = prefetched.get("tesouraria_pagamentos")
    if pagamentos is None:
        return None
    return list(pagamentos)


def _query_tesouraria_pagamentos(contrato: Contrato) -> list[Pagamento]:
    return list(
        Pagamento.all_objects.filter(
            cadastro=contrato.associado,
            status=Pagamento.Status.PAGO,
        ).order_by("paid_at", "created_at", "id")
    )


def _legacy_renewal_has_treasury_payment_proof(
    contrato: Contrato,
    refinanciamento: Refinanciamento,
    *,
    activated_at: datetime | None = None,
) -> bool:
    if refinanciamento.legacy_refinanciamento_id is None:
        return False

    activation_point = activated_at or _effective_renewal_activation(refinanciamento)
    if activation_point is None:
        return False

    pagamentos = _prefetched_tesouraria_pagamentos(contrato)
    if pagamentos is None:
        pagamentos = _query_tesouraria_pagamentos(contrato)

    activation_reference = activation_point.date().replace(day=1)
    expected_value = contrato.valor_mensalidade or Decimal("0")
    for pagamento in pagamentos:
        if pagamento.status != Pagamento.Status.PAGO or pagamento.paid_at is None:
            continue
        if pagamento.contrato_codigo and pagamento.contrato_codigo != contrato.codigo:
            continue
        payment_reference = pagamento.paid_at.date().replace(day=1)
        if payment_reference != activation_reference:
            continue
        if abs(pagamento.paid_at - activation_point) > timedelta(days=21):
            continue
        payment_value = pagamento.valor_pago or Decimal("0")
        if expected_value and payment_value:
            if abs(payment_value - expected_value) > Decimal("0.01"):
                continue
        notes = (pagamento.notes or "").lower()
        forma_pagamento = (pagamento.forma_pagamento or "").lower()
        if not (
            "arquivo retorno" in notes
            or "coordenador" in notes
            or "renova" in notes
            or forma_pagamento in {"manual", "pix", "dinheiro"}
        ):
            continue
        return True
    return False


def _effective_renewal_first_reference(
    contrato: Contrato,
    refinanciamento: Refinanciamento,
    activated_at: datetime,
) -> date:
    origin_refs = _renewal_origin_refs(refinanciamento)
    activation_reference = activated_at.date().replace(day=1)
    if origin_refs:
        next_reference = _add_months(origin_refs[-1].replace(day=1), 1)
        if _legacy_renewal_has_treasury_payment_proof(
            contrato,
            refinanciamento,
            activated_at=activated_at,
        ):
            return max(next_reference, activation_reference)
        return next_reference
    return activation_reference


def _is_effective_renewal(refinanciamento: Refinanciamento) -> bool:
    if refinanciamento.deleted_at is not None:
        return False
    if refinanciamento.legacy_refinanciamento_id is not None:
        return _effective_renewal_activation(refinanciamento) is not None
    return bool(
        refinanciamento.status in EFFECTIVE_REFINANCIAMENTO_STATUSES
        or refinanciamento.executado_em is not None
        or refinanciamento.data_ativacao_ciclo is not None
    )


def _effective_renewals(
    contrato: Contrato,
    *,
    refs: list[FinancialReference] | None = None,
) -> list[EffectiveRenewal]:
    prefetched = getattr(contrato.associado, "_prefetched_objects_cache", {}).get(
        "refinanciamentos"
    )
    if prefetched is not None:
        base = [item for item in prefetched if item.contrato_origem_id == contrato.id]
    else:
        base = list(
            Refinanciamento.objects.filter(contrato_origem=contrato)
            .select_related("ciclo_origem", "ciclo_destino")
            .order_by("created_at", "id")
        )

    renewals: list[EffectiveRenewal] = []
    for refinanciamento in base:
        if not _is_effective_renewal(refinanciamento):
            continue
        if not refinanciamento_matches_contract_timeline(
            contrato,
            refinanciamento,
            refs=refs,
        ):
            continue
        activated_at = _effective_renewal_activation(refinanciamento)
        if activated_at is None:
            continue
        renewals.append(
            EffectiveRenewal(
                refinanciamento=refinanciamento,
                activated_at=activated_at,
                first_reference=_effective_renewal_first_reference(
                    contrato,
                    refinanciamento,
                    activated_at,
                ),
            )
        )
    renewals.sort(key=lambda item: (item.activated_at, item.refinanciamento.id))
    return renewals


def get_contract_materialized_cycle_count(contrato: Contrato) -> int:
    paid, unpaid = _merge_financial_references(contrato)
    if not _contract_is_activated(contrato, [*paid, *unpaid]):
        return 0
    return 1 + len(_effective_renewals(contrato, refs=[*paid, *unpaid]))


def _active_operational_refinanciamentos(contrato: Contrato) -> list[Refinanciamento]:
    prefetched = getattr(contrato.associado, "_prefetched_objects_cache", {}).get(
        "refinanciamentos"
    )
    if prefetched is not None:
        base = [item for item in prefetched if item.contrato_origem_id == contrato.id]
    else:
        base = list(
            Refinanciamento.objects.filter(contrato_origem=contrato).order_by(
                "-created_at", "-id"
            )
        )
    return [
        item
        for item in base
        if item.deleted_at is None
        and item.legacy_refinanciamento_id is None
        and item.status in ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES
        and not _is_effective_renewal(item)
    ]


def _normalize_operational_status(status: str) -> str:
    mapping = {
        Refinanciamento.Status.PENDENTE_APTO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.SOLICITADO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.EM_ANALISE: Refinanciamento.Status.EM_ANALISE_RENOVACAO,
        Refinanciamento.Status.APROVADO: Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
        Refinanciamento.Status.CONCLUIDO: Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
    }
    return mapping.get(status, status)


def _serialize_comprovante(comprovante: Comprovante) -> dict[str, object]:
    arquivo_path = str(getattr(comprovante.arquivo, "name", "") or "")
    local = comprovante.arquivo_disponivel_localmente
    created_at = (
        (
            getattr(comprovante.refinanciamento, "data_ativacao_ciclo", None)
            if comprovante.refinanciamento_id
            else None
        )
        or (
            getattr(comprovante.refinanciamento, "executado_em", None)
            if comprovante.refinanciamento_id
            else None
        )
        or comprovante.data_pagamento
        or comprovante.created_at
    )
    return {
        "id": comprovante.id,
        "tipo": comprovante.tipo,
        "papel": comprovante.papel,
        "arquivo": arquivo_path or comprovante.arquivo_referencia,
        "arquivo_referencia": comprovante.arquivo_referencia,
        "arquivo_disponivel_localmente": local,
        "tipo_referencia": "local" if local else "legado_sem_arquivo",
        "nome_original": comprovante.nome_original,
        "mime": comprovante.mime,
        "size_bytes": comprovante.size_bytes,
        "data_pagamento": comprovante.data_pagamento,
        "origem": comprovante.origem,
        "created_at": created_at,
        "legacy_comprovante_id": comprovante.legacy_comprovante_id,
    }


def _synthesize_termo_payload(refinanciamento: Refinanciamento) -> dict[str, object] | None:
    if not refinanciamento.termo_antecipacao_path:
        return None
    activation_at = (
        refinanciamento.data_ativacao_ciclo
        or refinanciamento.executado_em
        or refinanciamento.created_at
    )
    return {
        "id": None,
        "tipo": Comprovante.Tipo.TERMO_ANTECIPACAO,
        "papel": Comprovante.Papel.OPERACIONAL,
        "arquivo": refinanciamento.termo_antecipacao_path,
        "arquivo_referencia": refinanciamento.termo_antecipacao_path,
        "arquivo_disponivel_localmente": False,
        "tipo_referencia": "legado_sem_arquivo",
        "nome_original": refinanciamento.termo_antecipacao_original_name,
        "mime": refinanciamento.termo_antecipacao_mime,
        "size_bytes": refinanciamento.termo_antecipacao_size_bytes,
        "data_pagamento": activation_at,
        "origem": Comprovante.Origem.LEGADO,
        "created_at": activation_at,
        "legacy_comprovante_id": None,
    }


def _cycle_documents(
    contrato: Contrato,
    *,
    cycle_number: int,
    renewal: EffectiveRenewal | None,
    include_documents: bool,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    if not include_documents:
        return [], None

    if renewal is not None:
        comprovantes = list(
            Comprovante.objects.filter(refinanciamento=renewal.refinanciamento)
            .select_related("enviado_por")
            .order_by("created_at", "id")
        )
    else:
        comprovantes = list(
            Comprovante.objects.filter(contrato=contrato, refinanciamento__isnull=True)
            .filter(ciclo__numero=cycle_number)
            .select_related("enviado_por")
            .order_by("created_at", "id")
        )

    termo = next(
        (
            _serialize_comprovante(comprovante)
            for comprovante in comprovantes
            if comprovante.tipo == Comprovante.Tipo.TERMO_ANTECIPACAO
        ),
        None,
    )
    comprovantes_ciclo = [
        _serialize_comprovante(comprovante)
        for comprovante in comprovantes
        if comprovante.tipo != Comprovante.Tipo.TERMO_ANTECIPACAO
    ]
    if termo is None and renewal is not None:
        termo = _synthesize_termo_payload(renewal.refinanciamento)
    return comprovantes_ciclo, termo


def _build_projection_parcela(
    *,
    contrato: Contrato,
    cycle_number: int,
    slot_number: int,
    referencia_mes: date,
    status: str,
    data_pagamento: date | None = None,
    observacao: str = "",
    valor: Decimal | None = None,
) -> dict[str, object]:
    return {
        "id": _projection_id(
            contrato_id=contrato.id,
            cycle_number=cycle_number,
            slot=slot_number,
        ),
        "numero": slot_number,
        "referencia_mes": referencia_mes,
        "valor": valor or contrato.valor_mensalidade,
        "data_vencimento": referencia_mes,
        "status": status,
        "data_pagamento": data_pagamento,
        "observacao": observacao,
    }


def _build_cycle_dict(
    *,
    contrato: Contrato,
    cycle_number: int,
    referencias: list[date],
    parcelas: list[dict[str, object]],
    status: str,
    phase_slug: str,
    financial_slug: str,
    activation_at: datetime | None,
    activation_source: str,
    activation_inferred: bool,
    data_solicitacao_renovacao: datetime | None,
    renewal: EffectiveRenewal | None,
    refinanciamento_operacional: Refinanciamento | None,
    include_documents: bool,
) -> dict[str, object]:
    cycle_size = len(parcelas)
    valor_total = (contrato.valor_mensalidade * Decimal(str(cycle_size))).quantize(
        Decimal("0.01")
    )
    comprovantes_ciclo, termo_antecipacao = _cycle_documents(
        contrato,
        cycle_number=cycle_number,
        renewal=renewal,
        include_documents=include_documents,
    )
    refinement = renewal.refinanciamento if renewal is not None else refinanciamento_operacional
    visual_status = _compose_visual_status(
        phase_slug=phase_slug,
        financial_slug=financial_slug,
    )
    return {
        "id": _projection_cycle_id(contrato_id=contrato.id, cycle_number=cycle_number),
        "contrato_id": contrato.id,
        "contrato_codigo": contrato.codigo,
        "contrato_status": contrato.status,
        "numero": cycle_number,
        "data_inicio": referencias[0],
        "data_fim": referencias[-1],
        "status": status,
        "fase_ciclo": phase_slug,
        "situacao_financeira": financial_slug,
        "status_visual_slug": visual_status["status_visual_slug"],
        "status_visual_label": visual_status["status_visual_label"],
        "valor_total": valor_total,
        "data_ativacao_ciclo": activation_at,
        "origem_data_ativacao": activation_source,
        "ativacao_inferida": activation_inferred,
        "data_solicitacao_renovacao": data_solicitacao_renovacao,
        "data_renovacao": renewal.activated_at if renewal is not None else None,
        "origem_renovacao": renewal.refinanciamento.origem if renewal is not None else "",
        "primeira_competencia_ciclo": referencias[0],
        "ultima_competencia_ciclo": referencias[-1],
        "resumo_referencias": ", ".join(
            referencia.strftime("%m/%Y") for referencia in referencias
        ),
        "refinanciamento_id": refinement.id if refinement is not None else None,
        "legacy_refinanciamento_id": (
            renewal.refinanciamento.legacy_refinanciamento_id if renewal is not None else None
        ),
        "comprovantes_ciclo": comprovantes_ciclo,
        "termo_antecipacao": termo_antecipacao,
        "parcelas": parcelas,
    }


def _current_cycle_defaults(
    *,
    cycle_size: int,
    references: list[date],
    paid_count: int,
    explicit_references: set[date],
    unpaid_map: dict[date, FinancialReference],
) -> dict[date, str]:
    defaults: dict[date, str] = {}
    threshold = max(cycle_size - 1, 1)
    first_unresolved: int | None = None
    for index, referencia in enumerate(references, start=1):
        if referencia in explicit_references:
            continue
        if referencia in unpaid_map:
            continue
        if first_unresolved is None:
            first_unresolved = index
        if index == cycle_size and paid_count >= threshold:
            defaults[referencia] = Parcela.Status.EM_PREVISAO
        elif index == first_unresolved:
            defaults[referencia] = Parcela.Status.EM_ABERTO
        else:
            defaults[referencia] = Parcela.Status.FUTURO
    return defaults


def _financial_row(item: FinancialReference, *, contrato: Contrato, index: int) -> dict[str, object]:
    return {
        "id": -((contrato.id * 10000) + index + 1),
        "contrato_id": contrato.id,
        "contrato_codigo": contrato.codigo,
        "referencia_mes": item.referencia_mes,
        "valor": item.valor,
        "status": item.status,
        "data_pagamento": item.data_pagamento,
        "observacao": item.observacao,
        "source": item.source,
    }


def build_contract_cycle_projection(
    contrato: Contrato,
    *,
    include_documents: bool = False,
) -> dict[str, object]:
    cycle_size = get_contract_cycle_size(contrato)
    paid, unpaid = _merge_financial_references(contrato)
    paid_map = {item.referencia_mes: item for item in paid}
    unpaid_map = {item.referencia_mes: item for item in unpaid}
    all_refs = [*paid, *unpaid]

    if not _contract_is_activated(contrato, all_refs):
        return {
            "cycle_size": cycle_size,
            "cycles": [],
            "unpaid_months": [
                _financial_row(item, contrato=contrato, index=index)
                for index, item in enumerate(
                    sorted(unpaid, key=lambda item: item.referencia_mes, reverse=True)
                )
            ],
            "status_renovacao": "",
            "refinanciamento_id": None,
            "movimentos_financeiros_avulsos": [
                _financial_row(item, contrato=contrato, index=index)
                for index, item in enumerate(
                    sorted([*paid, *unpaid], key=lambda item: item.referencia_mes)
                )
            ],
        }

    activation_payload = get_contract_activation_payload(contrato)
    renewals = _effective_renewals(contrato, refs=all_refs)
    operational_refis = _active_operational_refinanciamentos(contrato)
    operational_refi = operational_refis[0] if operational_refis else None

    cycle_start_references = [_seed_reference(contrato, paid or unpaid, renewals)]
    for renewal in renewals:
        minimum_reference = _add_months(cycle_start_references[-1], cycle_size)
        cycle_start_references.append(max(renewal.first_reference, minimum_reference))

    cycles: list[dict[str, object]] = []
    cycle_reference_set: set[date] = set()

    for index, start_reference in enumerate(cycle_start_references, start=1):
        references = [_add_months(start_reference, slot) for slot in range(cycle_size)]
        cycle_reference_set.update(references)
        renewal = renewals[index - 2] if index > 1 and index - 2 < len(renewals) else None
        next_renewal = renewals[index - 1] if index - 1 < len(renewals) else None

        explicit_statuses: dict[date, FinancialReference] = {}
        paid_count = 0
        for referencia in references:
            paid_item = paid_map.get(referencia)
            unpaid_item = unpaid_map.get(referencia)
            if paid_item is not None:
                explicit_statuses[referencia] = paid_item
                paid_count += 1
            elif unpaid_item is not None:
                explicit_statuses[referencia] = unpaid_item

        defaults = (
            _current_cycle_defaults(
                cycle_size=cycle_size,
                references=references,
                paid_count=paid_count,
                explicit_references=set(explicit_statuses),
                unpaid_map=unpaid_map,
            )
            if index == len(cycle_start_references)
            else {}
        )
        parcelas = []
        for slot, referencia in enumerate(references, start=1):
            explicit = explicit_statuses.get(referencia)
            if explicit is not None:
                parcelas.append(
                    _build_projection_parcela(
                        contrato=contrato,
                        cycle_number=index,
                        slot_number=slot,
                        referencia_mes=referencia,
                        status=explicit.status,
                        data_pagamento=explicit.data_pagamento,
                        observacao=explicit.observacao,
                        valor=explicit.valor,
                    )
                )
                continue

            parcelas.append(
                _build_projection_parcela(
                    contrato=contrato,
                    cycle_number=index,
                    slot_number=slot,
                    referencia_mes=referencia,
                    status=defaults.get(referencia, Parcela.Status.FUTURO),
                )
            )

        if next_renewal is not None:
            cycle_status = Ciclo.Status.CICLO_RENOVADO
        elif any(parcela["status"] == Parcela.Status.EM_PREVISAO for parcela in parcelas):
            cycle_status = Ciclo.Status.APTO_A_RENOVAR
        else:
            cycle_status = Ciclo.Status.ABERTO

        financial_slug = _cycle_financial_status(contrato=contrato, parcelas=parcelas)
        phase_slug = _cycle_phase_status(
            contrato=contrato,
            cycle_status=cycle_status,
            next_renewal=next_renewal,
            refinanciamento_operacional=(
                operational_refi if index == len(cycle_start_references) else None
            ),
        )

        if index == 1:
            activation_at = activation_payload["data_primeiro_ciclo_ativado"]
            activation_source = str(activation_payload["origem_data_primeiro_ciclo"])
            activation_inferred = bool(
                activation_payload["primeiro_ciclo_ativacao_inferida"]
            )
            request_at = (
                next_renewal.activated_at
                if next_renewal
                else (
                    operational_refi.data_ativacao_ciclo
                    or operational_refi.executado_em
                    or operational_refi.created_at
                    if operational_refi
                    else None
                )
            )
        else:
            activation_at = renewal.activated_at if renewal is not None else None
            activation_source = (
                renewal.refinanciamento.origem if renewal is not None else "indisponivel"
            )
            activation_inferred = False
            request_at = renewal.activated_at if renewal is not None else None

        cycles.append(
            _build_cycle_dict(
                contrato=contrato,
                cycle_number=index,
                referencias=references,
                parcelas=parcelas,
                status=cycle_status,
                phase_slug=phase_slug,
                financial_slug=financial_slug,
                activation_at=activation_at,
                activation_source=activation_source,
                activation_inferred=activation_inferred,
                data_solicitacao_renovacao=request_at,
                renewal=renewal,
                refinanciamento_operacional=(
                    operational_refi if index == len(cycle_start_references) else None
                ),
                include_documents=include_documents,
            )
        )

    unpaid_rows = [
        _financial_row(item, contrato=contrato, index=index)
        for index, item in enumerate(
            sorted(unpaid, key=lambda item: item.referencia_mes, reverse=True)
        )
    ]
    movimentos_avulsos = [
        _financial_row(item, contrato=contrato, index=index)
        for index, item in enumerate(
            sorted(
                [
                    item
                    for item in [*paid, *unpaid]
                    if item.referencia_mes not in cycle_reference_set
                ],
                key=lambda item: item.referencia_mes,
            )
        )
    ]

    status_renovacao = ""
    refinanciamento_id: int | None = None
    if operational_refi is not None:
        status_renovacao = _normalize_operational_status(operational_refi.status)
        refinanciamento_id = operational_refi.id
    elif cycles and cycles[-1]["status"] == Ciclo.Status.APTO_A_RENOVAR:
        status_renovacao = Refinanciamento.Status.APTO_A_RENOVAR

    return {
        "cycle_size": cycle_size,
        "cycles": list(sorted(cycles, key=lambda item: item["numero"], reverse=True)),
        "unpaid_months": unpaid_rows,
        "status_renovacao": status_renovacao,
        "refinanciamento_id": refinanciamento_id,
        "movimentos_financeiros_avulsos": movimentos_avulsos,
    }


def get_contract_visual_status_payload(
    contrato: Contrato,
    *,
    projection: dict[str, object] | None = None,
) -> dict[str, object]:
    projection = projection or build_contract_cycle_projection(contrato)
    cycles = list(projection.get("cycles", []))

    if not cycles:
        return _fallback_visual_status_from_models(
            associado_status=getattr(contrato.associado, "status", ""),
            contrato_status=contrato.status,
        )

    relevant_cycle = max(cycles, key=_cycle_visual_rank)
    return {
        "status_visual_slug": relevant_cycle["status_visual_slug"],
        "status_visual_label": relevant_cycle["status_visual_label"],
        "fase_ciclo": relevant_cycle["fase_ciclo"],
        "situacao_financeira": relevant_cycle["situacao_financeira"],
        "cycle_id": relevant_cycle["id"],
        "cycle_number": relevant_cycle["numero"],
    }


def get_associado_visual_status_payload(associado: Associado) -> dict[str, object]:
    contratos = list(associado.contratos.exclude(status=Contrato.Status.CANCELADO))
    candidates: list[dict[str, object]] = []

    for contrato in contratos:
        projection = build_contract_cycle_projection(contrato)
        status_payload = get_contract_visual_status_payload(
            contrato,
            projection=projection,
        )
        if (
            associado.status == Associado.Status.INATIVO
            or contrato.status == Contrato.Status.CANCELADO
            or contrato.status == Contrato.Status.ENCERRADO
        ):
            financial_priority = -1
            phase_priority = -1
        else:
            financial_priority = STATUS_VISUAL_FINANCIAL_PRIORITY.get(
                str(status_payload.get("situacao_financeira") or ""),
                -1,
            )
            phase_priority = STATUS_VISUAL_PHASE_PRIORITY.get(
                str(status_payload.get("fase_ciclo") or ""),
                -1,
            )

        candidates.append(
            {
                **status_payload,
                "financial_priority": financial_priority,
                "phase_priority": phase_priority,
                "created_at": contrato.created_at,
            }
        )

    active_candidates = [
        item
        for item in candidates
        if item["financial_priority"] >= 0 and item["phase_priority"] >= 0
    ]
    if active_candidates:
        selected = max(
            active_candidates,
            key=lambda item: (
                int(item["financial_priority"]),
                int(item["phase_priority"]),
                item["created_at"],
            ),
        )
        return {
            "status_visual_slug": selected["status_visual_slug"],
            "status_visual_label": selected["status_visual_label"],
        }

    if candidates:
        selected = max(candidates, key=lambda item: item["created_at"])
        return {
            "status_visual_slug": selected["status_visual_slug"],
            "status_visual_label": selected["status_visual_label"],
        }

    return _fallback_visual_status_from_models(
        associado_status=associado.status,
        contrato_status=Contrato.Status.EM_ANALISE,
    )
