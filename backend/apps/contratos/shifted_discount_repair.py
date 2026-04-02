from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.associados.models import Associado, only_digits
from apps.contratos.competencia import (
    propagate_competencia_status,
    sync_competencia_locks_for_references,
)
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.tesouraria.models import BaixaManual

PAID_PARCELA_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
}
PAID_STATUS_CODES = {"1", "4", "M"}
MANUAL_REGULARIZED_STATUS = "projection_only_regularized"
MANUAL_REVIEW_STATUS = "manual_review"
REPAIRABLE_STATUS = "repairable"
REPAIRED_STATUS = "repaired"


def parse_reference_month(value: str | date) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    return datetime.strptime(str(value).strip(), "%Y-%m").date().replace(day=1)


def default_shifted_discount_report_path(prefix: str = "repair_shifted_discount_references") -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / f"{prefix}_{timestamp}.json"
    )


def write_shifted_discount_report(payload: dict[str, Any], target: str | Path | None = None) -> Path:
    report_path = Path(target) if target else default_shifted_discount_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report_path


def _month_string(value: date) -> str:
    return value.strftime("%Y-%m")


def _normalize_payment_document(associado: Associado) -> str:
    return only_digits(associado.cpf_cnpj)


def _is_paid_pagamento(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip() in PAID_STATUS_CODES
        or pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
    )


def _serialize_parcela(parcela: Parcela | None) -> dict[str, Any] | None:
    if parcela is None:
        return None
    return {
        "id": parcela.id,
        "referencia_mes": _month_string(parcela.referencia_mes),
        "status": parcela.status,
        "data_pagamento": (
            parcela.data_pagamento.isoformat() if parcela.data_pagamento else None
        ),
        "ciclo_id": parcela.ciclo_id,
        "numero": parcela.numero,
    }


def _serialize_pagamento(pagamento: PagamentoMensalidade) -> dict[str, Any]:
    return {
        "id": pagamento.id,
        "referencia_month": _month_string(pagamento.referencia_month),
        "status_code": pagamento.status_code,
        "manual_status": pagamento.manual_status,
        "manual_paid_at": (
            pagamento.manual_paid_at.isoformat() if pagamento.manual_paid_at else None
        ),
        "valor": str(pagamento.valor) if pagamento.valor is not None else None,
    }


def _serialize_baixa(baixa: BaixaManual | None) -> dict[str, Any] | None:
    if baixa is None:
        return None
    return {
        "id": baixa.id,
        "parcela_id": baixa.parcela_id,
        "data_baixa": baixa.data_baixa.isoformat(),
        "valor_pago": str(baixa.valor_pago),
    }


def _serialize_retorno_item(item: ArquivoRetornoItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "competencia": item.competencia,
        "parcela_id": item.parcela_id,
        "resultado_processamento": item.resultado_processamento,
        "status_codigo": item.status_codigo,
    }


def _projection_snapshot(contrato: Contrato) -> dict[str, Any]:
    projection = build_contract_cycle_projection(contrato)
    unresolved = [
        item
        for item in projection.get("unpaid_months", [])
        if item.get("status") == Parcela.Status.NAO_DESCONTADO
    ]
    cycle_status_by_ref = {
        _month_string(parcela["referencia_mes"]): parcela["status"]
        for cycle in projection.get("cycles", [])
        for parcela in cycle.get("parcelas", [])
    }
    return {
        "possui_meses_nao_descontados": bool(projection.get("possui_meses_nao_descontados")),
        "meses_nao_descontados_count": int(projection.get("meses_nao_descontados_count") or 0),
        "unpaid_months": [
            {
                "referencia_mes": _month_string(item["referencia_mes"]),
                "status": item["status"],
            }
            for item in projection.get("unpaid_months", [])
        ],
        "unresolved_unpaid_refs": [
            _month_string(item["referencia_mes"]) for item in unresolved
        ],
        "cycle_status_by_ref": cycle_status_by_ref,
    }


def _format_competencia_like(current: str | None, reference: date) -> str:
    raw = str(current or "").strip()
    if "/" in raw:
        return reference.strftime("%m/%Y")
    return reference.strftime("%Y-%m")


def _query_pagamentos_for_reference(
    associado: Associado,
    reference: date,
) -> list[PagamentoMensalidade]:
    cpf = _normalize_payment_document(associado)
    return list(
        PagamentoMensalidade.all_objects.filter(
            deleted_at__isnull=True,
            referencia_month=reference,
        )
        .filter(Q(associado=associado) | Q(cpf_cnpj__in=[associado.cpf_cnpj, cpf]))
        .order_by("id")
    )


