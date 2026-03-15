from __future__ import annotations

import re
from collections.abc import Iterable

from django.db.models import Exists, OuterRef, Q, QuerySet

from apps.contratos.models import Contrato
from apps.importacao.models import PagamentoMensalidade

from .models import Item, Refinanciamento

REFINANCIAMENTO_MENSALIDADES_NECESSARIAS = 3
PAGAMENTO_STATUS_CODES_OK = ("1", "4")
REFINANCIAMENTO_ACTIVE_STATUSES = (
    Refinanciamento.Status.PENDENTE_APTO,
    Refinanciamento.Status.CONCLUIDO,
    Refinanciamento.Status.EFETIVADO,
    Refinanciamento.Status.SOLICITADO,
    Refinanciamento.Status.EM_ANALISE,
    Refinanciamento.Status.APROVADO,
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
    return Refinanciamento.objects.filter(
        associado__cpf_cnpj=cpf_cnpj,
        status__in=REFINANCIAMENTO_ACTIVE_STATUSES,
    ).exists()


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
    pagamentos = _dedupe_pagamentos_by_competencia(
        free_paid_pagamentos_queryset(contrato, for_update=for_update)
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

    livres = _dedupe_pagamentos_by_competencia(livres)
    if len(livres) >= REFINANCIAMENTO_MENSALIDADES_NECESSARIAS:
        return livres
    return get_free_paid_pagamentos(contrato)


def is_paid_pagamento(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip() in PAGAMENTO_STATUS_CODES_OK
        or pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
    )


def refinanciamento_progress(
    pagamentos: Iterable[PagamentoMensalidade],
) -> tuple[int, int]:
    livres = len(list(pagamentos))
    return min(livres, REFINANCIAMENTO_MENSALIDADES_NECESSARIAS), (
        REFINANCIAMENTO_MENSALIDADES_NECESSARIAS
    )
