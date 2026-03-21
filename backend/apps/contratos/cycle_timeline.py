from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import Pagamento

from .models import Ciclo, Contrato, Parcela

CICLO_TOTAL_PARCELAS = 3
RENOVACAO_PAGAMENTOS_MINIMOS = 2

_INITIAL_PAYMENT_LOOKBACK_DAYS = 31
_INITIAL_PAYMENT_LOOKAHEAD_DAYS = 45
_RENOVACAO_PAYMENT_LOOKBACK_DAYS = 15
_RENOVACAO_PAYMENT_LOOKAHEAD_DAYS = 45


@dataclass(frozen=True)
class ActivationInfo:
    activated_at: datetime | None
    source: str
    inferred: bool = False
    refinanciamento_id: int | None = None
    tesouraria_pagamento_id: int | None = None


def normalize_cycle_size(value: int | None) -> int:
    if value == 4:
        return 4
    return 3


def get_contract_cycle_size(contract_or_cycle: Contrato | Ciclo | None) -> int:
    if contract_or_cycle is None:
        return CICLO_TOTAL_PARCELAS
    if isinstance(contract_or_cycle, Ciclo):
        contrato = contract_or_cycle.contrato
    else:
        contrato = contract_or_cycle
    return normalize_cycle_size(getattr(contrato, "prazo_meses", None))


def get_future_generation_threshold(contract_or_cycle: Contrato | Ciclo | None) -> int:
    cycle_size = get_contract_cycle_size(contract_or_cycle)
    return max(cycle_size - 1, 1)


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _aware_start(value: date) -> datetime:
    return timezone.make_aware(datetime.combine(value, time.min))


def _aware_end(value: date) -> datetime:
    return timezone.make_aware(datetime.combine(value, time.max))


def _iter_contract_cycles(contrato: Contrato) -> list[Ciclo]:
    cached = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
    cycles = list(cached) if cached is not None else list(contrato.ciclos.all())
    return sorted(cycles, key=lambda item: (item.numero, item.id))


def _iter_cycle_parcelas(ciclo: Ciclo) -> list[Parcela]:
    cached = getattr(ciclo, "_prefetched_objects_cache", {}).get("parcelas")
    parcelas = list(cached) if cached is not None else list(ciclo.parcelas.all())
    return sorted(parcelas, key=lambda item: (item.numero, item.id))


def get_cycle_references(ciclo: Ciclo) -> tuple[date, ...]:
    parcelas = _iter_cycle_parcelas(ciclo)
    if parcelas:
        return tuple(
            parcela.referencia_mes.replace(day=1)
            for parcela in sorted(parcelas, key=lambda item: (item.numero, item.id))
        )
    start_reference = ciclo.data_inicio.replace(day=1)
    cycle_size = get_contract_cycle_size(ciclo)
    return tuple(add_months(start_reference, index) for index in range(cycle_size))


def get_current_cycle(contrato: Contrato) -> Ciclo | None:
    ciclos = _iter_contract_cycles(contrato)
    if not ciclos:
        return None
    non_future = [ciclo for ciclo in ciclos if ciclo.status != Ciclo.Status.FUTURO]
    if non_future:
        return non_future[-1]
    return ciclos[-1]


def get_first_cycle(contrato: Contrato) -> Ciclo | None:
    ciclos = _iter_contract_cycles(contrato)
    if not ciclos:
        return None
    return ciclos[0]


def get_next_cycle(contrato: Contrato, ciclo: Ciclo) -> Ciclo | None:
    for candidate in _iter_contract_cycles(contrato):
        if candidate.numero == ciclo.numero + 1:
            return candidate
    return None


def count_discounted_parcelas(ciclo: Ciclo) -> int:
    return sum(
        1
        for parcela in _iter_cycle_parcelas(ciclo)
        if parcela.status == Parcela.Status.DESCONTADO
    )


def get_cycle_origin_references(ciclo: Ciclo) -> tuple[date | None, ...]:
    referencias = list(get_cycle_references(ciclo))
    while len(referencias) < get_contract_cycle_size(ciclo):
        referencias.append(None)
    return tuple(referencias)


def get_cycle_request_key(ciclo: Ciclo) -> str:
    return "|".join(referencia.strftime("%Y-%m") for referencia in get_cycle_references(ciclo))


def get_cycle_request_competencia(ciclo: Ciclo) -> date:
    referencias = get_cycle_references(ciclo)
    if not referencias:
        return ciclo.data_fim.replace(day=1)
    return add_months(referencias[-1], 1)


def get_destination_cycle_start(ciclo: Ciclo) -> date:
    return get_cycle_request_competencia(ciclo)


def _normalize_document(value: str | None) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def _paid_tesouraria_queryset(contrato: Contrato):
    return Pagamento.objects.filter(
        cadastro=contrato.associado,
        status=Pagamento.Status.PAGO,
        paid_at__isnull=False,
    ).order_by("paid_at", "id")