def _query_return_items_for_reference(
    associado: Associado,
    reference: date,
) -> list[ArquivoRetornoItem]:
    target_competencias = {
        reference.strftime("%Y-%m"),
        reference.strftime("%m/%Y"),
    }
    return list(
        ArquivoRetornoItem.all_objects.filter(
            deleted_at__isnull=True,
        )
        .filter(
            Q(associado=associado)
            | Q(cpf_cnpj__in=[associado.cpf_cnpj, _normalize_payment_document(associado)])
        )
        .filter(
            Q(parcela__referencia_mes=reference)
            | Q(competencia__in=target_competencias)
        )
        .select_related("parcela")
        .order_by("id")
    )


def _detect_primary_contract(
    associado: Associado,
    *,
    paid_ref: date,
    correct_ref: date,
) -> tuple[Contrato | None, list[str]]:
    matching: list[Contrato] = []
    for contrato in (
        associado.contratos.exclude(status=Contrato.Status.CANCELADO)
        .prefetch_related("ciclos__parcelas")
        .order_by("created_at", "id")
    ):
        referencias = {
            parcela.referencia_mes
            for ciclo in contrato.ciclos.all()
            for parcela in ciclo.parcelas.all()
            if parcela.deleted_at is None and parcela.status != Parcela.Status.CANCELADO
        }
        if paid_ref in referencias and correct_ref in referencias:
            matching.append(contrato)
    if not matching:
        return None, []
    if len(matching) > 1:
        return None, ["associated_has_multiple_contracts_for_reference_pair"]
    return matching[0], []


def _first_or_none(items: list[Any]) -> Any | None:
    return items[0] if items else None


def _pick_paid_date(
    *,
    pagamentos: list[PagamentoMensalidade],
    baixa: BaixaManual | None,
    parcela: Parcela,
) -> date:
    if baixa is not None:
        return baixa.data_baixa
    if parcela.data_pagamento is not None:
        return parcela.data_pagamento
    for pagamento in pagamentos:
        if pagamento.manual_paid_at is not None:
            return pagamento.manual_paid_at.date()
        if _is_paid_pagamento(pagamento):
            timestamp = pagamento.updated_at or pagamento.created_at
            return timestamp.date()
    return parcela.referencia_mes


