from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User

from .financeiro import build_financeiro_resumo
from .models import ArquivoRetorno, PagamentoMensalidade
from .parcelas_retorno_correction import (
    ParcelasRetornoCorrectionError,
    parse_competencia_argument,
    run_parcelas_retorno_correction,
)
from .services import ArquivoRetornoService


class ServerReturnCorrectionError(Exception):
    pass


@dataclass(slots=True)
class ExpectedReturnTotals:
    total: int
    ok: int
    faltando: int
    esperado: Decimal
    recebido: Decimal
    status_counts: dict[str, int]


def _resolve_target_arquivo(
    *,
    competencia: date,
    arquivo_retorno_id: int | None = None,
    arquivo_path: str | None = None,
    uploaded_by_id: int | None = None,
) -> ArquivoRetorno:
    if arquivo_retorno_id:
        arquivo = ArquivoRetorno.objects.filter(pk=arquivo_retorno_id).first()
        if arquivo is None:
            raise ServerReturnCorrectionError(
                f"ArquivoRetorno #{arquivo_retorno_id} não encontrado."
            )
        if arquivo.competencia != competencia:
            raise ServerReturnCorrectionError(
                f"ArquivoRetorno #{arquivo.id} pertence à competência "
                f"{arquivo.competencia:%Y-%m}, diferente de {competencia:%Y-%m}."
            )
        return arquivo

    arquivo = (
        ArquivoRetorno.objects.filter(competencia=competencia)
        .order_by(
            "-processado_em",
            "-created_at",
            "-id",
        )
        .first()
    )
    if arquivo is not None:
        return arquivo

    if not arquivo_path:
        raise ServerReturnCorrectionError(
            "Nenhum ArquivoRetorno encontrado para a competência informada; "
            "use --arquivo-path e --uploaded-by-id."
        )
    if not uploaded_by_id:
        raise ServerReturnCorrectionError(
            "--uploaded-by-id é obrigatório quando usar --arquivo-path sem ArquivoRetorno prévio."
        )

    uploaded_by = User.objects.filter(pk=uploaded_by_id).first()
    if uploaded_by is None:
        raise ServerReturnCorrectionError(f"Usuário #{uploaded_by_id} não encontrado.")

    path = Path(arquivo_path).expanduser().resolve()
    if not path.exists():
        raise ServerReturnCorrectionError(f"Arquivo não encontrado: {path}")

    service = ArquivoRetornoService()
    uploaded = SimpleUploadedFile(
        path.name,
        path.read_bytes(),
        content_type="text/plain",
    )
    arquivo = service.upload(uploaded, uploaded_by)
    if arquivo.competencia != competencia:
        raise ServerReturnCorrectionError(
            f"O arquivo enviado pertence à competência {arquivo.competencia:%Y-%m}, "
            f"diferente de {competencia:%Y-%m}."
        )
    return arquivo


def _compute_expected_totals(arquivo: ArquivoRetorno) -> ExpectedReturnTotals:
    service = ArquivoRetornoService()
    parsed = service.parser.parse(service._arquivo_path(arquivo))
    items, _duplicate_cpfs = service._deduplicar_itens_por_cpf(parsed.items)
    status_counts = Counter(str(item.get("status_codigo", "")).strip() for item in items)
    esperado = sum(Decimal(str(item.get("valor_descontado") or "0")) for item in items)
    recebido = sum(
        Decimal(str(item.get("valor_descontado") or "0"))
        for item in items
        if str(item.get("status_codigo", "")).strip() in {"1", "4"}
    )
    ok = sum(1 for item in items if str(item.get("status_codigo", "")).strip() in {"1", "4"})
    total = len(items)
    return ExpectedReturnTotals(
        total=total,
        ok=ok,
        faltando=total - ok,
        esperado=esperado,
        recebido=recebido,
        status_counts=dict(sorted(status_counts.items())),
    )


def _refresh_cached_financeiro_summary(*, arquivo: ArquivoRetorno) -> dict[str, Any]:
    arquivo.refresh_from_db()
    resumo = dict(arquivo.resultado_resumo or {})
    resumo["financeiro"] = build_financeiro_resumo(competencia=arquivo.competencia)
    arquivo.resultado_resumo = resumo
    arquivo.save(update_fields=["resultado_resumo", "updated_at"])
    return resumo["financeiro"]


