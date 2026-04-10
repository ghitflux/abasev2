from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone

from apps.associados.models import Associado, only_digits
from apps.importacao.models import ArquivoRetornoItem
from apps.importacao.small_value_return_materialization import (
    materialize_small_value_items_for_cpf,
    resolve_default_small_value_agent,
)
from apps.refinanciamento.models import Refinanciamento

from .canonicalization import resolve_operational_contract_for_associado
from .cycle_projection import build_contract_cycle_projection
from .cycle_rebuild import rebuild_contract_cycle_state, relink_contract_documents
from .cycle_timeline import add_months, get_contract_cycle_size
from .models import Ciclo, Contrato, Parcela
from .pre_october_cycle_repair import repair_contract_pre_october_cycles
from .small_value_rules import (
    blocked_small_value_cycle_status,
    is_return_imported_small_value_contract,
)

APRIL_TARGET_REFERENCE = date(2026, 4, 1)
DEFAULT_FLOOR_REFERENCE = date(2025, 10, 1)
RESOLVED_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
    "quitada",
}


@dataclass(frozen=True)
class AprilRenewalRow:
    index: int
    cpf_original: str
    cpf_normalized: str
    nome: str
    mensalidade: str
    matricula: str
    fevereiro: str
    marco: str
    abril: str


def default_april_repair_report_path(prefix: str = "repair_april_renewal_cohort") -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return Path(settings.BASE_DIR) / "media" / "relatorios" / f"{prefix}_{timestamp}.json"


def write_april_repair_report(
    payload: dict[str, Any],
    target: str | Path | None = None,
) -> Path:
    report_path = Path(target) if target else default_april_repair_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report_path


def load_april_rows(csv_path: str | Path) -> list[AprilRenewalRow]:
    path = Path(csv_path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    parsed: list[AprilRenewalRow] = []
    for index, row in enumerate(rows, start=1):
        cpf_original = str(row.get("CPF") or "").strip()
        parsed.append(
            AprilRenewalRow(
                index=index,
                cpf_original=cpf_original,
                cpf_normalized=only_digits(cpf_original).zfill(11),
                nome=str(row.get("NOME") or "").strip(),
                mensalidade=str(row.get("MENSALIDADE") or "").strip(),
                matricula=str(row.get("MATRICULA") or "").strip(),
                fevereiro=str(row.get("fev./26") or "").strip(),
                marco=str(row.get("mar./26") or "").strip(),
                abril=str(row.get("abr./26") or "").strip(),
            )
        )
    return parsed


def _active_cycle_parcelas(ciclo: Ciclo) -> list[Parcela]:
    return list(
        Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "numero", "id")
    )


def _find_incomplete_cycle_one_contract_ids() -> set[int]:
    contract_ids: set[int] = set()
    queryset = (
        Contrato.objects.select_related("associado")
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("id")
    )
    for contrato in queryset.iterator():
        ciclos = list(
            Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
        )
        if len(ciclos) < 2:
            continue
        ciclo_1 = next((ciclo for ciclo in ciclos if ciclo.numero == 1), None)
        if ciclo_1 is None or ciclo_1.status != Ciclo.Status.CICLO_RENOVADO:
            continue
        expected = get_contract_cycle_size(contrato)
        if len(_active_cycle_parcelas(ciclo_1)) < expected:
            contract_ids.add(contrato.id)
    return contract_ids


def _last_cycle_snapshot(contrato: Contrato) -> dict[str, Any]:
    ciclos = list(
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
    )
    if not ciclos:
        return {
            "cycle_number": None,
            "cycle_status": "",
            "references": [],
            "april_status": "",
        }
    ciclo = ciclos[-1]
    parcelas = _active_cycle_parcelas(ciclo)
    april = next((parcela for parcela in parcelas if parcela.referencia_mes == APRIL_TARGET_REFERENCE), None)
    return {
        "cycle_number": ciclo.numero,
        "cycle_status": ciclo.status,
        "references": [parcela.referencia_mes.isoformat() for parcela in parcelas],
        "april_status": april.status if april is not None else "",
    }