def _classify_associado_case(
    associado: Associado,
    *,
    paid_ref: date,
    correct_ref: date,
) -> dict[str, Any] | None:
    contrato, contract_reasons = _detect_primary_contract(
        associado,
        paid_ref=paid_ref,
        correct_ref=correct_ref,
    )
    if contrato is None and not contract_reasons:
        return None

    result: dict[str, Any] = {
        "associado_id": associado.id,
        "cpf_cnpj": associado.cpf_cnpj,
        "nome_associado": associado.nome_completo,
        "contrato_id": getattr(contrato, "id", None),
        "contrato_codigo": getattr(contrato, "codigo", ""),
        "paid_ref": _month_string(paid_ref),
        "correct_ref": _month_string(correct_ref),
        "classification": MANUAL_REVIEW_STATUS if contract_reasons else "",
        "auto_repairable": False,
        "applied": False,
        "reasons": list(contract_reasons),
        "changes": {},
    }

    if contrato is None:
        return result

    parcelas_by_ref = {
        parcela.referencia_mes: parcela
        for ciclo in contrato.ciclos.all()
        for parcela in ciclo.parcelas.all()
        if parcela.deleted_at is None and parcela.status != Parcela.Status.CANCELADO
    }
    paid_parcela = parcelas_by_ref.get(paid_ref)
    correct_parcela = parcelas_by_ref.get(correct_ref)
    result["projection_before"] = _projection_snapshot(contrato)
    result["projection_regularized_only"] = bool(
        result["projection_before"]["unpaid_months"]
        and not result["projection_before"]["unresolved_unpaid_refs"]
    )

    if paid_parcela is None or correct_parcela is None:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("missing_materialized_parcelas_for_reference_pair")
        return result

    pagamentos_paid = _query_pagamentos_for_reference(associado, paid_ref)
    pagamentos_correct = _query_pagamentos_for_reference(associado, correct_ref)
    retorno_paid = _query_return_items_for_reference(associado, paid_ref)
    retorno_correct = _query_return_items_for_reference(associado, correct_ref)
    baixa_paid = _first_or_none(
        list(
            BaixaManual.all_objects.filter(
                deleted_at__isnull=True,
                parcela=paid_parcela,
            ).order_by("id")
        )
    )
    baixa_correct = _first_or_none(
        list(
            BaixaManual.all_objects.filter(
                deleted_at__isnull=True,
                parcela=correct_parcela,
            ).order_by("id")
        )
    )

    result["changes"] = {
        "paid_parcela": _serialize_parcela(paid_parcela),
        "correct_parcela": _serialize_parcela(correct_parcela),
        "pagamentos_paid": [_serialize_pagamento(item) for item in pagamentos_paid],
        "pagamentos_correct": [_serialize_pagamento(item) for item in pagamentos_correct],
        "baixa_paid": _serialize_baixa(baixa_paid),
        "baixa_correct": _serialize_baixa(baixa_correct),
        "retorno_items_paid": [_serialize_retorno_item(item) for item in retorno_paid],
        "retorno_items_correct": [
            _serialize_retorno_item(item) for item in retorno_correct
        ],
    }

    paid_evidence = (
        bool(pagamentos_paid)
        or baixa_paid is not None
        or paid_parcela.status in PAID_PARCELA_STATUSES
    )
    if not paid_evidence:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("paid_reference_has_no_paid_evidence")
        return result

    if len(pagamentos_paid) > 1:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("paid_reference_has_multiple_payment_records")
        return result

    if len(retorno_paid) > 1:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("paid_reference_has_multiple_return_items")
        return result

    if pagamentos_correct:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("correct_reference_already_has_financial_record")
        return result

    if baixa_correct is not None:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("correct_reference_already_has_baixa_manual")
        return result

    if retorno_correct:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("correct_reference_already_has_return_item")
        return result

    if baixa_paid is not None and pagamentos_paid:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("paid_reference_has_manual_and_import_payment_evidence")
        return result

    if correct_parcela.status in PAID_PARCELA_STATUSES:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("correct_reference_parcela_already_paid")
        return result

    result["classification"] = REPAIRABLE_STATUS
    result["auto_repairable"] = True
    result["repair_context"] = {
        "paid_parcela_id": paid_parcela.id,
        "correct_parcela_id": correct_parcela.id,
        "pagamento_ids": [item.id for item in pagamentos_paid],
        "retorno_item_ids": [item.id for item in retorno_paid],
        "baixa_id": getattr(baixa_paid, "id", None),
    }
    return result


def _apply_case_repair(result: dict[str, Any], *, paid_ref: date, correct_ref: date) -> dict[str, Any]:
    associado = Associado.objects.get(pk=result["associado_id"])
    contrato = (
        Contrato.objects.select_related("associado")
        .prefetch_related("ciclos__parcelas")
        .get(pk=result["contrato_id"])
    )
    context = result.get("repair_context") or {}

    with transaction.atomic():
        paid_parcela = Parcela.all_objects.select_for_update().get(
            pk=context["paid_parcela_id"]
        )
        correct_parcela = Parcela.all_objects.select_for_update().get(
            pk=context["correct_parcela_id"]
        )
        pagamentos = list(
            PagamentoMensalidade.all_objects.select_for_update().filter(
                pk__in=context["pagamento_ids"]
            )
        )
        retorno_items = list(
            ArquivoRetornoItem.all_objects.select_for_update().filter(
                pk__in=context["retorno_item_ids"]
            )
        )
        baixa = None
        if context.get("baixa_id"):
            baixa = BaixaManual.all_objects.select_for_update().get(pk=context["baixa_id"])

        paid_date = _pick_paid_date(
            pagamentos=pagamentos,
            baixa=baixa,
            parcela=paid_parcela,
        )
        target_status = (
            paid_parcela.status
            if paid_parcela.status in PAID_PARCELA_STATUSES
            else Parcela.Status.DESCONTADO
        )

        for pagamento in pagamentos:
            pagamento.referencia_month = correct_ref
            pagamento.save(update_fields=["referencia_month", "updated_at"])

        if baixa is not None:
            baixa.parcela = correct_parcela
            baixa.save(update_fields=["parcela", "updated_at"])

        for item in retorno_items:
            item.parcela = correct_parcela
            item.competencia = _format_competencia_like(item.competencia, correct_ref)
            item.associado = associado
            item.cpf_cnpj = associado.cpf_cnpj
            item.save(
                update_fields=[
                    "parcela",
                    "competencia",
                    "associado",
                    "cpf_cnpj",
                    "updated_at",
                ]
            )

        correct_parcela.status = target_status
        correct_parcela.data_pagamento = paid_date
        correct_parcela.save(
            update_fields=["status", "data_pagamento", "updated_at"]
        )
        paid_parcela.status = Parcela.Status.EM_PREVISAO
        paid_parcela.data_pagamento = None
        paid_parcela.save(
            update_fields=["status", "data_pagamento", "updated_at"]
        )

        propagate_competencia_status(correct_parcela)
        propagate_competencia_status(paid_parcela)
        sync_competencia_locks_for_references(
            associado_id=associado.id,
            referencias=[correct_ref, paid_ref],
        )

        reloaded_contract = (
            Contrato.objects.select_related("associado")
            .prefetch_related("ciclos__parcelas")
            .get(pk=contrato.pk)
        )
        projection_after = _projection_snapshot(reloaded_contract)
        if _month_string(correct_ref) in projection_after["unresolved_unpaid_refs"]:
            raise ValueError("correct_reference_still_marked_as_unpaid_after_repair")
        if projection_after["cycle_status_by_ref"].get(_month_string(correct_ref)) not in {
            Parcela.Status.DESCONTADO,
            Parcela.Status.LIQUIDADA,
        }:
            raise ValueError("correct_reference_not_materialized_as_paid_after_repair")
        if projection_after["cycle_status_by_ref"].get(_month_string(paid_ref)) in {
            Parcela.Status.DESCONTADO,
            Parcela.Status.LIQUIDADA,
        }:
            raise ValueError("paid_reference_remained_paid_after_repair")

    refreshed = _classify_associado_case(
        associado,
        paid_ref=paid_ref,
        correct_ref=correct_ref,
    )
    reloaded_contract = (
        Contrato.objects.select_related("associado")
        .prefetch_related("ciclos__parcelas")
        .get(pk=contrato.pk)
    )
    result["projection_after"] = _projection_snapshot(reloaded_contract)
    result["classification"] = REPAIRED_STATUS
    result["applied"] = True
    result["post_repair_auto_repairable"] = bool(refreshed and refreshed.get("auto_repairable"))
    return result


