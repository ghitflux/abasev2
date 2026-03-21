from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Q

from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetornoItem
from apps.tesouraria.initial_payment import build_initial_payment_payload
from apps.tesouraria.payment_evidence import (
    build_competencia_evidence_payload,
    get_pagamento_for_reference,
)
from apps.tesouraria.models import BaixaManual
from core.file_references import build_storage_reference


@dataclass(frozen=True)
class ParcelaDetailTarget:
    kind: str
    cycle: dict[str, Any] | None
    parcela: dict[str, Any] | None
    unpaid: dict[str, Any] | None


def _humanize_tipo(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _normalize_reference_document(
    item: dict[str, Any],
    *,
    request=None,
) -> dict[str, object]:
    storage_path = str(item.get("arquivo") or item.get("arquivo_referencia") or "")
    tipo_referencia = str(item.get("tipo_referencia") or "legado_sem_arquivo")
    reference = build_storage_reference(
        storage_path,
        request=request,
        missing_type=tipo_referencia or "legado_sem_arquivo",
        local_type="local",
    )
    return {
        "id": str(item.get("id") or f"documento-{storage_path}"),
        "nome": str(item.get("nome_original") or _humanize_tipo(str(item.get("tipo") or "documento"))),
        "url": reference.url,
        "arquivo_referencia": str(item.get("arquivo_referencia") or storage_path),
        "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
        "tipo_referencia": reference.tipo_referencia or tipo_referencia,
        "origem": str(item.get("origem") or ""),
        "papel": str(item.get("papel") or ""),
        "tipo": str(item.get("tipo") or ""),
        "status": "",
        "competencia": None,
        "created_at": item.get("created_at"),
    }


def _query_actual_parcela(
    *,
    contrato: Contrato,
    referencia_mes: date,
) -> Parcela | None:
    return (
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            referencia_mes=referencia_mes,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo", "baixa_manual")
        .prefetch_related("itens_retorno__arquivo_retorno")
        .order_by("ciclo__numero", "numero", "id")
        .first()
    )


def _query_retorno_items(
    *,
    contrato: Contrato,
    referencia_mes: date,
    parcela: Parcela | None,
) -> list[ArquivoRetornoItem]:
    associado = contrato.associado
    cpf_cnpj = "".join(char for char in (associado.cpf_cnpj or "") if char.isdigit())
    queryset = ArquivoRetornoItem.objects.select_related("arquivo_retorno").filter(
        arquivo_retorno__competencia=referencia_mes
    )
    if parcela is not None:
        queryset = queryset.filter(
            Q(parcela=parcela)
            | Q(
                parcela__isnull=True,
                associado=associado,
            )
            | Q(
                parcela__isnull=True,
                associado__isnull=True,
                cpf_cnpj=cpf_cnpj,
            )
        )
    else:
        queryset = queryset.filter(
            Q(associado=associado)
            | Q(associado__isnull=True, cpf_cnpj=cpf_cnpj)
        )
    return list(queryset.order_by("arquivo_retorno__created_at", "id"))


def _query_baixa_manual(
    *,
    contrato: Contrato,
    referencia_mes: date,
    parcela: Parcela | None,
) -> BaixaManual | None:
    queryset = BaixaManual.objects.select_related("parcela").filter(
        parcela__associado=contrato.associado,
        parcela__referencia_mes=referencia_mes,
    )
    if parcela is not None:
        preferred = queryset.filter(parcela=parcela).order_by("-data_baixa", "-id").first()
        if preferred is not None:
            return preferred
    return queryset.order_by("-data_baixa", "-id").first()


def _resolve_target(
    projection: dict[str, object],
    *,
    referencia_mes: date,
    kind: str,
) -> ParcelaDetailTarget | None:
    cycle_match: dict[str, Any] | None = None
    parcela_match: dict[str, Any] | None = None
    for cycle in projection["cycles"]:
        current = next(
            (
                item
                for item in cycle["parcelas"]
                if item["referencia_mes"] == referencia_mes
            ),
            None,
        )
        if current is not None:
            cycle_match = cycle
            parcela_match = current
            break

    unpaid_match = next(
        (
            item
            for item in projection["unpaid_months"]
            if item["referencia_mes"] == referencia_mes
        ),
        None,
    )

    if kind == "cycle" and parcela_match is None:
        return None
    if kind == "unpaid" and unpaid_match is None:
        return None

    return ParcelaDetailTarget(
        kind=kind,
        cycle=cycle_match,
        parcela=parcela_match,
        unpaid=unpaid_match,
    )


def build_parcela_detail_payload(
    *,
    contrato: Contrato,
    referencia_mes: date,
    kind: str,
    request=None,
) -> dict[str, object]:
    projection = build_contract_cycle_projection(
        contrato,
        include_documents=True,
    )
    target = _resolve_target(
        projection,
        referencia_mes=referencia_mes,
        kind=kind,
    )
    if target is None:
        raise LookupError("Competência não encontrada para o contrato informado.")

    cycle = target.cycle
    parcela = target.parcela
    unpaid = target.unpaid
    actual_parcela = _query_actual_parcela(
        contrato=contrato,
        referencia_mes=referencia_mes,
    )
    pagamento_mensalidade = get_pagamento_for_reference(
        associado=contrato.associado,
        referencia_mes=referencia_mes,
    )
    baixa_manual = _query_baixa_manual(
        contrato=contrato,
        referencia_mes=referencia_mes,
        parcela=actual_parcela,
    )
    evidence_payload = build_competencia_evidence_payload(
        referencia_mes=referencia_mes,
        arquivo_items=_query_retorno_items(
            contrato=contrato,
            referencia_mes=referencia_mes,
            parcela=actual_parcela,
        ),
        pagamento_mensalidade=pagamento_mensalidade,
        baixa_manual=baixa_manual,
        request=request,
    )

    data_pagamento = None
    valor = contrato.valor_mensalidade
    observacao = ""
    data_vencimento = None
    cycle_number = None
    numero_parcela = None
    if parcela is not None:
        data_pagamento = parcela.get("data_pagamento")
        valor = parcela.get("valor") or valor
        observacao = str(parcela.get("observacao") or "")
        data_vencimento = parcela.get("data_vencimento")
        cycle_number = int(cycle["numero"]) if cycle is not None else None
        numero_parcela = int(parcela["numero"])
    elif unpaid is not None:
        data_pagamento = unpaid.get("data_pagamento")
        valor = unpaid.get("valor") or valor
        observacao = str(unpaid.get("observacao") or "")
        data_vencimento = getattr(actual_parcela, "data_vencimento", None)
        if cycle is not None:
            cycle_number = int(cycle["numero"])
            numero_parcela = next(
                (
                    int(item["numero"])
                    for item in cycle["parcelas"]
                    if item["referencia_mes"] == referencia_mes
                ),
                None,
            )

    documentos_ciclo: list[dict[str, object]] = []
    termo_antecipacao: dict[str, object] | None = None
    data_pagamento_tesouraria = None
    if cycle is not None:
        if int(cycle["numero"]) == 1:
            initial_payment = build_initial_payment_payload(
                contrato,
                request=request,
            )
            documentos_ciclo = initial_payment.evidencias
            data_pagamento_tesouraria = initial_payment.paid_at
        else:
            documentos_ciclo = [
                _normalize_reference_document(item, request=request)
                for item in cycle["comprovantes_ciclo"]
            ]
            if cycle.get("termo_antecipacao") is not None:
                termo_antecipacao = _normalize_reference_document(
                    cycle["termo_antecipacao"],
                    request=request,
                )
            data_pagamento_tesouraria = (
                cycle.get("data_renovacao") or cycle.get("data_ativacao_ciclo")
            )

    return {
        "contrato_id": contrato.id,
        "contrato_codigo": contrato.codigo,
        "cycle_number": cycle_number,
        "numero_parcela": numero_parcela,
        "kind": kind,
        "referencia_mes": referencia_mes,
        "status": str(
            parcela["status"]
            if parcela is not None
            else unpaid["status"]
            if unpaid is not None
            else ""
        ),
        "valor": valor,
        "data_vencimento": data_vencimento,
        "observacao": observacao,
        "data_pagamento": data_pagamento or evidence_payload.data_baixa_manual,
        "data_importacao_arquivo": evidence_payload.data_importacao_arquivo,
        "data_baixa_manual": evidence_payload.data_baixa_manual,
        "data_pagamento_tesouraria": data_pagamento_tesouraria,
        "origem_quitacao": evidence_payload.origem_quitacao,
        "origem_quitacao_label": evidence_payload.origem_quitacao_label,
        "competencia_evidencias": evidence_payload.evidencias,
        "documentos_ciclo": documentos_ciclo,
        "termo_antecipacao": termo_antecipacao,
    }
