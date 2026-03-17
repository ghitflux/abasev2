from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.tesouraria.models import BaixaManual
from core.file_references import build_filefield_reference, build_storage_reference

MANUAL_STATUS_OK = {"pago", "ok", "concluido", "concluído"}

QUITACAO_LABELS = {
    "arquivo_retorno": "Quitado por arquivo retorno",
    "baixa_manual": "Quitado por baixa manual",
    "manual": "Quitado por comprovante manual",
    "relatorio_competencia": "Quitado por relatório manual",
    "manual_sem_arquivo": "Quitado manualmente sem anexo",
    "pendente": "Competência pendente",
}


@dataclass(frozen=True)
class CompetenciaEvidencePayload:
    evidencias: list[dict[str, object]]
    data_importacao_arquivo: datetime | None
    data_baixa_manual: date | None
    origem_quitacao: str
    origem_quitacao_label: str


def _normalize_manual_status(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized


def _payment_reference_key(item: PagamentoMensalidade) -> tuple[object, date]:
    associado_key = item.associado_id or re.sub(r"\D", "", item.cpf_cnpj or "")
    return associado_key, item.referencia_month


def _payment_recency_key(item: PagamentoMensalidade) -> tuple[object, int]:
    return (
        item.manual_paid_at or item.updated_at or item.created_at,
        item.id,
    )


def canonicalize_pagamentos(
    pagamentos: Iterable[PagamentoMensalidade],
) -> list[PagamentoMensalidade]:
    canonical: dict[tuple[object, date], PagamentoMensalidade] = {}
    for item in pagamentos:
        key = _payment_reference_key(item)
        current = canonical.get(key)
        if current is None or _payment_recency_key(item) >= _payment_recency_key(current):
            canonical[key] = item
    return list(canonical.values())


def get_pagamento_for_reference(
    *,
    associado,
    referencia_mes: date,
) -> PagamentoMensalidade | None:
    cpf_cnpj = re.sub(r"\D", "", associado.cpf_cnpj or "")
    pagamentos = canonicalize_pagamentos(
        PagamentoMensalidade.objects.filter(referencia_month=referencia_mes).filter(
            associado=associado
        )
        | PagamentoMensalidade.objects.filter(
            referencia_month=referencia_mes,
            cpf_cnpj=cpf_cnpj,
        )
    )
    return pagamentos[0] if pagamentos else None


def _manual_report_reference(
    referencia_mes: date,
    *,
    request=None,
) -> tuple[dict[str, object] | None, datetime | None]:
    arquivo = (
        ArquivoRetorno.objects.filter(
            competencia=referencia_mes,
            formato=ArquivoRetorno.Formato.MANUAL,
            status=ArquivoRetorno.Status.CONCLUIDO,
        )
        .order_by("-processado_em", "-created_at", "-id")
        .first()
    )
    if arquivo is None:
        return None, None

    reference = build_storage_reference(
        arquivo.arquivo_url,
        request=request,
        missing_type="relatorio_competencia",
        local_type="relatorio_competencia",
    )
    return (
        {
            "id": f"manual-report-{arquivo.id}",
            "nome": arquivo.arquivo_nome or f"Relatório mensal {referencia_mes:%m/%Y}",
            "url": reference.url,
            "arquivo_referencia": reference.arquivo_referencia,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
            "origem": "relatorio_competencia",
            "papel": "",
            "tipo": "relatorio_competencia",
            "status": "baixa_efetuada",
            "competencia": referencia_mes,
            "created_at": arquivo.processado_em or arquivo.created_at,
        },
        arquivo.processado_em or arquivo.created_at,
    )


def _sort_arquivo_items(
    items: Iterable[ArquivoRetornoItem],
) -> list[ArquivoRetornoItem]:
    return sorted(
        items,
        key=lambda item: (
            getattr(getattr(item, "arquivo_retorno", None), "processado_em", None)
            or getattr(getattr(item, "arquivo_retorno", None), "created_at", None)
            or item.created_at,
            item.id,
        ),
    )


def build_competencia_evidence_payload(
    *,
    referencia_mes: date,
    arquivo_items: Iterable[ArquivoRetornoItem] = (),
    pagamento_mensalidade: PagamentoMensalidade | None = None,
    baixa_manual: BaixaManual | None = None,
    request=None,
) -> CompetenciaEvidencePayload:
    evidencias: list[dict[str, object]] = []
    import_dates: list[datetime] = []
    has_manual_report_reference = False

    for item in _sort_arquivo_items(arquivo_items):
        arquivo = getattr(item, "arquivo_retorno", None)
        if not arquivo or not arquivo.arquivo_url:
            continue

        created_at = arquivo.processado_em or arquivo.created_at
        if created_at is not None:
            import_dates.append(created_at)

        if arquivo.formato == ArquivoRetorno.Formato.MANUAL:
            reference = build_storage_reference(
                arquivo.arquivo_url,
                request=request,
                missing_type="relatorio_competencia",
                local_type="relatorio_competencia",
            )
            origem = "relatorio_competencia"
            tipo = "relatorio_competencia"
            nome = arquivo.arquivo_nome or f"Relatório mensal {referencia_mes:%m/%Y}"
            has_manual_report_reference = True
        else:
            reference = build_storage_reference(
                arquivo.arquivo_url,
                request=request,
                missing_type="legado_sem_arquivo",
            )
            origem = "arquivo_retorno"
            tipo = "arquivo_retorno"
            nome = arquivo.arquivo_nome or f"Arquivo retorno {referencia_mes:%m/%Y}"

        evidencias.append(
            {
                "id": f"retorno-{item.id}",
                "nome": nome,
                "url": reference.url,
                "arquivo_referencia": reference.arquivo_referencia,
                "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                "tipo_referencia": reference.tipo_referencia,
                "origem": origem,
                "papel": "",
                "tipo": tipo,
                "status": item.resultado_processamento or "",
                "competencia": referencia_mes,
                "created_at": created_at,
            }
        )

    manual_status = _normalize_manual_status(
        pagamento_mensalidade.manual_status if pagamento_mensalidade else None
    )
    if pagamento_mensalidade and pagamento_mensalidade.manual_comprovante_path:
        reference = build_storage_reference(
            pagamento_mensalidade.manual_comprovante_path,
            request=request,
            missing_type="legado_sem_arquivo",
        )
        evidencias.append(
            {
                "id": f"manual-{pagamento_mensalidade.id}",
                "nome": pagamento_mensalidade.manual_forma_pagamento or "Comprovante manual",
                "url": reference.url,
                "arquivo_referencia": reference.arquivo_referencia,
                "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                "tipo_referencia": reference.tipo_referencia,
                "origem": "manual",
                "papel": "",
                "tipo": "manual",
                "status": pagamento_mensalidade.manual_status or "",
                "competencia": referencia_mes,
                "created_at": pagamento_mensalidade.manual_paid_at
                or pagamento_mensalidade.created_at,
            }
        )
    elif (
        pagamento_mensalidade
        and manual_status in MANUAL_STATUS_OK
        and not has_manual_report_reference
    ):
        report_reference, imported_at = _manual_report_reference(
            referencia_mes,
            request=request,
        )
        if report_reference is not None:
            evidencias.append(report_reference)
            if imported_at is not None:
                import_dates.append(imported_at)

    if baixa_manual and baixa_manual.comprovante:
        reference = build_filefield_reference(
            baixa_manual.comprovante,
            request=request,
        )
        evidencias.append(
            {
                "id": f"baixa-manual-{baixa_manual.id}",
                "nome": baixa_manual.nome_comprovante or "Comprovante baixa manual",
                "url": reference.url,
                "arquivo_referencia": reference.arquivo_referencia,
                "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                "tipo_referencia": reference.tipo_referencia,
                "origem": "baixa_manual",
                "papel": "",
                "tipo": "baixa_manual",
                "status": "baixa_efetuada",
                "competencia": referencia_mes,
                "created_at": baixa_manual.created_at,
            }
        )

    if any(item["origem"] == "arquivo_retorno" for item in evidencias):
        origem_quitacao = "arquivo_retorno"
    elif any(item["origem"] == "baixa_manual" for item in evidencias):
        origem_quitacao = "baixa_manual"
    elif any(item["origem"] == "manual" for item in evidencias):
        origem_quitacao = "manual"
    elif any(item["origem"] == "relatorio_competencia" for item in evidencias):
        origem_quitacao = "relatorio_competencia"
    elif pagamento_mensalidade and manual_status in MANUAL_STATUS_OK:
        origem_quitacao = "manual_sem_arquivo"
    else:
        origem_quitacao = "pendente"

    data_baixa_manual = None
    if baixa_manual is not None:
        data_baixa_manual = baixa_manual.data_baixa
    elif pagamento_mensalidade and pagamento_mensalidade.manual_paid_at:
        data_baixa_manual = pagamento_mensalidade.manual_paid_at.date()

    return CompetenciaEvidencePayload(
        evidencias=evidencias,
        data_importacao_arquivo=max(import_dates) if import_dates else None,
        data_baixa_manual=data_baixa_manual,
        origem_quitacao=origem_quitacao,
        origem_quitacao_label=QUITACAO_LABELS[origem_quitacao],
    )