def _force_latest_cycle_apto(contrato: Contrato) -> None:
    latest_cycle = (
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True)
        .order_by("-numero", "-id")
        .first()
    )
    if latest_cycle is None:
        return
    if latest_cycle.status == Ciclo.Status.CICLO_RENOVADO:
        return
    desired_status = Ciclo.Status.APTO_A_RENOVAR
    if is_return_imported_small_value_contract(contrato):
        projection = build_contract_cycle_projection(contrato)
        desired_status = blocked_small_value_cycle_status(
            has_unpaid_months=bool(projection.get("unpaid_months"))
        )
    if latest_cycle.status != desired_status:
        latest_cycle.status = desired_status
        latest_cycle.save(update_fields=["status", "updated_at"])


def _set_small_value_renewal_override(contrato: Contrato) -> bool:
    if contrato.allow_small_value_renewal:
        return False
    contrato.allow_small_value_renewal = True
    contrato.save(update_fields=["allow_small_value_renewal", "updated_at"])
    if hasattr(contrato, "_is_return_imported_small_value_contract"):
        delattr(contrato, "_is_return_imported_small_value_contract")
    return True


def _small_value_items_for_cpf(cpf: str) -> list[ArquivoRetornoItem]:
    return list(
        ArquivoRetornoItem.objects.filter(
            deleted_at__isnull=True,
            cpf_cnpj=cpf,
            valor_descontado__in=["30.00", "50.00"],
        )
        .select_related("arquivo_retorno", "associado", "parcela", "parcela__ciclo", "parcela__ciclo__contrato")
        .order_by(
            "arquivo_retorno__competencia",
            "arquivo_retorno__processado_em",
            "linha_numero",
            "id",
        )
    )


def _materialize_missing_small_value_april_rows(
    rows: list[AprilRenewalRow],
) -> dict[str, Any]:
    default_agent = resolve_default_small_value_agent()
    payload: dict[str, Any] = {
        "cpfs_materialized": [],
        "contracts_created": 0,
        "associados_created": 0,
        "items_linked": 0,
        "errors": [],
    }
    for row in rows:
        associado = Associado.objects.filter(cpf_cnpj=row.cpf_normalized).first()
        contrato = (
            resolve_operational_contract_for_associado(associado)
            if associado is not None
            else None
        )
        if contrato is not None:
            continue
        items = _small_value_items_for_cpf(row.cpf_normalized)
        if not items:
            payload["errors"].append(
                {
                    "cpf": row.cpf_normalized,
                    "nome": row.nome,
                    "reason": "sem_itens_retorno_30_50",
                }
            )
            continue
        result = materialize_small_value_items_for_cpf(
            cpf_cnpj=row.cpf_normalized,
            items=items,
            default_agent=default_agent,
            apply=True,
        )
        payload["cpfs_materialized"].append(row.cpf_normalized)
        payload["contracts_created"] += int(result.contract_created)
        payload["associados_created"] += int(result.associated_created)
        payload["items_linked"] += int(result.stats.get("items_linked", 0))
    return payload


def _enable_small_value_override_for_april_rows(
    rows: list[AprilRenewalRow],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contracts_overridden": 0,
        "cpfs_overridden": [],
    }
    for row in rows:
        associado = Associado.objects.filter(cpf_cnpj=row.cpf_normalized).first()
        contrato = (
            resolve_operational_contract_for_associado(associado)
            if associado is not None
            else None
        )
        if contrato is None:
            continue
        if not is_return_imported_small_value_contract(contrato):
            continue
        if _set_small_value_renewal_override(contrato):
            payload["contracts_overridden"] += 1
            payload["cpfs_overridden"].append(row.cpf_normalized)
    return payload


