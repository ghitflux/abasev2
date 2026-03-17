from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

MONTHS_PT_BR = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass(frozen=True)
class ManualReturnRow:
    legacy_id: int
    nome: str
    cpf_cnpj: str
    esperado: Decimal
    recebido: Decimal
    situacao: str
    status: str
    paid_at: datetime


@dataclass(frozen=True)
class ManualReturnReport:
    competencia: date
    generated_at: datetime | None
    esperado_total: Decimal
    recebido_total: Decimal
    ok_total: int
    total: int
    rows: list[ManualReturnRow]


def _parse_decimal(value: str) -> Decimal:
    normalized = value.replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {value}") from exc


def _parse_competencia(line: str) -> date:
    match = re.search(
        r"Baixa do M[eê]s\s+([A-Za-zçÇãÃõÕ]+)\s+de\s+(\d{4})",
        line,
        flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError("Competência não encontrada no relatório manual.")
    month_name = match.group(1).strip().lower()
    month = MONTHS_PT_BR.get(month_name)
    if month is None:
        raise ValueError(f"Mês inválido no relatório manual: {match.group(1)}")
    return date(int(match.group(2)), month, 1)


def _parse_generated_at(line: str) -> datetime | None:
    match = re.search(r"Gerado em:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})", line)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%d/%m/%Y %H:%M")


def _parse_totals(line: str) -> tuple[Decimal, Decimal, int, int]:
    match = re.search(
        r"Esperado:\s*R\$\s*([\d\.\,]+)\s*\|\s*Recebido:\s*R\$\s*([\d\.\,]+)\s*\|\s*OK:\s*(\d+)\s*\|\s*Total:\s*(\d+)",
        line,
    )
    if not match:
        raise ValueError("Totais não encontrados no relatório manual.")
    return (
        _parse_decimal(match.group(1)),
        _parse_decimal(match.group(2)),
        int(match.group(3)),
        int(match.group(4)),
    )


def _normalize_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _row_buffers(lines: list[str]) -> list[str]:
    buffers: list[str] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("--- PAGE"):
            continue
        if line.startswith("Conferência (soma das linhas):") or line.startswith(
            "Diferença vs topo:"
        ) or line.startswith("Status:"):
            if current:
                buffers.append(" ".join(current))
                current = []
            continue
        if line.startswith("Baixa do Mês") or line.startswith("Gerado em:") or line.startswith(
            "Totais:"
        ) or line.startswith("ID Nome CPF"):
            continue
        if re.match(r"^\d{4}\b", line):
            if current:
                buffers.append(" ".join(current))
            current = [line]
            continue
        if current:
            current.append(line)
    if current:
        buffers.append(" ".join(current))
    return buffers


ROW_RE = re.compile(
    r"^(?P<id>\d+)\s+"
    r"(?P<nome>.+?)\s+"
    r"(?P<cpf>\d{11})\s+"
    r"R\$\s*(?P<esperado>[\d\.\,]+)\s+"
    r"R\$\s*(?P<recebido>[\d\.\,]+)\s+"
    r"(?P<situacao>[A-Z]+)\s+"
    r"(?P<status>[A-Z])\s+"
    r"(?P<data>\d{4}-\d{2}-\d{2})"
    r"(?:\s+(?P<hora>\d{2}:\d{2}:\d{2}))?$"
)


def parse_manual_report_text(text: str) -> ManualReturnReport:
    lines = _normalize_lines(text)
    if not lines:
        raise ValueError("Relatório manual vazio.")

    competencia = _parse_competencia(lines[0])
    generated_at = next(
        (_parse_generated_at(line) for line in lines if line.startswith("Gerado em:")),
        None,
    )
    totals_line = next((line for line in lines if line.startswith("Totais:")), "")
    esperado_total, recebido_total, ok_total, total = _parse_totals(totals_line)

    rows: list[ManualReturnRow] = []
    for buffer in _row_buffers(lines):
        match = ROW_RE.match(re.sub(r"\s+", " ", buffer).strip())
        if not match:
            continue
        paid_at_raw = f"{match.group('data')} {match.group('hora') or '00:00:00'}"
        rows.append(
            ManualReturnRow(
                legacy_id=int(match.group("id")),
                nome=match.group("nome").strip(),
                cpf_cnpj=match.group("cpf"),
                esperado=_parse_decimal(match.group("esperado")),
                recebido=_parse_decimal(match.group("recebido")),
                situacao=match.group("situacao"),
                status=match.group("status"),
                paid_at=datetime.strptime(paid_at_raw, "%Y-%m-%d %H:%M:%S"),
            )
        )

    if len(rows) != total:
        raise ValueError(
            f"Quantidade de linhas divergente no relatório manual: esperado {total}, lido {len(rows)}."
        )

    return ManualReturnReport(
        competencia=competencia,
        generated_at=generated_at,
        esperado_total=esperado_total,
        recebido_total=recebido_total,
        ok_total=ok_total,
        total=total,
        rows=rows,
    )


def parse_manual_report_pdf(pdf_path: str | Path) -> ManualReturnReport:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "pypdf não está instalado no ambiente atual. Atualize as dependências do backend."
        ) from exc

    reader = PdfReader(str(Path(pdf_path).expanduser()))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return parse_manual_report_text(text)
