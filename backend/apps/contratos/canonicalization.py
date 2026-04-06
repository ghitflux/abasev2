from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Sequence

from django.db.models import QuerySet
from django.utils import timezone

from apps.associados.models import Associado

from .models import Contrato, Parcela

RETIMP_PREFIX = "RETIMP-"
PAID_PARCELA_STATUSES = {
    Parcela.Status.DESCONTADO,
    Parcela.Status.LIQUIDADA,
}
CONTRACT_STATUS_PRIORITY = {
    Contrato.Status.ATIVO: 0,
    Contrato.Status.ENCERRADO: 1,
    Contrato.Status.EM_ANALISE: 2,
    Contrato.Status.RASCUNHO: 3,
    Contrato.Status.CANCELADO: 4,
}


@dataclass(frozen=True)
class ContractCanonicalGroup:
    associado_id: int
    cpf_cnpj: str
    nome_associado: str
    canonical_contract_id: int
    canonical_contract_code: str
    duplicate_contract_ids: list[int]
    duplicate_contract_codes: list[str]
    rows: list[dict[str, object]]
    changed_contract_ids: list[int]

    def as_dict(self) -> dict[str, object]:
        return {
            "associado_id": self.associado_id,
            "cpf_cnpj": self.cpf_cnpj,
            "nome_associado": self.nome_associado,
            "canonical_contract_id": self.canonical_contract_id,
            "canonical_contract_code": self.canonical_contract_code,
            "duplicate_contract_ids": self.duplicate_contract_ids,
            "duplicate_contract_codes": self.duplicate_contract_codes,
            "rows": self.rows,
            "changed_contract_ids": self.changed_contract_ids,
        }


def is_synthetic_return_contract_code(value: str | None) -> bool:
    return (value or "").startswith(RETIMP_PREFIX)


def is_shadow_duplicate_contract(contrato: Contrato | None) -> bool:
    return bool(contrato and contrato.contrato_canonico_id)


def operational_contracts_queryset(queryset: QuerySet[Contrato]) -> QuerySet[Contrato]:
    return queryset.filter(contrato_canonico__isnull=True)


def _has_duplicate_shadow_metadata(contracts: Sequence[Contrato]) -> bool:
    return any(is_shadow_duplicate_contract(contrato) for contrato in contracts)


def _has_synthetic_duplicate_signal(contracts: Sequence[Contrato]) -> bool:
    synthetic = [contrato for contrato in contracts if is_synthetic_return_contract_code(contrato.codigo)]
    return bool(synthetic and len(contracts) > 1)


def should_collapse_associado_contracts(contracts: Sequence[Contrato]) -> bool:
    if len(contracts) <= 1:
        return False
    return _has_duplicate_shadow_metadata(contracts) or _has_synthetic_duplicate_signal(contracts)


def _resolve_cached_contracts(associado: Associado) -> list[Contrato] | None:
    cache = getattr(associado, "_prefetched_objects_cache", {})
    contratos = cache.get("contratos")
    if contratos is None:
        return None
    return list(contratos)


def _contracts_for_associado(associado: Associado) -> list[Contrato]:
    cached = _resolve_cached_contracts(associado)
    if cached is not None:
        return [contrato for contrato in cached if contrato.status != Contrato.Status.CANCELADO]
    return list(
        associado.contratos.exclude(status=Contrato.Status.CANCELADO)
        .select_related("agente")
        .order_by("created_at", "id")
    )


def _contract_seed_date(contrato: Contrato) -> date:
    return (
        contrato.auxilio_liberado_em
        or contrato.mes_averbacao
        or contrato.data_primeira_mensalidade
        or contrato.data_aprovacao
        or contrato.data_contrato
        or contrato.created_at.date()
    )


def _contract_is_effective(contrato: Contrato) -> bool:
    return bool(
        contrato.status in {Contrato.Status.ATIVO, Contrato.Status.ENCERRADO}
        or contrato.auxilio_liberado_em is not None
        or contrato.mes_averbacao is not None
    )


def _resolve_contract_parcelas(contrato: Contrato) -> list[Parcela]:
    prefetched_cycles = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
    if prefetched_cycles is not None:
        parcelas: list[Parcela] = []
        for ciclo in prefetched_cycles:
            prefetched_parcelas = getattr(ciclo, "_prefetched_objects_cache", {}).get("parcelas")
            if prefetched_parcelas is not None:
                parcelas.extend(
                    parcela
                    for parcela in prefetched_parcelas
                    if parcela.status != Parcela.Status.CANCELADO
                )
            else:
                parcelas.extend(list(ciclo.parcelas.exclude(status=Parcela.Status.CANCELADO)))
        return parcelas
    return list(
        Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "id")
    )


