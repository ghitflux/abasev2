from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.db import DatabaseError, connection

LEGACY_PAGAMENTOS_TABLE = "pagamentos_mensalidades"


@dataclass(frozen=True)
class LegacyPagamentoSnapshot:
    manual_status: str | None = None
    esperado_manual: Decimal | None = None
    recebido_manual: Decimal | None = None
    manual_paid_at: datetime | None = None
    manual_forma_pagamento: str | None = None
    manual_comprovante_path: str | None = None
    agente_refi_solicitado: bool = False

    def has_manual_context(self) -> bool:
        return bool(
            self.manual_status
            or self.esperado_manual is not None
            or self.recebido_manual is not None
            or self.manual_paid_at is not None
            or self.manual_forma_pagamento
            or self.manual_comprovante_path
            or self.agente_refi_solicitado
        )


def _normalize_cpf(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _legacy_table_exists() -> bool:
    try:
        return LEGACY_PAGAMENTOS_TABLE in connection.introspection.table_names()
    except DatabaseError:
        return False


def _parse_dump_date(value: str | None) -> date | None:
    if not value or value == "NULL":
        return None
    try:
        return datetime.strptime(value.strip("'"), "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_dump_datetime(value: str | None) -> datetime | None:
    if not value or value == "NULL":
        return None
    raw = value.strip("'")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _parse_dump_decimal(value: str | None) -> Decimal | None:
    if not value or value == "NULL":
        return None
    try:
        return Decimal(value.strip("'"))
    except Exception:
        return None


def _parse_dump_bool(value: str | None) -> bool:
    if not value or value == "NULL":
        return False
    return value.strip("'") in {"1", "true", "True"}


def _parse_dump_str(value: str | None) -> str | None:
    if not value or value == "NULL":
        return None
    return value.strip("'").replace("\\'", "'").replace("\\\\", "\\") or None


def _split_row_tuples(values_str: str) -> list[str]:
    rows: list[str] = []
    current = ""
    depth = 0
    in_quote = False
    previous = ""

    for char in values_str:
        if char == "'" and previous != "\\":
            in_quote = not in_quote

        if not in_quote and char == "(":
            depth += 1
            if depth == 1:
                previous = char
                continue

        if not in_quote and char == ")":
            depth -= 1
            if depth == 0:
                rows.append(current)
                current = ""
                previous = char
                continue

        if depth >= 1:
            current += char

        previous = char

    return rows


def _split_values(values_str: str) -> list[str]:
    values: list[str] = []
    current = ""
    in_quote = False
    previous = ""

    for char in values_str:
        if char == "'" and previous != "\\":
            in_quote = not in_quote
            current += char
            previous = char
            continue

        if char == "," and not in_quote:
            values.append(current.strip())
            current = ""
            previous = char
            continue

        current += char
        previous = char

    if current:
        values.append(current.strip())
    return values


def _build_snapshot(
    *,
    manual_status: str | None,
    esperado_manual: Decimal | None,
    recebido_manual: Decimal | None,
    manual_paid_at: datetime | None,
    manual_forma_pagamento: str | None,
    manual_comprovante_path: str | None,
    agente_refi_solicitado: bool,
) -> LegacyPagamentoSnapshot:
    return LegacyPagamentoSnapshot(
        manual_status=manual_status,
        esperado_manual=esperado_manual,
        recebido_manual=recebido_manual,
        manual_paid_at=manual_paid_at,
        manual_forma_pagamento=manual_forma_pagamento,
        manual_comprovante_path=manual_comprovante_path,
        agente_refi_solicitado=agente_refi_solicitado,
    )


def _snapshot_sort_key(
    *,
    manual_paid_at: datetime | None,
    updated_at: datetime | None,
    created_at: datetime | None,
    row_id: int,
) -> tuple[datetime, int]:
    return (
        manual_paid_at or updated_at or created_at or datetime.min,
        row_id,
    )


def list_legacy_pagamento_snapshots_from_dump(
    *,
    dump_path: str | Path,
    competencia: date | None = None,
) -> dict[tuple[str, date], LegacyPagamentoSnapshot]:
    sql_text = Path(dump_path).read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(LEGACY_PAGAMENTOS_TABLE) + r"`\s*"
        r"\(([^)]+)\)\s*VALUES\s*([\s\S]+?);",
        re.IGNORECASE,
    )

    snapshots: dict[tuple[str, date], tuple[tuple[datetime, int], LegacyPagamentoSnapshot]] = {}
    for match in pattern.finditer(sql_text):
        columns = [column.strip().strip("`") for column in match.group(1).split(",")]
        for row_raw in _split_row_tuples(match.group(2)):
            raw_values = _split_values(row_raw)
            if len(raw_values) != len(columns):
                continue
            row = dict(zip(columns, raw_values))

            referencia = _parse_dump_date(row.get("referencia_month"))
            if referencia is None:
                continue
            if competencia and referencia != competencia:
                continue

            snapshot = _build_snapshot(
                manual_status=_parse_dump_str(row.get("manual_status")),
                esperado_manual=_parse_dump_decimal(row.get("esperado_manual")),
                recebido_manual=_parse_dump_decimal(row.get("recebido_manual")),
                manual_paid_at=_parse_dump_datetime(row.get("manual_paid_at")),
                manual_forma_pagamento=_parse_dump_str(row.get("manual_forma_pagamento")),
                manual_comprovante_path=_parse_dump_str(row.get("manual_comprovante_path")),
                agente_refi_solicitado=_parse_dump_bool(row.get("agente_refi_solicitado")),
            )
            if not snapshot.has_manual_context():
                continue

            cpf = _normalize_cpf(_parse_dump_str(row.get("cpf_cnpj")))
            if not cpf:
                continue

            sort_key = _snapshot_sort_key(
                manual_paid_at=snapshot.manual_paid_at,
                updated_at=_parse_dump_datetime(row.get("updated_at")),
                created_at=_parse_dump_datetime(row.get("created_at")),
                row_id=int((row.get("id") or "0").strip("'") or 0),
            )
            current = snapshots.get((cpf, referencia))
            if current is None or sort_key >= current[0]:
                snapshots[(cpf, referencia)] = (sort_key, snapshot)

    return {
        key: snapshot
        for key, (_sort_key, snapshot) in snapshots.items()
    }


def list_legacy_pagamento_snapshots(*, competencia: date) -> dict[str, LegacyPagamentoSnapshot]:
    if not _legacy_table_exists():
        return {}

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    cpf_cnpj,
                    manual_status,
                    esperado_manual,
                    recebido_manual,
                    manual_paid_at,
                    manual_forma_pagamento,
                    manual_comprovante_path,
                    agente_refi_solicitado
                FROM {LEGACY_PAGAMENTOS_TABLE}
                WHERE referencia_month = %s
                """,
                [competencia],
            )
            rows = cursor.fetchall()
    except DatabaseError:
        return {}

    snapshots: dict[str, LegacyPagamentoSnapshot] = {}
    for row in rows:
        snapshot = _build_snapshot(
            manual_status=row[1] or None,
            esperado_manual=row[2],
            recebido_manual=row[3],
            manual_paid_at=row[4],
            manual_forma_pagamento=row[5] or None,
            manual_comprovante_path=row[6] or None,
            agente_refi_solicitado=bool(row[7]),
        )
        if not snapshot.has_manual_context():
            continue

        cpf = _normalize_cpf(row[0])
        if cpf:
            snapshots[cpf] = snapshot

    return snapshots
