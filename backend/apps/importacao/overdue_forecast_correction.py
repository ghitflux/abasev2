from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.models import Parcela
from apps.importacao.models import ArquivoRetornoItem
from core.business_reference import resolve_business_reference


STATUS_DESCONTADO = {"1", "4"}
STATUS_NAO_DESCONTADO = {"2", "3", "5", "S"}


class OverdueForecastCorrectionError(Exception):
    pass


@dataclass(slots=True)
class ImportedItemRow:
    cpf_cnpj: str
    status_codigo: str
    arquivo_retorno_id: int | None


def parse_competencia_argument(value: str) -> date:
    try:
        year_str, month_str = value.split("-", 1)
        return date(int(year_str), int(month_str), 1)
    except (TypeError, ValueError) as exc:
        raise OverdueForecastCorrectionError(
            "Competência inválida. Use YYYY-MM."
        ) from exc


def iter_competencias(start: date, end: date):
    current = start.replace(day=1)
    final = end.replace(day=1)
    while current <= final:
        yield current
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _replace_competencia_note(existing: str, *, competencia_display: str, new_note: str) -> str:
    prefix = f"Saneamento previsão vencida {competencia_display}:"
    lines = [line.strip() for line in (existing or "").splitlines() if line.strip()]
    cleaned = [line for line in lines if not line.startswith(prefix)]
    if new_note not in cleaned:
        cleaned.append(new_note)
    return "\n".join(cleaned)


def _load_items_by_cpf(competencia: date) -> tuple[dict[str, ImportedItemRow], list[str]]:
    rows = (
        ArquivoRetornoItem.objects.filter(
            arquivo_retorno__competencia=competencia,
            arquivo_retorno__status="concluido",
        )
        .select_related("arquivo_retorno")
        .order_by("arquivo_retorno_id", "linha_numero", "id")
    )
    by_cpf: dict[str, ImportedItemRow] = {}
    conflicts: set[str] = set()

    for row in rows:
        cpf = _only_digits(row.cpf_cnpj)
        if len(cpf) != 11:
            continue
        status_codigo = (row.status_codigo or "").strip().upper()
        imported = ImportedItemRow(
            cpf_cnpj=cpf,
            status_codigo=status_codigo,
            arquivo_retorno_id=row.arquivo_retorno_id,
        )
        current = by_cpf.get(cpf)
        if current is None:
            by_cpf[cpf] = imported
            continue
        if current.status_codigo != imported.status_codigo:
            conflicts.add(cpf)

    for cpf in conflicts:
        by_cpf.pop(cpf, None)

    return by_cpf, sorted(conflicts)


def _classify_target_status(status_codigo: str | None) -> str:
    code = (status_codigo or "").strip().upper()
    if code in STATUS_DESCONTADO:
        return Parcela.Status.DESCONTADO
    return Parcela.Status.NAO_DESCONTADO


def _build_note(*, competencia: date, parcela: Parcela, imported: ImportedItemRow | None, target_status: str) -> str:
    competencia_display = competencia.strftime("%m/%Y")
    status_label = "descontada" if target_status == Parcela.Status.DESCONTADO else "não descontada"
    if imported is None:
        return (
            f"Saneamento previsão vencida {competencia_display}: "
            f"parcela vencida sem item importado para a competência; marcada como {status_label}."
        )
    return (
        f"Saneamento previsão vencida {competencia_display}: "
        f"ETIPI {imported.status_codigo or '?'} do ArquivoRetorno #{imported.arquivo_retorno_id} "
        f"marcou a parcela como {status_label}."
    )