def _validate_final_totals(
    *,
    competencia: date,
    arquivo: ArquivoRetorno,
    expected: ExpectedReturnTotals,
) -> dict[str, Any]:
    arquivo.refresh_from_db()
    financeiro = build_financeiro_resumo(competencia=competencia)

    resumo = arquivo.resultado_resumo or {}
    arquivo_total = int(arquivo.total_registros or 0)
    arquivo_ok = int(resumo.get("baixa_efetuada") or 0)
    arquivo_faltando = int(resumo.get("nao_descontado") or 0)
    financeiro_total = int(financeiro.get("total") or 0)
    financeiro_ok = int(financeiro.get("ok") or 0)
    financeiro_faltando = int(financeiro.get("faltando") or 0)

    errors: list[str] = []
    if arquivo_total != expected.total:
        errors.append(f"ArquivoRetorno.total_registros={arquivo_total} esperado={expected.total}")
    if arquivo_ok != expected.ok:
        errors.append(f"ArquivoRetorno.baixa_efetuada={arquivo_ok} esperado={expected.ok}")
    if arquivo_faltando != expected.faltando:
        errors.append(
            f"ArquivoRetorno.nao_descontado={arquivo_faltando} esperado={expected.faltando}"
        )
    if financeiro_total != expected.total:
        errors.append(f"Financeiro.total={financeiro_total} esperado={expected.total}")
    if financeiro_ok != expected.ok:
        errors.append(f"Financeiro.ok={financeiro_ok} esperado={expected.ok}")
    if financeiro_faltando != expected.faltando:
        errors.append(f"Financeiro.faltando={financeiro_faltando} esperado={expected.faltando}")
    if Decimal(str(financeiro.get("esperado") or "0")) != expected.esperado:
        errors.append(
            f"Financeiro.esperado={financeiro.get('esperado')} esperado={expected.esperado:.2f}"
        )
    if Decimal(str(financeiro.get("recebido") or "0")) != expected.recebido:
        errors.append(
            f"Financeiro.recebido={financeiro.get('recebido')} esperado={expected.recebido:.2f}"
        )
    if int(resumo.get("ciclo_aberto") or 0) != 0:
        errors.append(f"ArquivoRetorno.ciclo_aberto={resumo.get('ciclo_aberto')} esperado=0")

    if errors:
        raise ServerReturnCorrectionError(
            "Validação final divergente após correção:\n- " + "\n- ".join(errors)
        )

    return {
        "arquivo_retorno": {
            "id": arquivo.id,
            "status": arquivo.status,
            "total_registros": arquivo_total,
            "baixa_efetuada": arquivo_ok,
            "nao_descontado": arquivo_faltando,
            "ciclo_aberto": int(resumo.get("ciclo_aberto") or 0),
            "associados_importados": int(resumo.get("associados_importados") or 0),
        },
        "financeiro": financeiro,
    }


def run_server_return_correction(
    *,
    competencia: date,
    apply: bool,
    arquivo_retorno_id: int | None = None,
    arquivo_path: str | None = None,
    uploaded_by_id: int | None = None,
) -> dict[str, Any]:
    try:
        target_arquivo = _resolve_target_arquivo(
            competencia=competencia,
            arquivo_retorno_id=arquivo_retorno_id,
            arquivo_path=arquivo_path,
            uploaded_by_id=uploaded_by_id,
        )
    except ParcelasRetornoCorrectionError as exc:
        raise ServerReturnCorrectionError(str(exc)) from exc

    expected = _compute_expected_totals(target_arquivo)
    financeiro_before = build_financeiro_resumo(competencia=competencia)
    parcelas_report = run_parcelas_retorno_correction(
        competencia=competencia,
        apply=False,
        arquivo_retorno_id=target_arquivo.id,
    )

    report: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "competencia": competencia.isoformat(),
        "arquivo_retorno_id": target_arquivo.id,
        "arquivo_nome": target_arquivo.arquivo_nome,
        "expected": {
            "total": expected.total,
            "ok": expected.ok,
            "faltando": expected.faltando,
            "esperado": f"{expected.esperado:.2f}",
            "recebido": f"{expected.recebido:.2f}",
            "status_counts": expected.status_counts,
        },
        "financeiro_before": financeiro_before,
        "parcelas_preview": {
            "elegiveis_total": parcelas_report["parcelas_elegiveis_total"],
            "descontado_total": parcelas_report["parcelas_descontado_total"],
            "nao_descontado_total": parcelas_report["parcelas_nao_descontado_total"],
            "sem_match_total": parcelas_report["parcelas_sem_match_total"],
            "cpfs_sem_parcela_total": parcelas_report["cpfs_sem_parcela_total"],
        },
        "pagamentos_before_total": PagamentoMensalidade.objects.filter(
            referencia_month=competencia
        ).count(),
    }

    if not apply:
        return report

    ArquivoRetornoService().processar(target_arquivo.id)
    financeiro_after = _refresh_cached_financeiro_summary(arquivo=target_arquivo)
    parcelas_apply = run_parcelas_retorno_correction(
        competencia=competencia,
        apply=True,
        arquivo_retorno_id=target_arquivo.id,
    )
    validation = _validate_final_totals(
        competencia=competencia,
        arquivo=target_arquivo,
        expected=expected,
    )

    pagamentos_after_total = PagamentoMensalidade.objects.filter(
        referencia_month=competencia
    ).count()
    report["pagamentos_after_total"] = pagamentos_after_total
    report["pagamentos_extra_fora_do_arquivo_total"] = max(
        pagamentos_after_total - expected.total,
        0,
    )
    report["financeiro_after_cached"] = financeiro_after
    report.update(validation)
    report["parcelas_apply"] = {
        "elegiveis_total": parcelas_apply["parcelas_elegiveis_total"],
        "descontado_total": parcelas_apply["parcelas_descontado_total"],
        "nao_descontado_total": parcelas_apply["parcelas_nao_descontado_total"],
        "sem_match_total": parcelas_apply["parcelas_sem_match_total"],
        "cpfs_sem_parcela_total": parcelas_apply["cpfs_sem_parcela_total"],
        "smoke_test": parcelas_apply["smoke_test"],
    }
    return report


__all__ = [
    "ServerReturnCorrectionError",
    "parse_competencia_argument",
    "run_server_return_correction",
]