def _regularized_target_refs(contrato: Contrato) -> list[date]:
    cycle_size = get_contract_cycle_size(contrato)
    start = add_months(APRIL_TARGET_REFERENCE, -(cycle_size - 1))
    refs: list[date] = []
    current = start
    while current < APRIL_TARGET_REFERENCE:
        refs.append(current)
        current = add_months(current, 1)
    return refs


def _materialize_remaining_cycle_one_regularized_rows(contrato: Contrato) -> bool:
    cycle_size = get_contract_cycle_size(contrato)
    ciclo_1 = (
        Ciclo.objects.filter(
            contrato=contrato,
            numero=1,
            deleted_at__isnull=True,
        )
        .order_by("id")
        .first()
    )
    if ciclo_1 is None or ciclo_1.status != Ciclo.Status.CICLO_RENOVADO:
        return False

    active_cycle_rows = _active_cycle_parcelas(ciclo_1)
    if len(active_cycle_rows) >= cycle_size:
        return False

    latest_cycle = (
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True)
        .order_by("-numero", "-id")
        .first()
    )
    if latest_cycle is None:
        return False

    projection = build_contract_cycle_projection(contrato)
    unpaid_rows = sorted(
        projection.get("unpaid_months") or [],
        key=lambda item: item["referencia_mes"],
    )
    existing_refs = {parcela.referencia_mes for parcela in active_cycle_rows}
    candidates = [
        row
        for row in unpaid_rows
        if row.get("status") == "quitada"
        and row["referencia_mes"] < latest_cycle.data_inicio
        and row["referencia_mes"] not in existing_refs
    ]
    if not candidates:
        return False

    changed = False
    used_numbers = set(
        Parcela.all_objects.filter(ciclo=ciclo_1).values_list("numero", flat=True)
    )

    def next_free_numero() -> int:
        numero = 1
        while numero in used_numbers:
            numero += 1
        used_numbers.add(numero)
        return numero

    for row in candidates[: max(cycle_size - len(active_cycle_rows), 0)]:
        existing = (
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                referencia_mes=row["referencia_mes"],
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("deleted_at", "id")
            .first()
        )
        defaults = {
            "ciclo": ciclo_1,
            "associado": contrato.associado,
            "numero": next_free_numero(),
            "referencia_mes": row["referencia_mes"],
            "valor": row.get("valor") or contrato.valor_mensalidade,
            "data_vencimento": row["referencia_mes"],
            "status": Parcela.Status.LIQUIDADA,
            "layout_bucket": Parcela.LayoutBucket.CYCLE,
            "data_pagamento": row.get("data_pagamento") or row["referencia_mes"],
            "observacao": (
                "Competência quitada manualmente e incorporada ao ciclo 1 "
                "na correção do lote oficial de renovação parcial de abril de 2026."
            ),
            "deleted_at": None,
        }
        if existing is None:
            Parcela.all_objects.create(**defaults)
        else:
            changed_fields: list[str] = []
            for field, value in defaults.items():
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed_fields.append(field)
            if changed_fields:
                existing.save(update_fields=[*changed_fields, "updated_at"])
        changed = True

    if not changed:
        return False

    ciclo_1_rows = _active_cycle_parcelas(ciclo_1)
    ciclo_1.data_inicio = min(parcela.referencia_mes for parcela in ciclo_1_rows)
    ciclo_1.data_fim = max(parcela.referencia_mes for parcela in ciclo_1_rows)
    ciclo_1.valor_total = sum((parcela.valor for parcela in ciclo_1_rows), start=0)
    ciclo_1.status = Ciclo.Status.CICLO_RENOVADO
    ciclo_1.save(update_fields=["data_inicio", "data_fim", "valor_total", "status", "updated_at"])

    latest_cycle.status = (
        blocked_small_value_cycle_status(
            has_unpaid_months=bool(build_contract_cycle_projection(contrato).get("unpaid_months"))
        )
        if is_return_imported_small_value_contract(contrato)
        else Ciclo.Status.APTO_A_RENOVAR
    )
    latest_cycle.save(update_fields=["status", "updated_at"])

    if not contrato.admin_manual_layout_enabled:
        contrato.admin_manual_layout_enabled = True
        contrato.admin_manual_layout_updated_at = timezone.now()
        contrato.save(
            update_fields=[
                "admin_manual_layout_enabled",
                "admin_manual_layout_updated_at",
                "updated_at",
            ]
        )

    return True


