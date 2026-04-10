from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.associados.models import Associado, only_digits
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.tesouraria.models import BaixaManual

from .competencia import sync_competencia_locks_for_references
from .cycle_timeline import get_contract_cycle_size
from .models import Ciclo, Contrato, Parcela

PAID_STATUS_CODES = {"1", "4", "M"}
UNPAID_STATUS_CODES = {"2", "3", "S"}
RESOLVED_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
    "quitada",
}


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def month_start(value: date | None) -> date | None:
    if value is None:
        return None
    return value.replace(day=1)


def month_label(value: date) -> str:
    return value.strftime("%Y-%m")


def default_pre_october_repair_report_path(
    prefix: str = "repair_pre_october_cycles",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return Path(settings.BASE_DIR) / "media" / "relatorios" / f"{prefix}_{timestamp}.json"


def write_pre_october_repair_report(
    payload: dict[str, Any],
    target: str | Path | None = None,
) -> Path:
    report_path = Path(target) if target else default_pre_october_repair_report_path()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report_path


@dataclass(frozen=True)
class DesiredParcela:
    referencia_mes: date
    status: str
    valor: Any
    data_pagamento: date | None
    observacao: str


def _pagamento_sort_key(pagamento: PagamentoMensalidade) -> tuple[Any, ...]:
    return (
        pagamento.manual_paid_at or pagamento.updated_at or pagamento.created_at,
        pagamento.id,
    )


def _return_sort_key(item: ArquivoRetornoItem) -> tuple[Any, ...]:
    return (
        item.arquivo_retorno.processado_em or item.arquivo_retorno.created_at,
        item.updated_at,
        item.id,
    )


def _map_return_status(status_code: str) -> str:
    folded = str(status_code or "").strip().upper()
    if folded in PAID_STATUS_CODES:
        return Parcela.Status.DESCONTADO
    if folded in UNPAID_STATUS_CODES:
        return Parcela.Status.NAO_DESCONTADO
    return Parcela.Status.EM_ABERTO


def _map_payment_status(pagamento: PagamentoMensalidade) -> str:
    status_code = str(pagamento.status_code or "").strip().upper()
    if pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO:
        if status_code and status_code not in PAID_STATUS_CODES:
            return "quitada"
        return Parcela.Status.DESCONTADO
    if status_code in PAID_STATUS_CODES:
        return Parcela.Status.DESCONTADO
    if status_code in UNPAID_STATUS_CODES:
        return Parcela.Status.NAO_DESCONTADO
    return Parcela.Status.EM_ABERTO


def _payment_paid_date(pagamento: PagamentoMensalidade) -> date | None:
    if pagamento.manual_paid_at is not None:
        return pagamento.manual_paid_at.date()
    status = _map_payment_status(pagamento)
    if status in RESOLVED_STATUSES:
        return (pagamento.updated_at or pagamento.created_at or timezone.now()).date()
    return None


def _sanitize_contract_dates(contrato: Contrato, *, floor_reference: date) -> dict[str, tuple[Any, Any]]:
    changed: dict[str, tuple[Any, Any]] = {}
    approval_anchor = add_months(floor_reference, -1)

    def _set_if_changed(field: str, value: Any) -> None:
        current = getattr(contrato, field)
        if current != value:
            changed[field] = (current, value)
            setattr(contrato, field, value)

    data_contrato = month_start(contrato.data_contrato)
    if data_contrato is None or data_contrato < approval_anchor:
        _set_if_changed("data_contrato", approval_anchor)

    data_aprovacao = month_start(contrato.data_aprovacao)
    if data_aprovacao is None or data_aprovacao < approval_anchor:
        _set_if_changed("data_aprovacao", approval_anchor)

    primeira = month_start(contrato.data_primeira_mensalidade)
    if primeira is None or primeira < floor_reference or contrato.data_primeira_mensalidade != floor_reference:
        _set_if_changed("data_primeira_mensalidade", floor_reference)

    averbacao = month_start(contrato.mes_averbacao)
    if averbacao is None or averbacao < floor_reference or contrato.mes_averbacao != floor_reference:
        _set_if_changed("mes_averbacao", floor_reference)

    liberado = month_start(contrato.auxilio_liberado_em)
    if liberado is not None and liberado < floor_reference:
        _set_if_changed("auxilio_liberado_em", floor_reference)

    if changed:
        contrato.save(update_fields=[*changed.keys(), "updated_at"])
    return changed


def _active_parcelas(contrato: Contrato) -> list[Parcela]:
    return list(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo")
        .order_by("referencia_mes", "ciclo__numero", "numero", "id")
    )


def _reserve_cycle_parcela_numbers(parcelas: list[Parcela]) -> None:
    by_cycle: dict[int, list[Parcela]] = defaultdict(list)
    for parcela in parcelas:
        by_cycle[parcela.ciclo_id].append(parcela)

    for cycle_parcelas in by_cycle.values():
        max_existing_number = max((parcela.numero or 0) for parcela in cycle_parcelas)
        reserved_base = max_existing_number + 100
        for index, parcela in enumerate(cycle_parcelas, start=1):
            reserved_number = reserved_base + index
            if parcela.numero == reserved_number:
                continue
            parcela.numero = reserved_number
            parcela.save(update_fields=["numero", "updated_at"])


def _reserve_contract_cycle_parcela_numbers(contrato: Contrato) -> None:
    parcelas = list(
        Parcela.all_objects.filter(ciclo__contrato=contrato)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("ciclo_id", "numero", "id")
    )
    _reserve_cycle_parcela_numbers(parcelas)


def _choose_existing_parcelas_by_reference(
    parcelas: list[Parcela],
) -> tuple[dict[date, Parcela], list[Parcela]]:
    by_reference: dict[date, Parcela] = {}
    leftovers: list[Parcela] = []
    for parcela in parcelas:
        current = by_reference.get(parcela.referencia_mes)
        if current is None:
            by_reference[parcela.referencia_mes] = parcela
            continue
        if current.status == Parcela.Status.EM_PREVISAO and parcela.status in RESOLVED_STATUSES:
            leftovers.append(current)
            by_reference[parcela.referencia_mes] = parcela
        else:
            leftovers.append(parcela)
    return by_reference, leftovers


def _return_queryset_for_contract(contrato: Contrato, *, floor_reference: date):
    cpf = only_digits(contrato.associado.cpf_cnpj)
    return (
        ArquivoRetornoItem.all_objects.filter(
            deleted_at__isnull=True,
            arquivo_retorno__competencia__gte=floor_reference,
        )
        .filter(
            Q(associado=contrato.associado)
            | Q(cpf_cnpj__in=[contrato.associado.cpf_cnpj, cpf])
        )
        .select_related("arquivo_retorno")
        .order_by("arquivo_retorno__competencia", "id")
    )


def _payment_queryset_for_contract(contrato: Contrato, *, floor_reference: date):
    cpf = only_digits(contrato.associado.cpf_cnpj)
    return (
        PagamentoMensalidade.all_objects.filter(
            deleted_at__isnull=True,
            referencia_month__gte=floor_reference,
        )
        .filter(
            Q(associado=contrato.associado)
            | Q(cpf_cnpj__in=[contrato.associado.cpf_cnpj, cpf])
        )
        .order_by("referencia_month", "id")
    )


def _build_desired_parcelas(
    contrato: Contrato,
    *,
    floor_reference: date,
    current_month: date,
    end_reference: date | None = None,
    conditional_status_overrides: dict[date, str] | None = None,
    conditional_observacao_overrides: dict[date, str] | None = None,
    unconditional_status_overrides: dict[date, str] | None = None,
    unconditional_observacao_overrides: dict[date, str] | None = None,
) -> tuple[list[DesiredParcela], dict[str, Any]]:
    active_parcelas = _active_parcelas(contrato)
    active_by_reference, duplicate_parcelas = _choose_existing_parcelas_by_reference(active_parcelas)

    pagamentos_by_reference: dict[date, PagamentoMensalidade] = {}
    for pagamento in _payment_queryset_for_contract(contrato, floor_reference=floor_reference):
        pagamentos_by_reference[month_start(pagamento.referencia_month)] = pagamento

    retorno_by_reference: dict[date, ArquivoRetornoItem] = {}
    for item in _return_queryset_for_contract(contrato, floor_reference=floor_reference):
        referencia = month_start(item.arquivo_retorno.competencia)
        current = retorno_by_reference.get(referencia)
        if current is None or _return_sort_key(item) >= _return_sort_key(current):
            retorno_by_reference[referencia] = item

    known_references = {
        referencia
        for referencia in active_by_reference.keys()
        if referencia >= floor_reference
    }
    known_references.update(
        referencia
        for referencia in pagamentos_by_reference.keys()
        if referencia is not None and referencia >= floor_reference
    )
    known_references.update(
        referencia
        for referencia in retorno_by_reference.keys()
        if referencia is not None and referencia >= floor_reference
    )
    if not known_references:
        return [], {
            "pre_floor_refs": [],
            "known_refs": [],
            "duplicates": [],
        }

    if end_reference is not None:
        end_reference = month_start(end_reference)
        known_references.add(end_reference)

    max_reference = max(known_references)
    desired_references: list[date] = []
    cursor = floor_reference
    while cursor <= max_reference:
        desired_references.append(cursor)
        cursor = add_months(cursor, 1)

    desired: list[DesiredParcela] = []
    for referencia in desired_references:
        unconditional_status = (unconditional_status_overrides or {}).get(referencia)
        unconditional_note = (unconditional_observacao_overrides or {}).get(referencia) or ""
        conditional_status = (conditional_status_overrides or {}).get(referencia)
        conditional_note = (conditional_observacao_overrides or {}).get(referencia) or ""
        existing = active_by_reference.get(referencia)
        pagamento = pagamentos_by_reference.get(referencia)
        retorno = retorno_by_reference.get(referencia)

        if unconditional_status is not None:
            resolved = unconditional_status in RESOLVED_STATUSES
            desired.append(
                DesiredParcela(
                    referencia_mes=referencia,
                    status=unconditional_status,
                    valor=(
                        existing.valor
                        if existing is not None
                        else pagamento.valor
                        if pagamento is not None and pagamento.valor
                        else retorno.valor_descontado
                        if retorno is not None and retorno.valor_descontado
                        else contrato.valor_mensalidade
                    ),
                    data_pagamento=(
                        existing.data_pagamento
                        if existing is not None and existing.data_pagamento
                        else _payment_paid_date(pagamento)
                        if pagamento is not None and resolved
                        else referencia
                        if resolved
                        else None
                    ),
                    observacao=(
                        unconditional_note
                        or "Competência ajustada explicitamente na janela de reparo."
                    ),
                )
            )
            continue

        if (
            existing is not None
            and (
                existing.status in RESOLVED_STATUSES
                or existing.status == Parcela.Status.NAO_DESCONTADO
                or referencia >= current_month
            )
        ):
            status = existing.status
            data_pagamento = existing.data_pagamento
            observacao = existing.observacao
            if conditional_status is not None and status not in RESOLVED_STATUSES:
                status = conditional_status
                observacao = (
                    conditional_note
                    or "Competência regularizada pela janela de reparo."
                )
                if conditional_status in RESOLVED_STATUSES and data_pagamento is None:
                    data_pagamento = referencia
            desired.append(
                DesiredParcela(
                    referencia_mes=referencia,
                    status=status,
                    valor=existing.valor,
                    data_pagamento=data_pagamento,
                    observacao=observacao,
                )
            )
            continue

        if pagamento is not None:
            status = _map_payment_status(pagamento)
            data_pagamento = _payment_paid_date(pagamento)
            observacao = "Materializada a partir de PagamentoMensalidade."
            if conditional_status is not None and status not in RESOLVED_STATUSES:
                status = conditional_status
                observacao = (
                    conditional_note
                    or "Competência regularizada pela janela de reparo."
                )
                if conditional_status in RESOLVED_STATUSES and data_pagamento is None:
                    data_pagamento = referencia
            desired.append(
                DesiredParcela(
                    referencia_mes=referencia,
                    status=status,
                    valor=pagamento.valor or contrato.valor_mensalidade,
                    data_pagamento=data_pagamento,
                    observacao=observacao,
                )
            )
            continue

        if retorno is not None:
            status = _map_return_status(retorno.status_codigo)
            data_pagamento = (
                referencia if status in RESOLVED_STATUSES else None
            )
            observacao = (
                f"Materializada a partir do arquivo retorno {retorno.arquivo_retorno.arquivo_nome}."
            )
            if conditional_status is not None and status not in RESOLVED_STATUSES:
                status = conditional_status
                observacao = (
                    conditional_note
                    or "Competência regularizada pela janela de reparo."
                )
                if conditional_status in RESOLVED_STATUSES and data_pagamento is None:
                    data_pagamento = referencia
            desired.append(
                DesiredParcela(
                    referencia_mes=referencia,
                    status=status,
                    valor=retorno.valor_descontado or contrato.valor_mensalidade,
                    data_pagamento=data_pagamento,
                    observacao=observacao,
                )
            )
            continue

        fallback_status = (
            Parcela.Status.NAO_DESCONTADO
            if referencia < current_month
            else Parcela.Status.EM_PREVISAO
        )
        fallback_data_pagamento = None
        fallback_observacao = (
            "Competência preenchida automaticamente ao remover referências pré-outubro."
        )
        if conditional_status is not None and fallback_status not in RESOLVED_STATUSES:
            fallback_status = conditional_status
            fallback_observacao = (
                conditional_note
                or "Competência regularizada pela janela de reparo."
            )
            if conditional_status in RESOLVED_STATUSES:
                fallback_data_pagamento = referencia
        desired.append(
            DesiredParcela(
                referencia_mes=referencia,
                status=fallback_status,
                valor=contrato.valor_mensalidade,
                data_pagamento=fallback_data_pagamento,
                observacao=fallback_observacao,
            )
        )

    return desired, {
        "pre_floor_refs": sorted(
            month_label(parcela.referencia_mes)
            for parcela in active_parcelas
            if parcela.referencia_mes < floor_reference
        ),
        "known_refs": sorted(month_label(ref) for ref in known_references),
        "duplicates": [parcela.id for parcela in duplicate_parcelas],
    }


def _derive_cycle_status(
    parcelas: list[DesiredParcela],
    *,
    cycle_index: int,
    total_cycles: int,
    threshold: int,
) -> str:
    paid_count = sum(1 for parcela in parcelas if parcela.status in RESOLVED_STATUSES)
    has_unpaid = any(
        parcela.status in {Parcela.Status.NAO_DESCONTADO, Parcela.Status.EM_ABERTO}
        for parcela in parcelas
    )
    if cycle_index < total_cycles:
        if has_unpaid:
            return Ciclo.Status.PENDENCIA
        return Ciclo.Status.CICLO_RENOVADO
    if has_unpaid:
        return Ciclo.Status.PENDENCIA
    if paid_count >= threshold:
        return Ciclo.Status.APTO_A_RENOVAR
    return Ciclo.Status.ABERTO


def _iter_candidate_contracts(
    *,
    floor_reference: date,
    cpf_cnpj: str | None = None,
) -> list[Contrato]:
    queryset = (
        Contrato.objects.select_related("associado")
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("associado__nome_completo", "id")
    )
    if cpf_cnpj:
        queryset = queryset.filter(associado__cpf_cnpj=only_digits(cpf_cnpj))

    candidates: list[Contrato] = []
    for contrato in queryset:
        active_refs = sorted(
            {
                parcela.referencia_mes
                for parcela in _active_parcelas(contrato)
            }
        )
        if not active_refs:
            continue
        if any(ref < floor_reference for ref in active_refs):
            candidates.append(contrato)
            continue
        if not cpf_cnpj:
            continue
        expected = []
        cursor = active_refs[0]
        while cursor <= active_refs[-1]:
            expected.append(cursor)
            cursor = add_months(cursor, 1)
        if set(expected) != set(active_refs):
            candidates.append(contrato)
    return candidates


def _update_or_create_parcela(
    *,
    ciclo: Ciclo,
    contrato: Contrato,
    existing: Parcela | None,
    numero: int,
    desired: DesiredParcela,
) -> Parcela:
    defaults = {
        "associado": contrato.associado,
        "numero": numero,
        "referencia_mes": desired.referencia_mes,
        "valor": desired.valor,
        "data_vencimento": desired.referencia_mes,
        "status": desired.status,
        "layout_bucket": Parcela.LayoutBucket.CYCLE,
        "data_pagamento": desired.data_pagamento,
        "observacao": desired.observacao,
        "deleted_at": None,
    }
    if existing is None:
        return Parcela.all_objects.create(ciclo=ciclo, **defaults)

    changed_fields: list[str] = []
    if existing.ciclo_id != ciclo.id:
        existing.ciclo = ciclo
        changed_fields.append("ciclo")
    for field, value in defaults.items():
        if getattr(existing, field) != value:
            setattr(existing, field, value)
            changed_fields.append(field)
    if changed_fields:
        existing.save(update_fields=[*changed_fields, "updated_at"])
    return existing


@transaction.atomic
def repair_contract_pre_october_cycles(
    contrato: Contrato,
    *,
    floor_reference: date,
    end_reference: date | None = None,
    conditional_status_overrides: dict[date, str] | None = None,
    conditional_observacao_overrides: dict[date, str] | None = None,
    unconditional_status_overrides: dict[date, str] | None = None,
    unconditional_observacao_overrides: dict[date, str] | None = None,
    force_candidate: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    active_parcelas = _active_parcelas(contrato)
    current_month = timezone.localdate().replace(day=1)
    desired_parcelas, diagnostics = _build_desired_parcelas(
        contrato,
        floor_reference=floor_reference,
        current_month=current_month,
        end_reference=end_reference,
        conditional_status_overrides=conditional_status_overrides,
        conditional_observacao_overrides=conditional_observacao_overrides,
        unconditional_status_overrides=unconditional_status_overrides,
        unconditional_observacao_overrides=unconditional_observacao_overrides,
    )
    if not desired_parcelas:
        return {
            "contract_id": contrato.id,
            "contract_code": contrato.codigo,
            "associado": contrato.associado.nome_completo,
            "candidate": False,
            "applied": False,
            "pre_floor_removed": 0,
            "parcelas_created": 0,
            "parcelas_updated": 0,
            "parcelas_soft_deleted": 0,
            "cycles_created": 0,
            "cycles_updated": 0,
            "cycles_soft_deleted": 0,
            "date_fields_updated": {},
            **diagnostics,
        }

    old_reference_by_parcela_id = {
        parcela.id: parcela.referencia_mes
        for parcela in active_parcelas
    }
    has_pre_floor = any(parcela.referencia_mes < floor_reference for parcela in active_parcelas)
    desired_ref_set = {item.referencia_mes for item in desired_parcelas}
    candidate = force_candidate or has_pre_floor or desired_ref_set != {
        parcela.referencia_mes for parcela in active_parcelas if parcela.referencia_mes >= floor_reference
    }

    result = {
        "contract_id": contrato.id,
        "contract_code": contrato.codigo,
        "associado": contrato.associado.nome_completo,
        "candidate": candidate,
        "applied": False,
        "pre_floor_removed": sum(1 for parcela in active_parcelas if parcela.referencia_mes < floor_reference),
        "parcelas_created": 0,
        "parcelas_updated": 0,
        "parcelas_soft_deleted": 0,
        "cycles_created": 0,
        "cycles_updated": 0,
        "cycles_soft_deleted": 0,
        "date_fields_updated": {},
        **diagnostics,
    }
    if not execute or not candidate:
        return result

    result["date_fields_updated"] = _sanitize_contract_dates(
        contrato,
        floor_reference=floor_reference,
    )

    _reserve_contract_cycle_parcela_numbers(contrato)
    active_parcelas = _active_parcelas(contrato)
    active_by_reference, duplicate_parcelas = _choose_existing_parcelas_by_reference(active_parcelas)
    cycle_size = get_contract_cycle_size(contrato)
    desired_cycle_chunks = [
        desired_parcelas[index : index + cycle_size]
        for index in range(0, len(desired_parcelas), cycle_size)
    ]
    threshold = max(1, len(desired_cycle_chunks[0]) - 1) if desired_cycle_chunks else 1
    existing_cycles = list(
        Ciclo.all_objects.filter(contrato=contrato).order_by("numero", "deleted_at", "id")
    )
    cycle_by_number: dict[int, Ciclo] = {}
    for ciclo in existing_cycles:
        cycle_by_number.setdefault(ciclo.numero, ciclo)

    new_parcela_by_reference: dict[date, Parcela] = {}
    used_cycle_ids: set[int] = set()
    used_parcela_ids: set[int] = set()

    for cycle_index, chunk in enumerate(desired_cycle_chunks, start=1):
        existing_cycle = cycle_by_number.get(cycle_index)
        if existing_cycle is None:
            ciclo = Ciclo.objects.create(
                contrato=contrato,
                numero=cycle_index,
                data_inicio=chunk[0].referencia_mes,
                data_fim=chunk[-1].referencia_mes,
                status=_derive_cycle_status(
                    chunk,
                    cycle_index=cycle_index,
                    total_cycles=len(desired_cycle_chunks),
                    threshold=threshold,
                ),
                valor_total=sum(item.valor for item in chunk),
            )
            result["cycles_created"] += 1
        else:
            ciclo = existing_cycle
            used_cycle_ids.add(ciclo.id)
            changed_fields: list[str] = []
            if ciclo.deleted_at is not None:
                ciclo.deleted_at = None
                changed_fields.append("deleted_at")
            desired_status = _derive_cycle_status(
                chunk,
                cycle_index=cycle_index,
                total_cycles=len(desired_cycle_chunks),
                threshold=threshold,
            )
            if ciclo.data_inicio != chunk[0].referencia_mes:
                ciclo.data_inicio = chunk[0].referencia_mes
                changed_fields.append("data_inicio")
            if ciclo.data_fim != chunk[-1].referencia_mes:
                ciclo.data_fim = chunk[-1].referencia_mes
                changed_fields.append("data_fim")
            if ciclo.status != desired_status:
                ciclo.status = desired_status
                changed_fields.append("status")
            desired_total = sum(item.valor for item in chunk)
            if ciclo.valor_total != desired_total:
                ciclo.valor_total = desired_total
                changed_fields.append("valor_total")
            if changed_fields:
                ciclo.save(update_fields=[*changed_fields, "updated_at"])
                result["cycles_updated"] += 1

        used_cycle_ids.add(ciclo.id)
        for slot, desired in enumerate(chunk, start=1):
            existing_parcela = active_by_reference.get(desired.referencia_mes)
            parcela = _update_or_create_parcela(
                ciclo=ciclo,
                contrato=contrato,
                existing=existing_parcela,
                numero=slot,
                desired=desired,
            )
            if existing_parcela is None:
                result["parcelas_created"] += 1
            else:
                result["parcelas_updated"] += 1
            used_parcela_ids.add(parcela.id)
            new_parcela_by_reference[desired.referencia_mes] = parcela

    for parcela in duplicate_parcelas:
        if parcela.deleted_at is None:
            parcela.soft_delete()
            result["parcelas_soft_deleted"] += 1

    for parcela in active_parcelas:
        if parcela.id in used_parcela_ids or parcela.deleted_at is not None:
            continue
        parcela.soft_delete()
        result["parcelas_soft_deleted"] += 1

    for ciclo in existing_cycles:
        if ciclo.id in used_cycle_ids or ciclo.deleted_at is not None:
            continue
        ciclo.soft_delete()
        result["cycles_soft_deleted"] += 1

    affected_refs = set(old_reference_by_parcela_id.values()) | set(new_parcela_by_reference.keys())
    for parcela_id, referencia in old_reference_by_parcela_id.items():
        target = new_parcela_by_reference.get(referencia)
        if target is None or target.id == parcela_id:
            continue
        ArquivoRetornoItem.all_objects.filter(parcela_id=parcela_id).update(parcela=target)
        existing_baixa = BaixaManual.all_objects.filter(parcela_id=target.id, deleted_at__isnull=True).exists()
        if not existing_baixa:
            BaixaManual.all_objects.filter(
                parcela_id=parcela_id,
                deleted_at__isnull=True,
            ).update(parcela=target)

    for referencia, parcela in new_parcela_by_reference.items():
        competencias = {referencia.strftime("%m/%Y"), referencia.strftime("%Y-%m")}
        ArquivoRetornoItem.all_objects.filter(
            deleted_at__isnull=True,
        ).filter(
            Q(associado=contrato.associado)
            | Q(cpf_cnpj__in=[contrato.associado.cpf_cnpj, only_digits(contrato.associado.cpf_cnpj)])
        ).filter(
            Q(competencia__in=competencias)
            | Q(parcela__referencia_mes=referencia)
        ).update(associado=contrato.associado, parcela=parcela)

    sync_competencia_locks_for_references(
        associado_id=contrato.associado_id,
        referencias=sorted(affected_refs),
    )
    result["applied"] = True
    return result


def audit_and_repair_pre_october_cycles(
    *,
    floor_reference: date,
    cpf_cnpj: str | None = None,
    execute: bool = False,
) -> dict[str, Any]:
    contracts = _iter_candidate_contracts(
        floor_reference=floor_reference,
        cpf_cnpj=cpf_cnpj,
    )
    results = [
        repair_contract_pre_october_cycles(
            contrato,
            floor_reference=floor_reference,
            execute=execute,
        )
        for contrato in contracts
    ]

    return {
        "generated_at": timezone.now().isoformat(),
        "mode": "execute" if execute else "dry-run",
        "floor_reference": month_label(floor_reference),
        "summary": {
            "contracts_scanned": len(contracts),
            "contracts_candidate": sum(1 for item in results if item["candidate"]),
            "contracts_applied": sum(1 for item in results if item["applied"]),
            "pre_floor_removed": sum(item["pre_floor_removed"] for item in results),
            "parcelas_created": sum(item["parcelas_created"] for item in results),
            "parcelas_updated": sum(item["parcelas_updated"] for item in results),
            "parcelas_soft_deleted": sum(item["parcelas_soft_deleted"] for item in results),
            "cycles_created": sum(item["cycles_created"] for item in results),
            "cycles_updated": sum(item["cycles_updated"] for item in results),
            "cycles_soft_deleted": sum(item["cycles_soft_deleted"] for item in results),
        },
        "results": results,
    }