def _contract_progress_key(contrato: Contrato) -> tuple[int, Decimal, int, int]:
    parcelas = _resolve_contract_parcelas(contrato)
    paid_count = 0
    paid_value = Decimal("0.00")
    latest_payment_ordinal = 0
    for parcela in parcelas:
        if parcela.status in PAID_PARCELA_STATUSES:
            paid_count += 1
            paid_value += Decimal(str(parcela.valor or Decimal("0.00")))
            if parcela.data_pagamento is not None:
                latest_payment_ordinal = max(latest_payment_ordinal, parcela.data_pagamento.toordinal())
            else:
                latest_payment_ordinal = max(latest_payment_ordinal, parcela.referencia_mes.toordinal())
    return paid_count, paid_value, latest_payment_ordinal, len(parcelas)


def canonical_contract_sort_key(contrato: Contrato) -> tuple[object, ...]:
    paid_count, paid_value, latest_payment_ordinal, parcela_count = _contract_progress_key(contrato)
    return (
        0 if not is_synthetic_return_contract_code(contrato.codigo) else 1,
        CONTRACT_STATUS_PRIORITY.get(contrato.status, 99),
        0 if _contract_is_effective(contrato) else 1,
        -paid_count,
        -paid_value,
        -latest_payment_ordinal,
        -parcela_count,
        _contract_seed_date(contrato),
        contrato.id,
    )


def resolve_canonical_contract(
    associado: Associado | None = None,
    *,
    contracts: Sequence[Contrato] | None = None,
) -> Contrato | None:
    if contracts is None:
        if associado is None:
            raise ValueError("Informe associado ou contracts.")
        contracts = _contracts_for_associado(associado)
    candidates = [contrato for contrato in contracts if contrato.status != Contrato.Status.CANCELADO]
    if not candidates:
        return None
    non_shadow = [contrato for contrato in candidates if not is_shadow_duplicate_contract(contrato)]
    if non_shadow:
        candidates = non_shadow
    return min(candidates, key=canonical_contract_sort_key)


def get_operational_contracts_for_associado(associado: Associado) -> list[Contrato]:
    contracts = _contracts_for_associado(associado)
    if not contracts:
        return []
    operational = [contrato for contrato in contracts if not is_shadow_duplicate_contract(contrato)]
    if operational and len(operational) == 1:
        return operational
    if not should_collapse_associado_contracts(contracts):
        return sorted(operational, key=lambda contrato: (contrato.created_at, contrato.id), reverse=True)
    canonical = resolve_canonical_contract(contracts=operational or contracts)
    return [canonical] if canonical is not None else []


def resolve_operational_contract_for_associado(associado: Associado) -> Contrato | None:
    contracts = get_operational_contracts_for_associado(associado)
    if not contracts:
        return None
    if len(contracts) == 1:
        return contracts[0]
    return max(contracts, key=lambda contrato: (contrato.created_at, contrato.id))


def _shadow_type_for_contract(contrato: Contrato) -> str:
    if is_synthetic_return_contract_code(contrato.codigo):
        return Contrato.TipoUnificacao.RETIMP_SHADOW
    return Contrato.TipoUnificacao.DUPLICATE_CTR_SHADOW


def _base_queryset(*, cpf_cnpj: str | None = None) -> QuerySet[Contrato]:
    queryset = (
        Contrato.objects.select_related("associado", "agente")
        .prefetch_related("ciclos__parcelas")
        .exclude(status=Contrato.Status.CANCELADO)
        .order_by("associado__nome_completo", "created_at", "id")
    )
    if cpf_cnpj:
        queryset = queryset.filter(associado__cpf_cnpj=cpf_cnpj)
    return queryset


