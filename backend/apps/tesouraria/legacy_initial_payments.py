from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from apps.associados.models import only_digits
from core.legacy_dump import (
    LegacyDump,
    parse_decimal,
    parse_int,
    parse_str,
    parse_timestamp,
)


@dataclass
class LegacyInitialPaymentRecord:
    legacy_id: int | None
    legacy_cadastro_id: int | None
    cpf_cnpj: str
    contrato_codigo: str
    status: str
    valor_pago: Decimal | None
    contrato_margem_disponivel: Decimal | None
    paid_at: datetime | None
    forma_pagamento: str
    notes: str
    comprovante_associado_path: str
    comprovante_agente_path: str
    created_by_user_id: int | None
    created_at: datetime | None
    assoc_legacy_url: str = ""
    agente_legacy_url: str = ""
    observacao: str = ""
    source: str = "dump"


def load_legacy_initial_payments(
    dump: LegacyDump,
    *,
    cpf_filter: str | None = None,
) -> list[LegacyInitialPaymentRecord]:
    normalized_filter = only_digits(cpf_filter) if cpf_filter else ""
    payments: list[LegacyInitialPaymentRecord] = []
    for row in dump.table_rows("tesouraria_pagamentos"):
        cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
        if not cpf_cnpj:
            continue
        if normalized_filter and normalized_filter != cpf_cnpj:
            continue
        payments.append(
            LegacyInitialPaymentRecord(
                legacy_id=parse_int(row.get("id")),
                legacy_cadastro_id=parse_int(row.get("agente_cadastro_id")),
                cpf_cnpj=cpf_cnpj,
                contrato_codigo=parse_str(row.get("contrato_codigo_contrato"))[:80],
                status=parse_str(row.get("status")) or "pendente",
                valor_pago=parse_decimal(row.get("valor_pago")),
                contrato_margem_disponivel=parse_decimal(row.get("contrato_margem_disponivel")),
                paid_at=parse_timestamp(row.get("paid_at")),
                forma_pagamento=parse_str(row.get("forma_pagamento"))[:40],
                notes=parse_str(row.get("notes")),
                comprovante_associado_path=parse_str(row.get("comprovante_associado_path"))[:500],
                comprovante_agente_path=parse_str(row.get("comprovante_agente_path"))[:500],
                created_by_user_id=parse_int(row.get("created_by_user_id")),
                created_at=parse_timestamp(row.get("created_at")),
            )
        )
    payments.sort(key=lambda item: (item.created_at or datetime.min, item.legacy_id or 0))
    return payments


def _normalize_override_row(row: dict[str, object]) -> LegacyInitialPaymentRecord:
    parse_dt = lambda value: parse_timestamp(str(value)) if value else None
    parse_dec = lambda value: (
        parse_decimal(str(value))
        if value not in (None, "", "NULL")
        else None
    )
    return LegacyInitialPaymentRecord(
        legacy_id=parse_int(str(row.get("legacy_payment_id") or "")),
        legacy_cadastro_id=parse_int(str(row.get("legacy_cadastro_id") or "")),
        cpf_cnpj=only_digits(str(row.get("cpf_cnpj") or "")),
        contrato_codigo=str(row.get("contrato_codigo") or "")[:80],
        status=str(row.get("status") or "pendente"),
        valor_pago=parse_dec(row.get("valor_pago")),
        contrato_margem_disponivel=parse_dec(row.get("contrato_margem_disponivel")),
        paid_at=parse_dt(row.get("paid_at")),
        forma_pagamento=str(row.get("forma_pagamento") or "")[:40],
        notes=str(row.get("notes") or ""),
        comprovante_associado_path=str(row.get("assoc_legacy_path") or "")[:500],
        comprovante_agente_path=str(row.get("agente_legacy_path") or "")[:500],
        created_by_user_id=parse_int(str(row.get("created_by_user_id") or "")),
        created_at=parse_dt(row.get("created_at")),
        assoc_legacy_url=str(row.get("assoc_legacy_url") or ""),
        agente_legacy_url=str(row.get("agente_legacy_url") or ""),
        observacao=str(row.get("observacao") or ""),
        source="override",
    )


def load_initial_payment_overrides(
    override_path: str | Path | None,
) -> list[LegacyInitialPaymentRecord]:
    if not override_path:
        return []
    path = Path(override_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de overrides não encontrado: {path}")

    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            rows = payload.get("payments", [])
        else:
            rows = payload
        return [_normalize_override_row(dict(row)) for row in rows]

    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            return [_normalize_override_row(dict(row)) for row in reader]

    raise ValueError("Overrides devem ser JSON ou CSV.")


def merge_initial_payment_overrides(
    records: list[LegacyInitialPaymentRecord],
    overrides: list[LegacyInitialPaymentRecord],
) -> list[LegacyInitialPaymentRecord]:
    if not overrides:
        return records

    by_legacy_id = {
        record.legacy_id: record
        for record in records
        if record.legacy_id is not None
    }
    by_contract = {
        (record.cpf_cnpj, record.contrato_codigo): record
        for record in records
        if record.cpf_cnpj and record.contrato_codigo
    }

    for override in overrides:
        target = None
        if override.legacy_id is not None:
            target = by_legacy_id.get(override.legacy_id)
        if target is None and override.cpf_cnpj and override.contrato_codigo:
            target = by_contract.get((override.cpf_cnpj, override.contrato_codigo))
        if target is None:
            records.append(override)
            if override.legacy_id is not None:
                by_legacy_id[override.legacy_id] = override
            if override.cpf_cnpj and override.contrato_codigo:
                by_contract[(override.cpf_cnpj, override.contrato_codigo)] = override
            continue

        target.status = override.status or target.status
        target.valor_pago = (
            override.valor_pago
            if override.valor_pago is not None
            else target.valor_pago
        )
        target.contrato_margem_disponivel = (
            override.contrato_margem_disponivel
            if override.contrato_margem_disponivel is not None
            else target.contrato_margem_disponivel
        )
        target.paid_at = override.paid_at or target.paid_at
        target.forma_pagamento = override.forma_pagamento or target.forma_pagamento
        target.notes = override.notes or target.notes
        target.comprovante_associado_path = (
            override.comprovante_associado_path or target.comprovante_associado_path
        )
        target.comprovante_agente_path = (
            override.comprovante_agente_path or target.comprovante_agente_path
        )
        target.assoc_legacy_url = override.assoc_legacy_url or target.assoc_legacy_url
        target.agente_legacy_url = override.agente_legacy_url or target.agente_legacy_url
        target.observacao = override.observacao or target.observacao
        target.source = "override"

    records.sort(key=lambda item: (item.created_at or datetime.min, item.legacy_id or 0))
    return records