def _paid_tesouraria_candidates(contrato: Contrato) -> list[Pagamento]:
    cached = getattr(contrato.associado, "_prefetched_objects_cache", {}).get(
        "tesouraria_pagamentos"
    )
    if cached is not None:
        payments = [
            pagamento
            for pagamento in cached
            if pagamento.status == Pagamento.Status.PAGO and pagamento.paid_at is not None
        ]
        payments.sort(key=lambda item: (item.paid_at, item.id))
    else:
        payments = list(_paid_tesouraria_queryset(contrato))

    exact_contract = [
        pagamento for pagamento in payments if pagamento.contrato_codigo == contrato.codigo
    ]
    return exact_contract or payments


def _select_initial_tesouraria_payment(ciclo: Ciclo) -> Pagamento | None:
    contrato = ciclo.contrato
    base_date = contrato.data_aprovacao or contrato.data_contrato or ciclo.data_inicio
    min_dt = _aware_start(base_date - timedelta(days=_INITIAL_PAYMENT_LOOKBACK_DAYS))
    max_dt = _aware_end(ciclo.data_inicio + timedelta(days=_INITIAL_PAYMENT_LOOKAHEAD_DAYS))
    for pagamento in _paid_tesouraria_candidates(contrato):
        if pagamento.paid_at is None:
            continue
        if min_dt <= pagamento.paid_at <= max_dt:
            return pagamento
    return None


def get_destination_refinanciamento(ciclo: Ciclo) -> Refinanciamento | None:
    try:
        return ciclo.refinanciamento_destino
    except (
        Refinanciamento.DoesNotExist,
        Refinanciamento.MultipleObjectsReturned,
    ):
        return (
            Refinanciamento.objects.select_related("contrato_origem", "ciclo_destino")
            .filter(ciclo_destino=ciclo)
            .order_by("created_at", "id")
            .first()
        )


def get_origin_refinanciamento(ciclo: Ciclo) -> Refinanciamento | None:
    cached = getattr(ciclo, "_prefetched_objects_cache", {}).get("refinanciamentos_origem")
    if cached is not None:
        ordered = sorted(cached, key=lambda item: (item.created_at, item.id))
        return ordered[0] if ordered else None
    return (
        Refinanciamento.objects.select_related("contrato_origem", "ciclo_destino")
        .filter(ciclo_origem=ciclo)
        .order_by("created_at", "id")
        .first()
    )


def _infer_refinanciamento_activation(refinanciamento: Refinanciamento) -> Pagamento | None:
    contrato = refinanciamento.contrato_origem
    if contrato is None:
        return None

    anchor = (
        refinanciamento.ciclo_destino.data_inicio
        if refinanciamento.ciclo_destino_id and refinanciamento.ciclo_destino
        else refinanciamento.competencia_solicitada
    ).replace(day=1)
    min_dt = _aware_start(anchor - timedelta(days=_RENOVACAO_PAYMENT_LOOKBACK_DAYS))
    max_dt = _aware_end(anchor + timedelta(days=_RENOVACAO_PAYMENT_LOOKAHEAD_DAYS))

    for pagamento in _paid_tesouraria_candidates(contrato):
        if pagamento.paid_at is None:
            continue
        if min_dt <= pagamento.paid_at <= max_dt:
            return pagamento
    return None


def get_refinanciamento_activation_info(refinanciamento: Refinanciamento) -> ActivationInfo:
    if refinanciamento.data_ativacao_ciclo is not None:
        return ActivationInfo(
            activated_at=refinanciamento.data_ativacao_ciclo,
            source=refinanciamento.origem or "refinanciamento",
            refinanciamento_id=refinanciamento.id,
        )

    if refinanciamento.executado_em is not None:
        return ActivationInfo(
            activated_at=refinanciamento.executado_em,
            source=refinanciamento.origem or "refinanciamento",
            refinanciamento_id=refinanciamento.id,
        )

    inferred_payment = _infer_refinanciamento_activation(refinanciamento)
    if inferred_payment is not None:
        return ActivationInfo(
            activated_at=inferred_payment.paid_at,
            source="tesouraria_pagamento",
            inferred=True,
            refinanciamento_id=refinanciamento.id,
            tesouraria_pagamento_id=inferred_payment.id,
        )

    return ActivationInfo(
        activated_at=None,
        source="indisponivel",
        refinanciamento_id=refinanciamento.id,
    )


def get_cycle_activation_info(
    ciclo: Ciclo,
    *,
    allow_fallback: bool = True,
) -> ActivationInfo:
    if ciclo.numero <= 1:
        payment = _select_initial_tesouraria_payment(ciclo)
        if payment is not None:
            return ActivationInfo(
                activated_at=payment.paid_at,
                source="tesouraria_pagamento",
                tesouraria_pagamento_id=payment.id,
            )

        if allow_fallback:
            contrato = ciclo.contrato
            if contrato.auxilio_liberado_em is not None:
                return ActivationInfo(
                    activated_at=_aware_start(contrato.auxilio_liberado_em),
                    source="auxilio_liberado_em",
                )
            if contrato.data_aprovacao is not None:
                return ActivationInfo(
                    activated_at=_aware_start(contrato.data_aprovacao),
                    source="data_aprovacao",
                )
        return ActivationInfo(activated_at=None, source="indisponivel")

    refinanciamento = get_destination_refinanciamento(ciclo)
    if refinanciamento is not None:
        info = get_refinanciamento_activation_info(refinanciamento)
        if info.activated_at is not None:
            return info

    return ActivationInfo(activated_at=None, source="indisponivel")