def _materialize_manual_april_target_cycle(contrato: Contrato) -> bool:
    target_refs = [*_regularized_target_refs(contrato), APRIL_TARGET_REFERENCE]
    if not target_refs:
        return False

    ciclos = list(
        Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero", "id")
    )
    latest_cycle = ciclos[-1] if ciclos else None
    if latest_cycle is None:
        latest_cycle = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=target_refs[0],
            data_fim=target_refs[-1],
            status=(
                blocked_small_value_cycle_status(
                    has_unpaid_months=bool(build_contract_cycle_projection(contrato).get("unpaid_months"))
                )
                if is_return_imported_small_value_contract(contrato)
                else Ciclo.Status.APTO_A_RENOVAR
            ),
            valor_total=0,
        )

    projection = build_contract_cycle_projection(contrato)
    source_rows: dict[date, dict[str, Any]] = {}
    for row in projection.get("movimentos_financeiros_avulsos") or []:
        referencia = row.get("referencia_mes")
        if referencia in target_refs:
            source_rows[referencia] = row
    for row in projection.get("unpaid_months") or []:
        referencia = row.get("referencia_mes")
        if referencia in target_refs and referencia not in source_rows:
            source_rows[referencia] = row

    current_latest_rows = list(
        Parcela.all_objects.filter(ciclo=latest_cycle, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("numero", "id")
    )
    for parcela in current_latest_rows:
        if parcela.referencia_mes in target_refs:
            continue
        parcela.soft_delete()

    existing_by_reference: dict[date, Parcela] = {}
    for parcela in (
        Parcela.all_objects.filter(ciclo__contrato=contrato)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("deleted_at", "id")
    ):
        existing_by_reference.setdefault(parcela.referencia_mes, parcela)

    used_numbers = set(
        Parcela.all_objects.filter(ciclo=latest_cycle).values_list("numero", flat=True)
    )

    def next_free_numero() -> int:
        numero = 1
        while numero in used_numbers:
            numero += 1
        used_numbers.add(numero)
        return numero

    changed = False
    for referencia in target_refs:
        row = source_rows.get(referencia)
        if referencia == APRIL_TARGET_REFERENCE:
            status = Parcela.Status.EM_PREVISAO
            data_pagamento = None
            observacao = (
                "Competência de abril mantida em previsão para o lote oficial "
                "de renovação parcial de abril de 2026."
            )
        else:
            source_status = row.get("status") if row else ""
            status = (
                Parcela.Status.DESCONTADO
                if source_status == Parcela.Status.DESCONTADO
                else Parcela.Status.LIQUIDADA
            )
            data_pagamento = (row.get("data_pagamento") if row else None) or referencia
            observacao = (
                (row.get("observacao") if row else "")
                or "Competência regularizada no lote oficial de renovação parcial de abril de 2026."
            )

        defaults = {
            "ciclo": latest_cycle,
            "associado": contrato.associado,
            "numero": next_free_numero(),
            "referencia_mes": referencia,
            "valor": (row.get("valor") if row else None) or contrato.valor_mensalidade,
            "data_vencimento": referencia,
            "status": status,
            "layout_bucket": Parcela.LayoutBucket.CYCLE,
            "data_pagamento": data_pagamento,
            "observacao": observacao,
            "deleted_at": None,
        }
        existing = existing_by_reference.get(referencia)
        if existing is None:
            Parcela.all_objects.create(**defaults)
            changed = True
            continue

        changed_fields: list[str] = []
        for field, value in defaults.items():
            if getattr(existing, field) != value:
                setattr(existing, field, value)
                changed_fields.append(field)
        if changed_fields:
            existing.save(update_fields=[*changed_fields, "updated_at"])
            changed = True

    latest_cycle_rows = _active_cycle_parcelas(latest_cycle)
    latest_cycle.data_inicio = min(parcela.referencia_mes for parcela in latest_cycle_rows)
    latest_cycle.data_fim = max(parcela.referencia_mes for parcela in latest_cycle_rows)
    latest_cycle.valor_total = sum((parcela.valor for parcela in latest_cycle_rows), start=0)
    latest_cycle.status = (
        blocked_small_value_cycle_status(
            has_unpaid_months=bool(build_contract_cycle_projection(contrato).get("unpaid_months"))
        )
        if is_return_imported_small_value_contract(contrato)
        else Ciclo.Status.APTO_A_RENOVAR
    )
    latest_cycle.save(update_fields=["data_inicio", "data_fim", "valor_total", "status", "updated_at"])

    if not contrato.admin_manual_layout_enabled:
        contrato.admin_manual_layout_enabled = True
        contrato.admin_manual_layout_updated_at = timezone.now()
        contrato.save(
            update_fields=[
                "admin_manual_layout_enabled",
                "admin_manual_layout_updated_at",
                "updated_at",
            ]
        )

    return changed


def run_april_renewal_cohort_repair(
    *,
    csv_path: str | Path,
    execute: bool,
    floor_reference: date = DEFAULT_FLOOR_REFERENCE,
) -> dict[str, Any]:
    rows = load_april_rows(csv_path)
    materialization_report: dict[str, Any] = {
        "cpfs_materialized": [],
        "contracts_created": 0,
        "associados_created": 0,
        "items_linked": 0,
        "errors": [],
    }
    small_value_override_report: dict[str, Any] = {
        "contracts_overridden": 0,
        "cpfs_overridden": [],
    }
    if execute:
        materialization_report = _materialize_missing_small_value_april_rows(rows)
        small_value_override_report = _enable_small_value_override_for_april_rows(rows)

    normalized_rows: list[dict[str, Any]] = []
    contracts_by_id: dict[int, Contrato] = {}
    missing_rows: list[dict[str, Any]] = []

    for row in rows:
        associado = Associado.objects.filter(cpf_cnpj=row.cpf_normalized).first()
        contrato = (
            resolve_operational_contract_for_associado(associado)
            if associado is not None
            else None
        )
        normalized_rows.append(
            {
                "index": row.index,
                "cpf_original": row.cpf_original,
                "cpf_normalized": row.cpf_normalized,
                "nome": row.nome,
                "associado_id": getattr(associado, "id", None),
                "contrato_id": getattr(contrato, "id", None),
                "contrato_codigo": getattr(contrato, "codigo", ""),
            }
        )
        if contrato is None:
            missing_rows.append(
                {
                    "index": row.index,
                    "cpf_original": row.cpf_original,
                    "cpf_normalized": row.cpf_normalized,
                    "nome": row.nome,
                }
            )
            continue
        contracts_by_id[contrato.id] = contrato

    incomplete_cycle_one_ids = _find_incomplete_cycle_one_contract_ids()
    candidate_ids = set(contracts_by_id.keys()) | incomplete_cycle_one_ids
    for contrato in (
        Contrato.objects.select_related("associado")
        .filter(id__in=sorted(candidate_ids))
        .order_by("id")
    ):
        contracts_by_id[contrato.id] = contrato

    preflight = {
        "rows_total": len(rows),
        "rows_with_contract": len({item["contrato_id"] for item in normalized_rows if item["contrato_id"]}),
        "missing_after_normalization": len(missing_rows),
        "incomplete_cycle_one_contracts": len(incomplete_cycle_one_ids),
        "candidate_contracts_total": len(candidate_ids),
    }

    pass_one_results: list[dict[str, Any]] = []
    april_results: list[dict[str, Any]] = []
    rebuild_results: list[dict[str, Any]] = []
    touched_contract_ids: set[int] = set()
    final_contract_ids = {
        item["contrato_id"] for item in normalized_rows if item["contrato_id"]
    }

    for contract_id in sorted(candidate_ids):
        contrato = contracts_by_id[contract_id]
        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=floor_reference,
            execute=execute,
            force_candidate=contract_id in incomplete_cycle_one_ids,
        )
        pass_one_results.append(result)
        if result["applied"]:
            touched_contract_ids.add(contract_id)

    for row in rows:
        contrato = contracts_by_id.get(
            next(
                (
                    item["contrato_id"]
                    for item in normalized_rows
                    if item["index"] == row.index and item["contrato_id"]
                ),
                None,
            )
        )
        if contrato is None:
            continue
        regularized_refs = _regularized_target_refs(contrato)
        conditional_status_overrides = {ref: "quitada" for ref in regularized_refs}
        conditional_observacao_overrides = {
            ref: "Competência regularizada a partir da lista oficial de renovação parcial de abril de 2026."
            for ref in regularized_refs
        }
        unconditional_status_overrides = {APRIL_TARGET_REFERENCE: Parcela.Status.EM_PREVISAO}
        unconditional_observacao_overrides = {
            APRIL_TARGET_REFERENCE: "Competência de abril mantida em previsão para o lote oficial de renovação parcial de abril de 2026."
        }
        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=floor_reference,
            end_reference=APRIL_TARGET_REFERENCE,
            conditional_status_overrides=conditional_status_overrides,
            conditional_observacao_overrides=conditional_observacao_overrides,
            unconditional_status_overrides=unconditional_status_overrides,
            unconditional_observacao_overrides=unconditional_observacao_overrides,
            force_candidate=True,
            execute=execute,
        )
        april_results.append(result)
        if result["applied"]:
            touched_contract_ids.add(contrato.id)

    if execute:
        for contract_id in sorted(touched_contract_ids):
            contrato = contracts_by_id[contract_id]
            rebuild = rebuild_contract_cycle_state(
                contrato,
                execute=True,
                force_active_operational_status=(
                    Refinanciamento.Status.APTO_A_RENOVAR
                    if contract_id in {item["contrato_id"] for item in normalized_rows if item["contrato_id"]}
                    else None
                ),
            )
            relink_contract_documents({contract_id})
            if contract_id in final_contract_ids:
                _force_latest_cycle_apto(contrato)
            rebuild_results.append(rebuild.as_dict())

        # The first rebuild pass is responsible for creating/updating the active
        # operational refinanciamento. Some projections depend on that operational
        # row to materialize the latest cycle layout (especially the official
        # April/2026 forecast on the renewal cohort), so run a second pass after
        # the operational sync is in place.
        for contract_id in sorted(final_contract_ids):
            contrato = contracts_by_id[contract_id]
            rebuild = rebuild_contract_cycle_state(
                contrato,
                execute=True,
                force_active_operational_status=Refinanciamento.Status.APTO_A_RENOVAR,
            )
            relink_contract_documents({contract_id})
            _force_latest_cycle_apto(contrato)
            rebuild_results.append(
                {
                    **rebuild.as_dict(),
                    "phase": "post_operational_sync",
                }
            )

        april_gap_ids = {
            contract_id
            for contract_id in final_contract_ids
            if _last_cycle_snapshot(contracts_by_id[contract_id])["april_status"]
            != Parcela.Status.EM_PREVISAO
        }
        for contract_id in sorted(april_gap_ids):
            contrato = contracts_by_id[contract_id]
            if not _materialize_manual_april_target_cycle(contrato):
                continue
            rebuild = rebuild_contract_cycle_state(
                contrato,
                execute=True,
                force_active_operational_status=Refinanciamento.Status.APTO_A_RENOVAR,
            )
            relink_contract_documents({contract_id})
            _force_latest_cycle_apto(contrato)
            rebuild_results.append(
                {
                    **rebuild.as_dict(),
                    "phase": "manual_april_target",
                }
            )

        remaining_cycle_one_ids = _find_incomplete_cycle_one_contract_ids() & final_contract_ids
        for contract_id in sorted(remaining_cycle_one_ids):
            contrato = contracts_by_id[contract_id]
            if not _materialize_remaining_cycle_one_regularized_rows(contrato):
                continue
            rebuild = rebuild_contract_cycle_state(
                contrato,
                execute=True,
                force_active_operational_status=Refinanciamento.Status.APTO_A_RENOVAR,
            )
            relink_contract_documents({contract_id})
            _force_latest_cycle_apto(contrato)
            rebuild_results.append(
                {
                    **rebuild.as_dict(),
                    "phase": "manual_cycle_one_completion",
                }
            )

    final_rows: list[dict[str, Any]] = []
    final_apto_total = 0
    final_april_forecast_total = 0
    final_missing_contracts: list[dict[str, Any]] = []
    for item in normalized_rows:
        contract_id = item["contrato_id"]
        if not contract_id:
            final_missing_contracts.append(item)
            continue
        contrato = contracts_by_id[contract_id]
        snapshot = _last_cycle_snapshot(contrato)
        active_refi = (
            Refinanciamento.objects.filter(
                contrato_origem=contrato,
                deleted_at__isnull=True,
                origem=Refinanciamento.Origem.OPERACIONAL,
            )
            .order_by("-updated_at", "-created_at", "-id")
            .first()
        )
        is_apto = snapshot["cycle_status"] == Ciclo.Status.APTO_A_RENOVAR or (
            active_refi is not None and active_refi.status == Refinanciamento.Status.APTO_A_RENOVAR
        )
        final_apto_total += int(is_apto)
        final_april_forecast_total += int(snapshot["april_status"] == Parcela.Status.EM_PREVISAO)
        final_rows.append(
            {
                **item,
                "last_cycle_number": snapshot["cycle_number"],
                "last_cycle_status": snapshot["cycle_status"],
                "last_cycle_references": snapshot["references"],
                "april_status": snapshot["april_status"],
                "operational_refinanciamento_id": getattr(active_refi, "id", None),
                "operational_status": getattr(active_refi, "status", ""),
                "operational_cycle_key": getattr(active_refi, "cycle_key", ""),
                "is_apto_final": is_apto,
            }
        )

    remaining_incomplete_cycle_one = 0
    for contract_id in _find_incomplete_cycle_one_contract_ids():
        if contract_id in final_contract_ids or contract_id in candidate_ids:
            remaining_incomplete_cycle_one += 1

    return {
        "generated_at": timezone.now().isoformat(),
        "mode": "execute" if execute else "dry-run",
        "csv_path": str(csv_path),
        "floor_reference": floor_reference.isoformat(),
        "target_april_reference": APRIL_TARGET_REFERENCE.isoformat(),
        "preflight": preflight,
        "summary": {
            "rows_total": len(rows),
            "rows_with_contract": len(final_rows),
            "missing_after_normalization": len(final_missing_contracts),
            "candidate_contracts_total": len(candidate_ids),
            "touched_contracts_total": len(touched_contract_ids),
            "small_value_materialized_total": len(materialization_report["cpfs_materialized"]),
            "small_value_override_total": small_value_override_report["contracts_overridden"],
            "final_apto_total": final_apto_total,
            "final_april_forecast_total": final_april_forecast_total,
            "remaining_incomplete_cycle_one": remaining_incomplete_cycle_one,
        },
        "materialization_report": materialization_report,
        "small_value_override_report": small_value_override_report,
        "missing_rows": missing_rows,
        "normalization": normalized_rows,
        "pass_one_results": pass_one_results,
        "april_results": april_results,
        "rebuild_results": rebuild_results,
        "final_rows": final_rows,
    }
