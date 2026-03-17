from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from apps.associados.models import only_digits
from core.legacy_dump import LegacyDump, parse_int, parse_str, parse_timestamp, parse_date


@dataclass(frozen=True)
class LegacyRenewalProof:
    legacy_id: int | None
    kind: str
    path: str
    original_name: str
    uploaded_by_user_id: int | None
    agente_snapshot: str = ""
    filial_snapshot: str = ""


@dataclass(frozen=True)
class LegacyRenewalTerm:
    path: str
    original_name: str
    mime: str
    size_bytes: int | None
    uploaded_at: datetime | None
    uploaded_by_user_id: int | None


@dataclass
class LegacyRenewal:
    legacy_id: int
    cpf_cnpj: str
    contrato_codigo_origem: str
    activation_at: datetime | None
    cycle_key: str
    ref1: date | None
    ref2: date | None
    ref3: date | None
    ref4: date | None
    created_by_user_id: int | None
    nome_snapshot: str = ""
    agente_snapshot: str = ""
    filial_snapshot: str = ""
    notes: str = ""
    proofs: list[LegacyRenewalProof] = field(default_factory=list)
    term: LegacyRenewalTerm | None = None


def _add_month(base: date) -> date:
    month_index = base.month
    year = base.year
    if month_index == 12:
        return date(year + 1, 1, 1)
    return date(year, month_index + 1, 1)


def next_month_start(
    value: datetime | None,
    *,
    ref1: date | None = None,
    ref2: date | None = None,
    ref3: date | None = None,
    ref4: date | None = None,
) -> date:
    origin_refs = sorted(reference for reference in [ref1, ref2, ref3, ref4] if reference is not None)
    if origin_refs:
        return _add_month(origin_refs[-1].replace(day=1))
    base = (value.date() if value else datetime.now().date()).replace(day=1)
    return base


def load_legacy_renewals(
    dump: LegacyDump,
    *,
    cpf_filter: str | None = None,
) -> list[LegacyRenewal]:
    normalized_filter = only_digits(cpf_filter) if cpf_filter else ""
    proofs_by_refi: dict[int, list[LegacyRenewalProof]] = {}
    for row in dump.table_rows("refinanciamento_comprovantes"):
        refinanciamento_id = parse_int(row.get("refinanciamento_id"))
        if refinanciamento_id is None:
            continue
        proofs_by_refi.setdefault(refinanciamento_id, []).append(
            LegacyRenewalProof(
                legacy_id=parse_int(row.get("id")),
                kind=parse_str(row.get("kind")).lower(),
                path=parse_str(row.get("path")),
                original_name=parse_str(row.get("original_name")),
                uploaded_by_user_id=parse_int(row.get("uploaded_by_user_id")),
                agente_snapshot=parse_str(row.get("agente_snapshot")),
                filial_snapshot=parse_str(row.get("filial_snapshot")),
            )
        )

    term_by_refi: dict[int, LegacyRenewalTerm] = {}
    for row in dump.table_rows("refinanciamento_solicitacoes"):
        refinanciamento_id = parse_int(row.get("refinanciamento_id"))
        if refinanciamento_id is None:
            continue
        term_path = parse_str(row.get("termo_antecipacao_path"))
        if not term_path:
            continue
        term_by_refi[refinanciamento_id] = LegacyRenewalTerm(
            path=term_path,
            original_name=parse_str(row.get("termo_antecipacao_original_name")),
            mime=parse_str(row.get("termo_antecipacao_mime")),
            size_bytes=parse_int(row.get("termo_antecipacao_size_bytes")),
            uploaded_at=parse_timestamp(row.get("termo_antecipacao_uploaded_at")),
            uploaded_by_user_id=parse_int(row.get("created_by_user_id")),
        )

    renewals: list[LegacyRenewal] = []
    for row in dump.table_rows("refinanciamentos"):
        legacy_id = parse_int(row.get("id"))
        cpf = only_digits(parse_str(row.get("cpf_cnpj")))
        if legacy_id is None or not cpf:
            continue
        if normalized_filter and cpf != normalized_filter:
            continue
        renewals.append(
            LegacyRenewal(
                legacy_id=legacy_id,
                cpf_cnpj=cpf,
                contrato_codigo_origem=parse_str(row.get("contrato_codigo_origem"))[:80],
                activation_at=parse_timestamp(row.get("created_at")),
                cycle_key=parse_str(row.get("cycle_key"))[:32],
                ref1=parse_date(row.get("ref1")),
                ref2=parse_date(row.get("ref2")),
                ref3=parse_date(row.get("ref3")),
                ref4=parse_date(row.get("ref4")),
                created_by_user_id=parse_int(row.get("created_by_user_id")),
                nome_snapshot=parse_str(row.get("nome_snapshot"))[:200],
                agente_snapshot=parse_str(row.get("agente_snapshot"))[:200],
                filial_snapshot=parse_str(row.get("filial_snapshot"))[:200],
                notes=parse_str(row.get("notes")),
                proofs=proofs_by_refi.get(legacy_id, []),
                term=term_by_refi.get(legacy_id),
            )
        )

    renewals.sort(key=lambda item: (item.activation_at or datetime.min, item.legacy_id))
    return renewals