def run_overdue_forecast_correction(
    *,
    competencia_inicial: date,
    competencia_final: date,
    apply: bool,
) -> dict[str, Any]:
    if competencia_final < competencia_inicial:
        raise OverdueForecastCorrectionError(
            "A competência final deve ser maior ou igual à inicial."
        )

    mes_atual = timezone.localdate().replace(day=1)
    competencias = [
        competencia
        for competencia in iter_competencias(competencia_inicial, competencia_final)
        if competencia < mes_atual
    ]
    if not competencias:
        raise OverdueForecastCorrectionError(
            "Nenhuma competência passada elegível para saneamento."
        )

    now = timezone.now()
    parcelas_to_update: list[Parcela] = []
    associados_nao_descontado: set[int] = set()
    report_rows: list[dict[str, Any]] = []
    summary = {
        "parcelas_avaliadas": 0,
        "parcelas_descontado": 0,
        "parcelas_nao_descontado": 0,
        "parcelas_sem_item": 0,
        "cpf_conflito_total": 0,
    }

    for competencia in competencias:
        items_by_cpf, conflicting_cpfs = _load_items_by_cpf(competencia)
        parcelas = list(
            Parcela.all_objects.filter(
                deleted_at__isnull=True,
                referencia_mes=competencia,
                status=Parcela.Status.EM_PREVISAO,
            )
            .select_related("associado", "ciclo__contrato")
            .order_by("ciclo__contrato__codigo", "numero", "id")
        )

        competencia_report = {
            "competencia": competencia.isoformat(),
            "parcelas_avaliadas": len(parcelas),
            "descontado": 0,
            "nao_descontado": 0,
            "sem_item": 0,
            "cpf_conflito_total": len(conflicting_cpfs),
            "samples": [],
        }
        summary["parcelas_avaliadas"] += len(parcelas)
        summary["cpf_conflito_total"] += len(conflicting_cpfs)

        for parcela in parcelas:
            cpf = _only_digits(parcela.associado.cpf_cnpj)
            imported = items_by_cpf.get(cpf)
            target_status = _classify_target_status(imported.status_codigo if imported else None)
            if imported is None:
                competencia_report["sem_item"] += 1
                summary["parcelas_sem_item"] += 1
            if target_status == Parcela.Status.DESCONTADO:
                competencia_report["descontado"] += 1
                summary["parcelas_descontado"] += 1
            else:
                competencia_report["nao_descontado"] += 1
                summary["parcelas_nao_descontado"] += 1
                associados_nao_descontado.add(parcela.associado_id)

            if len(competencia_report["samples"]) < 10:
                competencia_report["samples"].append(
                    {
                        "contrato": parcela.ciclo.contrato.codigo,
                        "cpf_cnpj": parcela.associado.cpf_cnpj,
                        "nome": parcela.associado.nome_completo,
                        "status_codigo": imported.status_codigo if imported else "",
                        "target_status": target_status,
                    }
                )

            if not apply:
                continue

            parcela.status = target_status
            parcela.data_pagamento = (
                parcela.data_vencimento if target_status == Parcela.Status.DESCONTADO else None
            )
            parcela.observacao = _replace_competencia_note(
                parcela.observacao,
                competencia_display=competencia.strftime("%m/%Y"),
                new_note=_build_note(
                    competencia=competencia,
                    parcela=parcela,
                    imported=imported,
                    target_status=target_status,
                ),
            )
            parcela.updated_at = now
            parcela.data_referencia_negocio = resolve_business_reference(parcela)
            parcelas_to_update.append(parcela)

        report_rows.append(competencia_report)

    if apply and parcelas_to_update:
        unique_updates = {parcela.id: parcela for parcela in parcelas_to_update}
        with transaction.atomic():
            Parcela.all_objects.bulk_update(
                list(unique_updates.values()),
                ["status", "data_pagamento", "observacao", "updated_at", "data_referencia_negocio"],
            )
            if associados_nao_descontado:
                Associado.objects.filter(pk__in=associados_nao_descontado).update(
                    status=Associado.Status.INADIMPLENTE,
                    updated_at=now,
                )

    return {
        "mode": "apply" if apply else "dry-run",
        "competencia_inicial": competencia_inicial.isoformat(),
        "competencia_final": competencia_final.isoformat(),
        "competencias_processadas": [competencia.isoformat() for competencia in competencias],
        "summary": summary,
        "results": report_rows,
    }
