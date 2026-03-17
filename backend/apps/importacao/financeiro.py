from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from core.file_references import build_storage_reference

from .legacy import LegacyPagamentoSnapshot, list_legacy_pagamento_snapshots
from .models import ArquivoRetorno, PagamentoMensalidade

RETORNO_MENSALIDADE_MIN = Decimal("100.00")
RETORNO_VALORES_3050 = {Decimal("30.00"), Decimal("50.00")}

STATUS_LABELS = {
    "1": "Efetivado",
    "4": "Efetivado c/ diferença",
    "2": "Sem margem (temp.)",
    "3": "Não lançado (outros)",
    "5": "Problemas técnicos",
    "6": "Com erros",
    "S": "Compra dívida / Suspensão",
}

MANUAL_STATUS_OK = {"pago", "ok", "concluido", "concluído"}
MANUAL_STATUS_CANCELADO = {"cancelado", "cancelada"}


def _normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").strip())
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def _normalize_money(value: Decimal | None) -> Decimal:
    return value if value is not None else Decimal("0")


def pagamento_identity(item: PagamentoMensalidade) -> tuple[object, date]:
    associado_key = item.associado_id or re.sub(r"\D", "", item.cpf_cnpj or "")
    return associado_key, item.referencia_month


def pagamento_recency_key(item: PagamentoMensalidade) -> tuple[object, int]:
    return (
        item.manual_paid_at or item.updated_at or item.created_at,
        item.id,
    )


def canonicalize_pagamentos(
    pagamentos: list[PagamentoMensalidade],
) -> list[PagamentoMensalidade]:
    canonical: dict[tuple[object, date], PagamentoMensalidade] = {}
    for item in pagamentos:
        key = pagamento_identity(item)
        current = canonical.get(key)
        if current is None or pagamento_recency_key(item) >= pagamento_recency_key(current):
            canonical[key] = item
    return sorted(canonical.values(), key=lambda item: (item.nome_relatorio or "", item.id))


def _build_row(
    item: PagamentoMensalidade,
    *,
    legacy_snapshot: LegacyPagamentoSnapshot | None = None,
    report_reference: dict[str, object] | None = None,
) -> dict:
    status_code = (item.status_code or "").strip()
    status_label = STATUS_LABELS.get(status_code, status_code or "-")

    manual_status = (item.manual_status or "").strip() or (
        (legacy_snapshot.manual_status or "").strip() if legacy_snapshot else ""
    )
    manual_status = manual_status or None
    manual_status_lc = _normalize_text(manual_status)
    recebido_manual = (
        item.recebido_manual
        if item.recebido_manual is not None
        else legacy_snapshot.recebido_manual if legacy_snapshot else None
    )
    manual_paid_at = item.manual_paid_at or (legacy_snapshot.manual_paid_at if legacy_snapshot else None)
    manual_forma_pagamento = item.manual_forma_pagamento or (
        legacy_snapshot.manual_forma_pagamento if legacy_snapshot else None
    )
    manual_comprovante_path = item.manual_comprovante_path or (
        legacy_snapshot.manual_comprovante_path if legacy_snapshot else None
    )

    ok_arquivo = status_code in {"1", "4"}
    ok_manual = manual_status_lc in MANUAL_STATUS_OK
    cancelado_manual = manual_status_lc in MANUAL_STATUS_CANCELADO
    ok = ok_manual or ok_arquivo

    esperado = _normalize_money(item.valor)
    if ok_manual:
        recebido = _normalize_money(recebido_manual) or esperado
    elif ok_arquivo:
        recebido = esperado
    else:
        recebido = Decimal("0")

    situacao_code = "ok" if ok else "bad" if cancelado_manual else "warn"
    situacao_label = "Concluído" if ok else "Cancelado" if cancelado_manual else "No arquivo"

    associado = item.associado
    associado_matricula = ""
    agente_responsavel = ""
    associado_nome = item.nome_relatorio or "-"
    if associado:
        associado_nome = associado.nome_completo or associado_nome
        associado_matricula = associado.matricula_orgao or associado.matricula or item.matricula
        if associado.agente_responsavel:
            agente_responsavel = associado.agente_responsavel.full_name

    categoria = "outros"
    if esperado >= RETORNO_MENSALIDADE_MIN:
        categoria = "mensalidades"
    elif esperado in RETORNO_VALORES_3050:
        categoria = "valores_30_50"

    evidence = {
        "origem_baixa": "sem_evidencia",
        "arquivo_referencia": None,
        "arquivo_disponivel_localmente": False,
        "tipo_referencia": "",
    }
    if ok_arquivo:
        evidence = {
            "origem_baixa": "arquivo_retorno",
            "arquivo_referencia": None,
            "arquivo_disponivel_localmente": False,
            "tipo_referencia": "",
        }
    elif ok_manual and manual_comprovante_path:
        reference = build_storage_reference(manual_comprovante_path)
        evidence = {
            "origem_baixa": "manual",
            "arquivo_referencia": reference.arquivo_referencia or None,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
        }
    elif ok_manual and report_reference is not None:
        evidence = {
            "origem_baixa": "relatorio_competencia",
            "arquivo_referencia": report_reference["arquivo_referencia"] or None,
            "arquivo_disponivel_localmente": bool(
                report_reference["arquivo_disponivel_localmente"]
            ),
            "tipo_referencia": str(report_reference["tipo_referencia"]),
        }
    elif ok_manual:
        evidence = {
            "origem_baixa": "manual_sem_arquivo",
            "arquivo_referencia": None,
            "arquivo_disponivel_localmente": False,
            "tipo_referencia": "sem_arquivo",
        }

    return {
        "id": item.id,
        "associado_id": item.associado_id,
        "associado_nome": associado_nome,
        "agente_responsavel": agente_responsavel,
        "matricula": associado_matricula or item.matricula,
        "cpf_cnpj": item.cpf_cnpj,
        "valor": esperado,
        "esperado": esperado,
        "recebido": recebido,
        "status_code": status_code,
        "status_label": status_label,
        "ok": ok,
        "situacao_code": situacao_code,
        "situacao_label": situacao_label,
        "orgao_pagto": item.orgao_pagto,
        "relatorio": item.nome_relatorio,
        "manual_status": manual_status,
        "manual_valor": recebido_manual,
        "manual_forma_pagamento": manual_forma_pagamento or None,
        "manual_paid_at": manual_paid_at,
        "manual_comprovante_path": manual_comprovante_path or None,
        **evidence,
        "categoria": categoria,
    }