def audit_and_repair_shifted_discount_references(
    *,
    paid_ref: date,
    correct_ref: date,
    cpf_cnpj: str | None = None,
    associado_id: int | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    queryset = Associado.objects.all().order_by("nome_completo", "id")
    if associado_id is not None:
        queryset = queryset.filter(id=associado_id)
    if cpf_cnpj:
        queryset = queryset.filter(cpf_cnpj=only_digits(cpf_cnpj))

    scanned = 0
    results: list[dict[str, Any]] = []
    for associado in queryset:
        scanned += 1
        result = _classify_associado_case(
            associado,
            paid_ref=paid_ref,
            correct_ref=correct_ref,
        )
        if result is None:
            for contrato in associado.contratos.exclude(status=Contrato.Status.CANCELADO):
                projection = _projection_snapshot(contrato)
                if projection["unpaid_months"] and not projection["unresolved_unpaid_refs"]:
                    results.append(
                        {
                            "associado_id": associado.id,
                            "cpf_cnpj": associado.cpf_cnpj,
                            "nome_associado": associado.nome_completo,
                            "contrato_id": contrato.id,
                            "contrato_codigo": contrato.codigo,
                            "paid_ref": _month_string(paid_ref),
                            "correct_ref": _month_string(correct_ref),
                            "classification": MANUAL_REGULARIZED_STATUS,
                            "auto_repairable": False,
                            "applied": False,
                            "reasons": ["projection_contains_only_regularized_months"],
                            "projection_before": projection,
                            "changes": {},
                        }
                    )
            continue

        if execute and result.get("auto_repairable"):
            try:
                result = _apply_case_repair(
                    result,
                    paid_ref=paid_ref,
                    correct_ref=correct_ref,
                )
            except Exception as exc:
                result["classification"] = MANUAL_REVIEW_STATUS
                result["auto_repairable"] = False
                result["applied"] = False
                result.setdefault("reasons", []).append(str(exc))
        results.append(result)

    counter = Counter(item["classification"] for item in results)
    return {
        "generated_at": timezone.now().isoformat(),
        "paid_ref": _month_string(paid_ref),
        "correct_ref": _month_string(correct_ref),
        "mode": "execute" if execute else "dry-run",
        "summary": {
            "scanned_associados": scanned,
            "results": len(results),
            "repairable": counter.get(REPAIRABLE_STATUS, 0),
            "repaired": counter.get(REPAIRED_STATUS, 0),
            "manual_review": counter.get(MANUAL_REVIEW_STATUS, 0),
            "projection_only_regularized": counter.get(MANUAL_REGULARIZED_STATUS, 0),
        },
        "results": results,
    }