def get_contract_first_cycle_activation_info(
    contrato: Contrato,
    *,
    allow_fallback: bool = True,
) -> ActivationInfo:
    ciclo = get_first_cycle(contrato)
    if ciclo is None:
        return ActivationInfo(activated_at=None, source="indisponivel")
    return get_cycle_activation_info(ciclo, allow_fallback=allow_fallback)


def get_cycle_activation_payload(ciclo: Ciclo) -> dict[str, object]:
    info = get_cycle_activation_info(ciclo)
    request_refi = get_destination_refinanciamento(ciclo) if ciclo.numero > 1 else None
    return {
        "data_ativacao_ciclo": info.activated_at,
        "origem_data_ativacao": info.source,
        "ativacao_inferida": info.inferred,
        "data_solicitacao_renovacao": request_refi.created_at if request_refi else None,
    }


def get_contract_activation_payload(contrato: Contrato) -> dict[str, object]:
    first_cycle_info = get_contract_first_cycle_activation_info(contrato)
    return {
        "data_primeiro_ciclo_ativado": first_cycle_info.activated_at,
        "origem_data_primeiro_ciclo": first_cycle_info.source,
        "primeiro_ciclo_ativacao_inferida": first_cycle_info.inferred,
    }


def _dedupe_pagamentos_by_competencia(
    pagamentos: list[PagamentoMensalidade],
) -> list[PagamentoMensalidade]:
    canonical: dict[tuple[object, object], PagamentoMensalidade] = {}
    for pagamento in pagamentos:
        key = (
            pagamento.associado_id or _normalize_document(pagamento.cpf_cnpj),
            pagamento.referencia_month,
        )
        current = canonical.get(key)
        recency_key = (
            pagamento.manual_paid_at or pagamento.updated_at or pagamento.created_at,
            pagamento.id,
        )
        if current is None:
            canonical[key] = pagamento
            continue
        current_key = (
            current.manual_paid_at or current.updated_at or current.created_at,
            current.id,
        )
        if recency_key >= current_key:
            canonical[key] = pagamento
    return sorted(canonical.values(), key=lambda item: (item.referencia_month, item.id))


def _is_paid_pagamento_mensalidade(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip() in {"1", "4"}
        or pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
    )


def get_cycle_paid_pagamentos(
    ciclo: Ciclo,
    *,
    unconsumed_only: bool = True,
) -> list[PagamentoMensalidade]:
    referencias = get_cycle_references(ciclo)
    if not referencias:
        return []

    prefetched = getattr(ciclo.contrato.associado, "_prefetched_objects_cache", {}).get(
        "pagamentos_mensalidades"
    )
    if prefetched is not None:
        pagamentos = [
            pagamento
            for pagamento in prefetched
            if pagamento.referencia_month in referencias and _is_paid_pagamento_mensalidade(pagamento)
        ]
        filtered: list[PagamentoMensalidade] = []
        for pagamento in sorted(pagamentos, key=lambda item: (item.referencia_month, item.id)):
            if not unconsumed_only:
                filtered.append(pagamento)
                continue
            itens_cache = getattr(pagamento, "_prefetched_objects_cache", {})
            refi_itens = itens_cache.get("refi_itens")
            if refi_itens is None:
                if pagamento.refi_itens.exists():
                    continue
            elif refi_itens:
                continue
            filtered.append(pagamento)
        return _dedupe_pagamentos_by_competencia(filtered)

    queryset = (
        PagamentoMensalidade.objects.filter(referencia_month__in=referencias)
        .filter(
            Q(associado=ciclo.contrato.associado)
            | Q(cpf_cnpj=_normalize_document(ciclo.contrato.associado.cpf_cnpj))
        )
        .order_by("referencia_month", "id")
    )
    pagamentos = [
        pagamento
        for pagamento in queryset
        if _is_paid_pagamento_mensalidade(pagamento)
    ]
    if unconsumed_only:
        pagamentos = [
            pagamento for pagamento in pagamentos if not pagamento.refi_itens.exists()
        ]
    return _dedupe_pagamentos_by_competencia(pagamentos)


def get_current_cycle_paid_pagamentos(
    contrato: Contrato,
    *,
    unconsumed_only: bool = True,
) -> list[PagamentoMensalidade]:
    ciclo = get_current_cycle(contrato)
    if ciclo is None:
        return []
    return get_cycle_paid_pagamentos(ciclo, unconsumed_only=unconsumed_only)


def get_current_cycle_payment_progress(contrato: Contrato) -> tuple[int, int]:
    pagamentos = get_current_cycle_paid_pagamentos(contrato)
    cycle_size = get_contract_cycle_size(contrato)
    return min(len(pagamentos), cycle_size), cycle_size
