from __future__ import annotations

import re
from collections.abc import Iterable

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Contrato
from apps.importacao.models import PagamentoMensalidade

from .models import Item, Refinanciamento

PAGAMENTO_STATUS_CODES_OK = ("1", "4")
REFINANCIAMENTO_ACTIVE_STATUSES = (
    Refinanciamento.Status.EM_ANALISE_RENOVACAO,
    Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
    Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
    Refinanciamento.Status.EM_ANALISE,
    Refinanciamento.Status.APROVADO,
    Refinanciamento.Status.CONCLUIDO,
)


def _is_effective_refinanciamento(refinanciamento: Refinanciamento) -> bool:
    return bool(
        refinanciamento.status
        in {
            Refinanciamento.Status.EFETIVADO,
            Refinanciamento.Status.CONCLUIDO,
        }
        or refinanciamento.executado_em is not None
        or refinanciamento.data_ativacao_ciclo is not None
        or refinanciamento.ciclo_destino_id is not None
    )


def normalize_document(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def paid_pagamento_filter(prefix: str = "") -> Q:
    status_code_field = f"{prefix}status_code"
    manual_status_field = f"{prefix}manual_status"
    return Q(**{f"{status_code_field}__in": PAGAMENTO_STATUS_CODES_OK}) | Q(
        **{manual_status_field: PagamentoMensalidade.ManualStatus.PAGO}
    )


def has_active_refinanciamento(contrato: Contrato) -> bool:
    cpf_cnpj = normalize_document(contrato.associado.cpf_cnpj)
    refinanciamentos = Refinanciamento.objects.filter(
        associado__cpf_cnpj=cpf_cnpj,
        status__in=REFINANCIAMENTO_ACTIVE_STATUSES,
        deleted_at__isnull=True,
    ).only("status", "executado_em", "data_ativacao_ciclo", "ciclo_destino_id")
    return any(
        not _is_effective_refinanciamento(refinanciamento)
        for refinanciamento in refinanciamentos
    )


def free_paid_pagamentos_queryset(
    contrato: Contrato,
    *,
    for_update: bool = False,
) -> QuerySet[PagamentoMensalidade]:
    cpf_cnpj = normalize_document(contrato.associado.cpf_cnpj)
    consumido_subquery = Item.objects.filter(
        pagamento_mensalidade_id=OuterRef("pk")
    )
    queryset = (
        PagamentoMensalidade.objects.filter(
            Q(associado=contrato.associado) | Q(cpf_cnpj=cpf_cnpj)
        )
        .filter(paid_pagamento_filter())
        .annotate(_consumido_refi=Exists(consumido_subquery))
        .filter(_consumido_refi=False)
        .select_related("associado")
        .order_by("referencia_month", "id")
    )
    if for_update:
        queryset = queryset.select_for_update()
    return queryset


def _pagamento_identity(pagamento: PagamentoMensalidade) -> tuple[object, object]:
    return (
        pagamento.associado_id or normalize_document(pagamento.cpf_cnpj),
        pagamento.referencia_month,
    )


def _pagamento_recency_key(pagamento: PagamentoMensalidade) -> tuple[object, int]:
    return (
        pagamento.manual_paid_at or pagamento.updated_at or pagamento.created_at,
        pagamento.id,
    )


def _dedupe_pagamentos_by_competencia(
    pagamentos: Iterable[PagamentoMensalidade],
) -> list[PagamentoMensalidade]:
    canonical: dict[tuple[object, object], PagamentoMensalidade] = {}
    for pagamento in pagamentos:
        key = _pagamento_identity(pagamento)
        current = canonical.get(key)
        if current is None or _pagamento_recency_key(pagamento) >= _pagamento_recency_key(
            current
        ):
            canonical[key] = pagamento
    return sorted(canonical.values(), key=lambda item: (item.referencia_month, item.id))


def get_free_paid_pagamentos(
    contrato: Contrato,
    *,
    limit: int | None = None,
    for_update: bool = False,
) -> list[PagamentoMensalidade]:
    if for_update:
        pagamentos = _dedupe_pagamentos_by_competencia(
            free_paid_pagamentos_queryset(contrato, for_update=True)
        )
    else:
        pagamentos = _dedupe_pagamentos_by_competencia(
            free_paid_pagamentos_queryset(contrato, for_update=False)
        )
    if limit is not None:
        pagamentos = pagamentos[:limit]
    return pagamentos


def get_prefetched_free_paid_pagamentos(
    contrato: Contrato,
) -> list[PagamentoMensalidade]:
    prefetched = getattr(contrato.associado, "_prefetched_objects_cache", {})
    pagamentos = list(prefetched.get("pagamentos_mensalidades", []))
    if not pagamentos:
        return get_free_paid_pagamentos(contrato)

    livres: list[PagamentoMensalidade] = []
    for pagamento in sorted(
        pagamentos, key=lambda item: (item.referencia_month, item.id)
    ):
        if not is_paid_pagamento(pagamento):
            continue
        itens_cache = getattr(pagamento, "_prefetched_objects_cache", {})
        refi_itens = itens_cache.get("refi_itens")
        if refi_itens is None:
            if pagamento.refi_itens.exists():
                continue
        elif refi_itens:
            continue
        livres.append(pagamento)

    return _dedupe_pagamentos_by_competencia(livres)


def is_paid_pagamento(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip() in PAGAMENTO_STATUS_CODES_OK
        or pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
    )


def refinanciamento_progress(
    pagamentos: Iterable[PagamentoMensalidade],
    *,
    contrato: Contrato | None = None,
) -> tuple[int, int]:
    livres = len(list(pagamentos))
    total = get_contract_cycle_size(contrato)
    return min(livres, total), total