def build_canonicalization_payload(*, cpf_cnpj: str | None = None) -> dict[str, object]:
    contracts = list(_base_queryset(cpf_cnpj=cpf_cnpj))
    by_associado: dict[int, list[Contrato]] = defaultdict(list)
    for contrato in contracts:
        by_associado[contrato.associado_id].append(contrato)

    groups: list[ContractCanonicalGroup] = []
    for associado_id, associated_contracts in by_associado.items():
        if len(associated_contracts) <= 1 and not any(
            is_shadow_duplicate_contract(contrato) for contrato in associated_contracts
        ):
            continue

        canonical = resolve_canonical_contract(contracts=associated_contracts)
        if canonical is None:
            continue

        changed_contract_ids: list[int] = []
        rows: list[dict[str, object]] = []
        duplicate_ids: list[int] = []
        duplicate_codes: list[str] = []
        now = timezone.now()

        for contrato in sorted(associated_contracts, key=canonical_contract_sort_key):
            is_canonical = contrato.id == canonical.id
            desired_canonical_id = None if is_canonical else canonical.id
            desired_type = "" if is_canonical else _shadow_type_for_contract(contrato)
            desired_unificado_em = None if is_canonical else (contrato.unificado_em or now)
            changed = (
                contrato.contrato_canonico_id != desired_canonical_id
                or contrato.tipo_unificacao != desired_type
                or (
                    is_canonical
                    and (contrato.unificado_em is not None or contrato.tipo_unificacao)
                )
                or (
                    not is_canonical
                    and contrato.unificado_em != desired_unificado_em
                )
            )
            if changed:
                changed_contract_ids.append(contrato.id)
            if not is_canonical:
                duplicate_ids.append(contrato.id)
                duplicate_codes.append(contrato.codigo)
            rows.append(
                {
                    "contract_id": contrato.id,
                    "contract_code": contrato.codigo,
                    "status": contrato.status,
                    "is_canonical": is_canonical,
                    "shadow_type": "" if is_canonical else desired_type,
                    "current_canonical_id": contrato.contrato_canonico_id,
                    "changed": changed,
                }
            )

        groups.append(
            ContractCanonicalGroup(
                associado_id=associado_id,
                cpf_cnpj=canonical.associado.cpf_cnpj,
                nome_associado=canonical.associado.nome_completo,
                canonical_contract_id=canonical.id,
                canonical_contract_code=canonical.codigo,
                duplicate_contract_ids=duplicate_ids,
                duplicate_contract_codes=duplicate_codes,
                rows=rows,
                changed_contract_ids=changed_contract_ids,
            )
        )

    groups.sort(key=lambda item: (item.nome_associado, item.associado_id))
    return {
        "summary": {
            "groups": len(groups),
            "associados_multi_contrato": len(groups),
            "canonical_contracts": len(groups),
            "shadow_contracts": sum(len(group.duplicate_contract_ids) for group in groups),
            "changed_contracts": sum(len(group.changed_contract_ids) for group in groups),
        },
        "groups": [group.as_dict() for group in groups],
    }


def apply_canonicalization(*, cpf_cnpj: str | None = None) -> dict[str, object]:
    payload = build_canonicalization_payload(cpf_cnpj=cpf_cnpj)
    if not payload["groups"]:
        return payload

    contracts = {
        contrato.id: contrato
        for contrato in _base_queryset(cpf_cnpj=cpf_cnpj)
    }
    now = timezone.now()
    updated = 0
    for group in payload["groups"]:
        canonical_id = int(group["canonical_contract_id"])
        for row in group["rows"]:
            contract = contracts[int(row["contract_id"])]
            changed_fields: list[str] = []
            if row["is_canonical"]:
                if contract.contrato_canonico_id is not None:
                    contract.contrato_canonico = None
                    changed_fields.append("contrato_canonico")
                if contract.tipo_unificacao:
                    contract.tipo_unificacao = ""
                    changed_fields.append("tipo_unificacao")
                if contract.unificado_em is not None:
                    contract.unificado_em = None
                    changed_fields.append("unificado_em")
            else:
                if contract.contrato_canonico_id != canonical_id:
                    contract.contrato_canonico = contracts[canonical_id]
                    changed_fields.append("contrato_canonico")
                desired_type = str(row["shadow_type"])
                if contract.tipo_unificacao != desired_type:
                    contract.tipo_unificacao = desired_type
                    changed_fields.append("tipo_unificacao")
                if contract.unificado_em is None:
                    contract.unificado_em = now
                    changed_fields.append("unificado_em")

            if changed_fields:
                contract.save(update_fields=[*changed_fields, "updated_at"])
                updated += 1

    payload["summary"]["updated_contracts"] = updated
    return payload


def write_canonicalization_report(
    payload: dict[str, object],
    *,
    output_path: Path,
    fmt: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "csv":
        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=[
                    "associado_id",
                    "cpf_cnpj",
                    "nome_associado",
                    "canonical_contract_id",
                    "canonical_contract_code",
                    "contract_id",
                    "contract_code",
                    "status",
                    "is_canonical",
                    "shadow_type",
                    "current_canonical_id",
                    "changed",
                ],
            )
            writer.writeheader()
            for group in payload["groups"]:
                for row in group["rows"]:
                    writer.writerow(
                        {
                            "associado_id": group["associado_id"],
                            "cpf_cnpj": group["cpf_cnpj"],
                            "nome_associado": group["nome_associado"],
                            "canonical_contract_id": group["canonical_contract_id"],
                            "canonical_contract_code": group["canonical_contract_code"],
                            **row,
                        }
                    )
        return

    output_path.write_text(
        __import__("json").dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
