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
from apps.contratos.cycle_projection import PROJECTION_STATUS_QUITADA, build_contract_cycle_projection
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.tesouraria.models import BaixaManual, DevolucaoAssociado, LiquidacaoContratoItem

PAID_PARCELA_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
}
PAID_PROJECTION_STATUSES = {
    *PAID_PARCELA_STATUSES,
    PROJECTION_STATUS_QUITADA,
}
MANUAL_REVIEW_STATUS = "manual_review"
REPAIRABLE_STATUS = "repairable"
REVERTED_STATUS = "reverted_to_forecast"


def parse_reference_month(value: str | date) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    return datetime.strptime(str(value).strip(), "%Y-%m").date().replace(day=1)


def default_revert_report_path(
    prefix: str = "revert_discounted_reference_to_forecast",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


def write_revert_report(
    payload: dict[str, Any],
    target: str | Path | None = None,
) -> Path:
    report_path = Path(target) if target else default_revert_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report_path


def _month_string(value: date) -> str:
    return value.strftime("%Y-%m")


def _append_note(current: str | None, message: str) -> str:
    current_text = (current or "").strip()
    if not current_text:
        return message
    if message in current_text:
        return current_text
    return f"{current_text}\n{message}"


def _normalize_payment_document(associado: Associado) -> str:
    return only_digits(associado.cpf_cnpj)


def _serialize_parcela(parcela: Parcela | None) -> dict[str, Any] | None:
    if parcela is None:
        return None
    return {
        "id": parcela.id,
        "referencia_mes": _month_string(parcela.referencia_mes),
        "status": parcela.status,
        "data_pagamento": parcela.data_pagamento.isoformat() if parcela.data_pagamento else None,
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


def _serialize_retorno_item(item: ArquivoRetornoItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "competencia": item.competencia,
        "parcela_id": item.parcela_id,
        "status_desconto": item.status_desconto,
        "resultado_processamento": item.resultado_processamento,
        "gerou_encerramento": item.gerou_encerramento,
        "gerou_novo_ciclo": item.gerou_novo_ciclo,
    }


def _serialize_baixa(baixa: BaixaManual) -> dict[str, Any]:
    return {
        "id": baixa.id,
        "parcela_id": baixa.parcela_id,
        "data_baixa": baixa.data_baixa.isoformat(),
        "valor_pago": str(baixa.valor_pago),
    }


def _projection_snapshot(contrato: Contrato, *, target_ref: date) -> dict[str, Any]:
    projection = build_contract_cycle_projection(contrato)
    target_ref_status: str | None = None
    target_ref_cycle_number: int | None = None
    target_ref_cycle_start: str | None = None
    target_ref_in_projection = False

    for cycle in sorted(projection.get("cycles", []), key=lambda item: item["numero"]):
        for parcela in cycle.get("parcelas", []):
            if parcela.get("referencia_mes") != target_ref:
                continue
            target_ref_status = str(parcela.get("status") or "")
            target_ref_cycle_number = int(cycle["numero"])
            data_inicio = cycle.get("data_inicio")
            target_ref_cycle_start = data_inicio.isoformat() if data_inicio else None
            target_ref_in_projection = True
            break
        if target_ref_in_projection:
            break

    return {
        "target_ref": _month_string(target_ref),
        "target_ref_in_projection": target_ref_in_projection,
        "target_ref_status": target_ref_status,
        "target_ref_cycle_number": target_ref_cycle_number,
        "target_ref_cycle_start": target_ref_cycle_start,
        "target_ref_counts_as_paid": target_ref_status in PAID_PROJECTION_STATUSES,
        "meses_nao_descontados_count": int(projection.get("meses_nao_descontados_count") or 0),
        "possui_meses_nao_descontados": bool(projection.get("possui_meses_nao_descontados")),
        "unpaid_months": [
            {
                "referencia_mes": _month_string(item["referencia_mes"]),
                "status": item["status"],
            }
            for item in projection.get("unpaid_months", [])
        ],
    }


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
        .exclude(manual_status=PagamentoMensalidade.ManualStatus.CANCELADO)
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
        .exclude(status_desconto=ArquivoRetornoItem.StatusDesconto.CANCELADO)
        .order_by("id")
    )


def _query_baixas_for_reference(
    associado: Associado,
    reference: date,
) -> list[BaixaManual]:
    return list(
        BaixaManual.all_objects.filter(
            deleted_at__isnull=True,
            parcela__associado=associado,
            parcela__referencia_mes=reference,
        )
        .select_related("parcela")
        .order_by("id")
    )


def _matching_contracts_for_reference(
    associado: Associado,
    *,
    target_ref: date,
) -> tuple[list[Contrato], dict[int, dict[str, Any]]]:
    snapshots: dict[int, dict[str, Any]] = {}
    matches: list[Contrato] = []
    contracts = list(
        associado.contratos.exclude(status=Contrato.Status.CANCELADO)
        .prefetch_related("ciclos__parcelas")
        .order_by("created_at", "id")
    )
    for contrato in contracts:
        has_materialized_ref = any(
            parcela.deleted_at is None
            and parcela.status != Parcela.Status.CANCELADO
            and parcela.referencia_mes == target_ref
            for ciclo in contrato.ciclos.all()
            for parcela in ciclo.parcelas.all()
        )
        snapshot = _projection_snapshot(contrato, target_ref=target_ref)
        snapshots[contrato.id] = snapshot
        if has_materialized_ref or snapshot["target_ref_in_projection"]:
            matches.append(contrato)
    return matches, snapshots


def _classify_associado_case(
    associado: Associado,
    *,
    target_ref: date,
) -> dict[str, Any] | None:
    pagamentos = _query_pagamentos_for_reference(associado, target_ref)
    retorno_items = _query_return_items_for_reference(associado, target_ref)
    baixas = _query_baixas_for_reference(associado, target_ref)
    matching_contracts, snapshots = _matching_contracts_for_reference(
        associado,
        target_ref=target_ref,
    )

    evidence_exists = bool(pagamentos or retorno_items or baixas)
    projection_paid_contracts = [
        contrato
        for contrato in matching_contracts
        if snapshots.get(contrato.id, {}).get("target_ref_counts_as_paid")
    ]
    if not evidence_exists and not projection_paid_contracts:
        return None

    result: dict[str, Any] = {
        "associado_id": associado.id,
        "cpf_cnpj": associado.cpf_cnpj,
        "nome_associado": associado.nome_completo,
        "target_ref": _month_string(target_ref),
        "classification": "",
        "auto_repairable": False,
        "applied": False,
        "contracts_scanned": len(snapshots),
        "reasons": [],
        "changes": {
            "pagamentos": [_serialize_pagamento(item) for item in pagamentos],
            "retorno_items": [_serialize_retorno_item(item) for item in retorno_items],
            "baixas": [_serialize_baixa(item) for item in baixas],
        },
    }

    if not matching_contracts:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("no_contract_contains_target_reference")
        return result

    if len(matching_contracts) > 1:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("associated_has_multiple_contracts_for_target_reference")
        result["matching_contracts"] = [
            {
                "contrato_id": contrato.id,
                "contrato_codigo": contrato.codigo,
                "projection": snapshots.get(contrato.id),
            }
            for contrato in matching_contracts
        ]
        return result

    contrato = matching_contracts[0]
    result["contrato_id"] = contrato.id
    result["contrato_codigo"] = contrato.codigo
    result["projection_before"] = snapshots[contrato.id]

    target_parcelas = list(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            referencia_mes=target_ref,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("ciclo__numero", "numero", "id")
    )
    if len(target_parcelas) > 1:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("contract_has_multiple_materialized_target_parcelas")
        return result

    target_parcela = target_parcelas[0] if target_parcelas else None
    result["changes"]["target_parcela"] = _serialize_parcela(target_parcela)

    has_paid_materialized_parcela = bool(
        target_parcela and target_parcela.status in PAID_PARCELA_STATUSES
    )
    projection_paid = bool(result["projection_before"]["target_ref_counts_as_paid"])
    if not evidence_exists and not has_paid_materialized_parcela and not projection_paid:
        return None

    liquidacao_items_count = LiquidacaoContratoItem.objects.filter(
        deleted_at__isnull=True,
        liquidacao__revertida_em__isnull=True,
        liquidacao__deleted_at__isnull=True,
        parcela__ciclo__contrato=contrato,
        referencia_mes=target_ref,
    ).count()
    if liquidacao_items_count > 0:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("active_liquidation_exists_for_target_reference")
        return result

    devolucoes_count = DevolucaoAssociado.objects.filter(
        deleted_at__isnull=True,
        contrato=contrato,
        competencia_referencia=target_ref,
        revertida_em__isnull=True,
    ).count()
    if devolucoes_count > 0:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("active_devolucao_exists_for_target_reference")
        return result

    if target_parcela is None and not result["projection_before"]["target_ref_in_projection"]:
        result["classification"] = MANUAL_REVIEW_STATUS
        result["reasons"].append("target_reference_not_present_in_contract_projection")
        return result

    result["classification"] = REPAIRABLE_STATUS
    result["auto_repairable"] = True
    result["repair_context"] = {
        "contrato_id": contrato.id,
        "target_parcela_id": getattr(target_parcela, "id", None),
        "pagamento_ids": [item.id for item in pagamentos],
        "retorno_item_ids": [item.id for item in retorno_items],
        "baixa_ids": [item.id for item in baixas],
        "target_ref_was_materialized": target_parcela is not None,
        "target_ref_was_in_projection": bool(
            result["projection_before"]["target_ref_in_projection"]
        ),
    }
    return result


def _apply_revert_case(result: dict[str, Any], *, target_ref: date) -> dict[str, Any]:
    associado = Associado.objects.get(pk=result["associado_id"])
    context = result["repair_context"]
    contrato = (
        Contrato.objects.select_related("associado")
        .prefetch_related("ciclos__parcelas")
        .get(pk=context["contrato_id"])
    )

    note = (
        f"Competência {_month_string(target_ref)} revertida para previsão em "
        f"{timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')}."
    )

    with transaction.atomic():
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
        baixas = list(
            BaixaManual.all_objects.select_for_update().filter(
                pk__in=context["baixa_ids"]
            )
        )
        target_parcela = None
        if context.get("target_parcela_id"):
            target_parcela = Parcela.all_objects.select_for_update().get(
                pk=context["target_parcela_id"]
            )

        for pagamento in pagamentos:
            pagamento.manual_status = PagamentoMensalidade.ManualStatus.CANCELADO
            pagamento.save(update_fields=["manual_status", "updated_at"])

        for item in retorno_items:
            item.status_desconto = ArquivoRetornoItem.StatusDesconto.CANCELADO
            item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.ERRO
            item.status_descricao = "Revertido para previsão"
            item.motivo_rejeicao = _append_note(item.motivo_rejeicao, note)
            item.observacao = _append_note(item.observacao, note)
            item.gerou_encerramento = False
            item.gerou_novo_ciclo = False
            item.parcela = None
            item.save(
                update_fields=[
                    "status_desconto",
                    "resultado_processamento",
                    "status_descricao",
                    "motivo_rejeicao",
                    "observacao",
                    "gerou_encerramento",
                    "gerou_novo_ciclo",
                    "parcela",
                    "updated_at",
                ]
            )

        for baixa in baixas:
            baixa.delete()

        if target_parcela is not None:
            target_parcela.status = Parcela.Status.EM_PREVISAO
            target_parcela.data_pagamento = None
            target_parcela.observacao = _append_note(target_parcela.observacao, note)
            target_parcela.save(
                update_fields=["status", "data_pagamento", "observacao", "updated_at"]
            )
            propagate_competencia_status(target_parcela)

        sync_competencia_locks_for_references(
            associado_id=associado.id,
            referencias=[target_ref],
        )
        fresh_contract_for_rebuild = Contrato.objects.select_related("associado").get(
            pk=contrato.pk
        )
        rebuild_report = rebuild_contract_cycle_state(
            fresh_contract_for_rebuild,
            execute=True,
        ).as_dict()

        reloaded_contract = (
            Contrato.objects.select_related("associado")
            .prefetch_related("ciclos__parcelas")
            .get(pk=contrato.pk)
        )
        projection_after = _projection_snapshot(reloaded_contract, target_ref=target_ref)
        if projection_after["target_ref_counts_as_paid"]:
            raise ValueError("target_reference_still_marked_as_paid_after_rebuild")

    result["projection_after"] = projection_after
    result["changes"]["rebuild_report"] = rebuild_report
    result["classification"] = REVERTED_STATUS
    result["applied"] = True
    result["evidence_changes"] = {
        "pagamentos": len(context["pagamento_ids"]),
        "retorno_items": len(context["retorno_item_ids"]),
        "baixas": len(context["baixa_ids"]),
        "parcelas": 1 if context.get("target_parcela_id") else 0,
        "rebuilds": 1,
    }
    return result


def audit_and_revert_discounted_reference_to_forecast(
    *,
    target_ref: date,
    cpf_cnpj: str | None = None,
    associado_id: int | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    queryset = Associado.objects.order_by("nome_completo", "id")
    if associado_id is not None:
        queryset = queryset.filter(id=associado_id)
    if cpf_cnpj:
        queryset = queryset.filter(cpf_cnpj=only_digits(cpf_cnpj))

    scanned_associados = 0
    scanned_contracts = 0
    results: list[dict[str, Any]] = []

    for associado in queryset:
        scanned_associados += 1
        scanned_contracts += associado.contratos.exclude(
            status=Contrato.Status.CANCELADO
        ).count()
        result = _classify_associado_case(associado, target_ref=target_ref)
        if result is None:
            continue
        if execute and result.get("auto_repairable"):
            try:
                result = _apply_revert_case(result, target_ref=target_ref)
            except Exception as exc:
                result["classification"] = MANUAL_REVIEW_STATUS
                result["auto_repairable"] = False
                result["applied"] = False
                result.setdefault("reasons", []).append(str(exc))
        results.append(result)

    counter = Counter(item["classification"] for item in results)
    evidence_changes = Counter()
    for item in results:
        for key, value in (item.get("evidence_changes") or {}).items():
            evidence_changes[key] += int(value)

    return {
        "generated_at": timezone.now().isoformat(),
        "target_ref": _month_string(target_ref),
        "mode": "execute" if execute else "dry-run",
        "summary": {
            "scanned_associados": scanned_associados,
            "scanned_contracts": scanned_contracts,
            "results": len(results),
            "repairable": counter.get(REPAIRABLE_STATUS, 0),
            "reverted": counter.get(REVERTED_STATUS, 0),
            "manual_review": counter.get(MANUAL_REVIEW_STATUS, 0),
            "evidence_changes": dict(evidence_changes),
        },
        "results": results,
    }