def _build_totals(rows: list[dict]) -> dict:
    esperado = sum((row["esperado"] for row in rows), Decimal("0"))
    recebido = sum((row["recebido"] for row in rows), Decimal("0"))
    ok = sum(1 for row in rows if row["ok"])
    total = len(rows)
    faltando = max(total - ok, 0)
    pendente = esperado - recebido
    percentual = float((recebido / esperado) * Decimal("100")) if esperado > 0 else 0.0
    return {
        "esperado": esperado,
        "recebido": recebido,
        "ok": ok,
        "total": total,
        "faltando": faltando,
        "pendente": pendente,
        "percentual": round(percentual, 1),
    }


def build_financeiro_payload(*, competencia) -> dict:
    legacy_snapshots = list_legacy_pagamento_snapshots(competencia=competencia)
    manual_report = (
        ArquivoRetorno.objects.filter(
            competencia=competencia,
            formato=ArquivoRetorno.Formato.MANUAL,
            status=ArquivoRetorno.Status.CONCLUIDO,
        )
        .order_by("-processado_em", "-created_at", "-id")
        .first()
    )
    report_reference = None
    if manual_report is not None:
        reference = build_storage_reference(
            manual_report.arquivo_url,
            missing_type="relatorio_competencia",
            local_type="relatorio_competencia",
        )
        report_reference = {
            "arquivo_referencia": reference.arquivo_referencia,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
        }
    pagamentos = canonicalize_pagamentos(
        list(
            PagamentoMensalidade.objects.filter(referencia_month=competencia)
            .select_related("associado", "associado__agente_responsavel")
            .order_by("nome_relatorio", "id")
        )
    )
    rows = [
        _build_row(
            item,
            legacy_snapshot=legacy_snapshots.get(re.sub(r"\D", "", item.cpf_cnpj or "")),
            report_reference=report_reference,
        )
        for item in pagamentos
    ]

    return {
        "resumo": {
            **_build_totals(rows),
            "mensalidades": _build_totals(
                [row for row in rows if row["categoria"] == "mensalidades"]
            ),
            "valores_30_50": _build_totals(
                [row for row in rows if row["categoria"] == "valores_30_50"]
            ),
        },
        "rows": rows,
    }


def build_financeiro_resumo(*, competencia) -> dict:
    return build_financeiro_payload(competencia=competencia)["resumo"]
