from __future__ import annotations

import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path


def fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


def normalize_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n").split("\n")


def parse_referencia_header(text: str) -> str | None:
    """Extrai 'YYYY-MM-01' do cabeçalho.
    Equivalente ao parseAbaseReferencia do PHP AdminController.
    Busca 'Referência: MM/YYYY' ou fallback MM/YYYY em qualquer linha.
    """
    match = re.search(r"Refer[eê]ncia:\s*(\d{2})\s*/\s*(20\d{2})", text, re.IGNORECASE)
    if match:
        mm, yy = int(match.group(1)), int(match.group(2))
        return f"{yy:04d}-{mm:02d}-01"
    match = re.search(r"\b([01]\d)\s*/\s*(20\d{2})\b", text)
    if match:
        mm, yy = int(match.group(1)), int(match.group(2))
        return f"{yy:04d}-{mm:02d}-01"
    return None


_LINHA_IGNORE_KEYWORDS = (
    "governo do estado",
    "empresa de tecnologia",
    "relatorio dos lancamentos",
    "entidade:",
    "status matricula",
    "legenda do status",
    "total do status:",
    "orgao pagamento:",
)

_LINHA_STATUS_RE = re.compile(r"^[1-6S]$", re.IGNORECASE)
_LINHA_CPF_RE = re.compile(r"^\d{11}$")
_LINHA_MONEY_RE = re.compile(r"[^\d,.\-]+")


def _looks_like_money_token(value: str) -> bool:
    token = (value or "").strip()
    if not token:
        return False
    return "," in token or "." in token


def parse_linha_spacesplit(line: str) -> dict | None:
    """Interpreta uma linha usando split por 2+ espaços.
    Equivalente ao parseAbaseLinha do PHP AdminController.

    Retorna dict com: status_code, matricula, nome, valor, orgao_pagto, cpf
    ou None se a linha deve ser ignorada.
    """
    line = line.strip()
    if not line:
        return None

    folded = fold_text(line)
    for kw in _LINHA_IGNORE_KEYWORDS:
        if kw in folded:
            return None
    if set(line.strip()) == {"="}:
        return None

    parts = re.split(r"\s{2,}", line)
    parts = [p for p in parts if p]
    if len(parts) < 5:
        return None

    cpf_tok = parts[-1]
    if not _LINHA_CPF_RE.match(re.sub(r"\D", "", cpf_tok)):
        return None
    cpf = re.sub(r"\D", "", cpf_tok)

    right_before_cpf = parts[-2]
    if _looks_like_money_token(right_before_cpf):
        orgao_tok = ""
        valor_tok = right_before_cpf
    else:
        if len(parts) < 6:
            return None
        orgao_tok = right_before_cpf
        valor_tok = parts[-3]
    status_tok = parts[0].strip().upper()
    if not _LINHA_STATUS_RE.match(status_tok):
        return None

    mat_tok = parts[1] if len(parts) > 1 else ""
    nome_tok = parts[2] if len(parts) > 2 else ""

    # parse valor
    v = _LINHA_MONEY_RE.sub("", valor_tok)
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(v) if v else None
    except InvalidOperation:
        valor = None
    if valor is None:
        return None

    return {
        "status_code": status_tok,
        "matricula": mat_tok.strip(),
        "nome": nome_tok.strip(),
        "valor": valor,
        "orgao_pagto": orgao_tok.strip(),
        "cpf": cpf,
    }


@dataclass(slots=True)
class RetornoMeta:
    competencia: str
    data_geracao: str
    entidade: str
    sistema_origem: str = "ETIPI/iNETConsig"


@dataclass(slots=True)
class ParsedRetorno:
    meta: RetornoMeta
    items: list[dict]
    warnings: list[dict] = field(default_factory=list)
    encoding: str = "latin-1"


class ParseStrategy(ABC):
    @abstractmethod
    def parse(self, arquivo_path: str) -> ParsedRetorno:
        raise NotImplementedError


class ETIPITxtRetornoParser(ParseStrategy):
    STATUS_CATEGORY_MAP = {
        "1": "efetivado",
        "2": "rejeitado",
        "3": "rejeitado",
        "4": "pendente",
        "5": "pendente",
        "6": "pendente",
        "S": "rejeitado",
    }
    DEFAULT_STATUS_DESCRIPTION_MAP = {
        "1": "Lançado e Efetivado",
        "2": "Não Lançado por Falta de Margem Temporariamente",
        "3": "Não Lançado por Outros Motivos",
        "4": "Lançado com Valor Diferente",
        "5": "Não Lançado por Problemas Técnicos",
        "6": "Lançamento com Erros",
        "S": "Não Lançado: Compra de Dívida ou Suspensão SEAD",
    }

    ENCODINGS = ("latin-1", "iso-8859-1", "cp1252", "utf-8")
    HEADER_PATTERN = re.compile(
        r"Entidade:\s*(?P<entidade>.*?)\s+Refer[^\d]*(?P<competencia>\d{2}/\d{4})\s+Data da Gera[^\d]*(?P<data>\d{2}/\d{2}/\d{4})",
        re.IGNORECASE,
    )
    ORGAO_PATTERN = re.compile(
        r"Org[aã]o Pagamento:\s*(?P<codigo>\d+)-(?P<nome>.+?)\s+-\s+\d+\s+Lan",
        re.IGNORECASE,
    )
    STATUS_LEGEND_PATTERN = re.compile(r"^\s*([1-6S])\s*-\s*(.+?)\s*$", re.IGNORECASE)

    STATUS_SLICE = slice(0, 7)
    MATRICULA_SLICE = slice(7, 17)
    NOME_SLICE = slice(17, 48)
    CARGO_SLICE = slice(48, 79)
    FIN_SLICE = slice(79, 84)
    ORGAO_SLICE = slice(84, 90)
    LANCAMENTO_SLICE = slice(90, 97)
    TOTAL_PAGO_SLICE = slice(97, 109)
    VALOR_SLICE = slice(109, 122)
    ORGAO_PAGTO_SLICE = slice(122, 134)
    CPF_SLICE = slice(134, None)

    @classmethod
    def decode_bytes(cls, raw_bytes: bytes) -> tuple[str, str]:
        fallback: tuple[str, str] | None = None
        for encoding in cls.ENCODINGS:
            try:
                decoded = raw_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
            if fallback is None:
                fallback = (decoded, encoding)
            folded = fold_text(decoded)
            if "entidade:" in folded and "referencia:" in folded and "status matricula" in folded:
                return decoded, encoding
        if fallback is not None:
            return fallback
        return raw_bytes.decode("latin-1", errors="replace"), "latin-1"

    @classmethod
    def extract_meta(cls, lines: list[str]) -> RetornoMeta:
        # Tentativa 1: padrão completo ETIPI (entidade + referência + data na mesma linha)
        for line in lines:
            match = cls.HEADER_PATTERN.search(line)
            if match:
                return RetornoMeta(
                    competencia=match.group("competencia"),
                    data_geracao=match.group("data"),
                    entidade=match.group("entidade").strip(),
                )

        # Tentativa 2: regex flexível estilo PHP parseAbaseReferencia
        # Varre as primeiras 40 linhas em busca de "Referência: MM/YYYY"
        header_text = "\n".join(lines[:40])
        ref_ymd = parse_referencia_header(header_text)
        if ref_ymd:
            # Extrai mês/ano no formato MM/YYYY para competência
            yy, mm, _ = ref_ymd.split("-")
            competencia = f"{mm}/{yy}"

            # Tenta extrair entidade separadamente
            entidade = ""
            for line in lines[:40]:
                m = re.search(r"Entidade:\s*(.+)", line, re.IGNORECASE)
                if m:
                    entidade = m.group(1).strip()
                    break

            # Tenta extrair data de geração
            data_geracao = ""
            for line in lines[:40]:
                m = re.search(r"Data da Gera[^\d]*(\d{2}/\d{2}/\d{4})", line, re.IGNORECASE)
                if m:
                    data_geracao = m.group(1)
                    break

            return RetornoMeta(
                competencia=competencia,
                data_geracao=data_geracao,
                entidade=entidade,
            )

        raise ValueError("Cabeçalho ETIPI com entidade e referência não encontrado.")

    def parse(self, arquivo_path: str) -> ParsedRetorno:
        raw_bytes = Path(arquivo_path).read_bytes()
        text, encoding = self.decode_bytes(raw_bytes)
        lines = normalize_lines(text)
        meta = self.extract_meta(lines)
        status_legend = self._extract_status_legend(lines)

        items: list[dict] = []
        warnings: list[dict] = []
        bloco_atual: list[dict] = []
        in_legend = False

        for linha_numero, line in enumerate(lines, start=1):
            stripped = line.rstrip()
            folded = fold_text(stripped).strip()

            if not stripped:
                continue

            if self._is_block_boundary(folded):
                if bloco_atual:
                    items.extend(bloco_atual)
                    bloco_atual = []
                continue

            if bloco_atual and (
                folded.startswith("governo do estado")
                or folded.startswith("entidade:")
                or folded.startswith("status matricula")
            ):
                items.extend(bloco_atual)
                bloco_atual = []

            if "legenda do status" in folded:
                if bloco_atual:
                    items.extend(bloco_atual)
                    bloco_atual = []
                in_legend = True
                continue

            if in_legend:
                continue

            if self._is_noise_line(stripped, folded):
                continue

            orgao_info = self._parse_orgao_pagamento(stripped)
            if orgao_info:
                for item in bloco_atual:
                    item["orgao_pagto_codigo"] = orgao_info["codigo"]
                    item["orgao_pagto_nome"] = orgao_info["nome"]
                    item["payload_bruto"]["orgao_pagto_bloco"] = orgao_info
                items.extend(bloco_atual)
                bloco_atual = []
                continue

            legacy_row = parse_linha_spacesplit(stripped)
            if legacy_row and self._prefer_legacy_parse(stripped):
                try:
                    bloco_atual.append(
                        self._parse_detail_line_legacy(
                            line=stripped,
                            legacy_row=legacy_row,
                            linha_numero=linha_numero,
                            competencia=meta.competencia,
                            status_legend=status_legend,
                        )
                    )
                except ValueError as exc:
                    warnings.append(
                        {
                            "linha_numero": linha_numero,
                            "erro": str(exc),
                            "conteudo": stripped,
                        }
                    )
                continue

            if not self._is_detail_line(stripped):
                continue

            try:
                bloco_atual.append(
                    self._parse_detail_line(
                        line=stripped,
                        linha_numero=linha_numero,
                        competencia=meta.competencia,
                        status_legend=status_legend,
                    )
                )
            except ValueError as exc:
                warnings.append(
                    {
                        "linha_numero": linha_numero,
                        "erro": str(exc),
                        "conteudo": stripped,
                    }
                )

        if bloco_atual:
            items.extend(bloco_atual)

        # Fallback: se o parser fixed-width não encontrou itens, tenta space-split (estilo PHP)
        if not items:
            items, warnings = self._parse_spacesplit_fallback(
                lines,
                meta.competencia,
                warnings,
                status_legend,
            )

        return ParsedRetorno(meta=meta, items=items, warnings=warnings, encoding=encoding)

    def _parse_spacesplit_fallback(
        self,
        lines: list[str],
        competencia: str,
        warnings: list[dict],
        status_legend: dict[str, str],
    ) -> tuple[list[dict], list[dict]]:
        """Fallback que usa parse_linha_spacesplit (estilo PHP parseAbaseLinha).
        Ativado quando o parser fixed-width ETIPI não encontra nenhum item.
        """
        items: list[dict] = []
        for linha_numero, line in enumerate(lines, start=1):
            row = parse_linha_spacesplit(line)
            if not row:
                continue
            try:
                status_desconto = self.STATUS_CATEGORY_MAP.get(row["status_code"], "pendente")
                status_descricao = status_legend.get(row["status_code"], "Status desconhecido")
                valor = row["valor"]
                items.append({
                    "linha_numero": linha_numero,
                    "cpf_cnpj": row["cpf"],
                    "matricula_servidor": row["matricula"],
                    "nome_servidor": row["nome"].upper(),
                    "cargo": "-",
                    "competencia": competencia,
                    "valor_descontado": valor,
                    "status_codigo": row["status_code"],
                    "status_desconto": status_desconto,
                    "status_descricao": status_descricao,
                    "motivo_rejeicao": status_descricao if status_desconto == "rejeitado" else None,
                    "orgao_codigo": "",
                    "orgao_pagto_codigo": row["orgao_pagto"],
                    "orgao_pagto_nome": "",
                    "payload_bruto": {
                        "status_codigo": row["status_code"],
                        "matricula": row["matricula"],
                        "nome": row["nome"],
                        "valor": str(valor),
                        "orgao_pagto": row["orgao_pagto"],
                        "cpf": row["cpf"],
                        "_parser": "spacesplit",
                    },
                })
            except Exception as exc:
                warnings.append({
                    "linha_numero": linha_numero,
                    "erro": str(exc),
                    "conteudo": line.rstrip(),
                })
        return items, warnings

    def _extract_status_legend(self, lines: list[str]) -> dict[str, str]:
        status_legend = dict(self.DEFAULT_STATUS_DESCRIPTION_MAP)
        in_legend = False

        for line in lines:
            folded = fold_text(line).strip()
            if "legenda do status" in folded:
                in_legend = True
                continue

            if not in_legend:
                continue

            match = self.STATUS_LEGEND_PATTERN.match(line)
            if not match:
                continue

            status_legend[match.group(1).upper()] = match.group(2).strip()

        return status_legend

    def _is_noise_line(self, line: str, folded: str) -> bool:
        return any(
            (
                folded.startswith("governo do estado"),
                folded.startswith("empresa de tecnologia"),
                folded.startswith("relatorio dos lancamentos"),
                folded.startswith("entidade:"),
                folded.startswith("status matricula"),
                set(line.strip()) == {"="},
                folded.startswith("1 - lancado"),
                folded.startswith("2 - nao lancado"),
                folded.startswith("3 - nao lancado"),
                folded.startswith("4 - lancado"),
                folded.startswith("5 - nao lancado"),
                folded.startswith("6 - lancamento"),
                folded.startswith("s - nao lancado"),
                "pag:" in folded,
            )
        )

    def _is_block_boundary(self, folded: str) -> bool:
        return folded.startswith("total do status:") or folded.startswith("---------------------------------------------------------------------------------")

    def _parse_orgao_pagamento(self, line: str) -> dict[str, str] | None:
        folded = fold_text(line)
        if "orgao pagamento:" not in folded:
            return None
        try:
            payload = line.split(":", 1)[1].strip()
            codigo, remainder = payload.split("-", 1)
        except (IndexError, ValueError):
            return None

        nome = remainder
        for marker in (" -  ", " - "):
            if marker in remainder:
                nome = remainder.split(marker, 1)[0]
                break

        return {"codigo": codigo.strip(), "nome": nome.strip()}

    def _is_detail_line(self, line: str) -> bool:
        status_code = line[self.STATUS_SLICE].strip().upper()
        cpf = re.sub(r"\D", "", line[self.CPF_SLICE].strip())
        return status_code in self.STATUS_CATEGORY_MAP and len(cpf) == 11

    def _prefer_legacy_parse(self, line: str) -> bool:
        payload = self._build_fixed_width_payload(line)
        return "," in payload["valor_fixed_width"]

    def _build_fixed_width_payload(self, line: str) -> dict[str, str]:
        padded = line.ljust(self.CPF_SLICE.start)
        return {
            "status_codigo": padded[self.STATUS_SLICE].strip().upper(),
            "matricula": padded[self.MATRICULA_SLICE].strip(),
            "nome": padded[self.NOME_SLICE].rstrip(),
            "cargo": padded[self.CARGO_SLICE].rstrip(),
            "financiador": padded[self.FIN_SLICE].strip(),
            "orgao_codigo": padded[self.ORGAO_SLICE].strip(),
            "lancamento": padded[self.LANCAMENTO_SLICE].strip(),
            "total_pago": padded[self.TOTAL_PAGO_SLICE].strip(),
            "valor_fixed_width": padded[self.VALOR_SLICE].strip(),
            "orgao_pagto_codigo_fixed_width": padded[self.ORGAO_PAGTO_SLICE].strip(),
            "cpf": re.sub(r"\D", "", padded[self.CPF_SLICE].strip()),
        }

    def _parse_detail_line_legacy(
        self,
        *,
        line: str,
        legacy_row: dict,
        linha_numero: int,
        competencia: str,
        status_legend: dict[str, str],
    ) -> dict:
        status_codigo = legacy_row["status_code"].upper()
        if status_codigo not in self.STATUS_CATEGORY_MAP:
            raise ValueError(f"Status ETIPI inválido: {status_codigo!r}")

        payload = self._build_fixed_width_payload(line)
        status_desconto = self.STATUS_CATEGORY_MAP[status_codigo]
        status_descricao = status_legend.get(status_codigo, "Status desconhecido")
        orgao_pagto_codigo = legacy_row["orgao_pagto"] or payload["orgao_pagto_codigo_fixed_width"]

        payload.update(
            {
                "valor_legacy": str(legacy_row["valor"]),
                "orgao_pagto_legacy": legacy_row["orgao_pagto"],
                "_parser": "legacy_spacesplit",
            }
        )

        return {
            "linha_numero": linha_numero,
            "cpf_cnpj": legacy_row["cpf"],
            "matricula_servidor": legacy_row["matricula"],
            "nome_servidor": legacy_row["nome"].strip().upper(),
            "cargo": payload["cargo"].strip() or "-",
            "competencia": competencia,
            "valor_descontado": legacy_row["valor"],
            "status_codigo": status_codigo,
            "status_desconto": status_desconto,
            "status_descricao": status_descricao,
            "motivo_rejeicao": status_descricao if status_desconto == "rejeitado" else None,
            "orgao_codigo": payload["orgao_codigo"],
            "orgao_pagto_codigo": orgao_pagto_codigo,
            "orgao_pagto_nome": "",
            "payload_bruto": payload,
        }

    def _parse_detail_line(
        self,
        line: str,
        linha_numero: int,
        competencia: str,
        status_legend: dict[str, str],
    ) -> dict:
        payload = self._build_fixed_width_payload(line)
        status_codigo = payload["status_codigo"]
        if status_codigo not in self.STATUS_CATEGORY_MAP:
            raise ValueError(f"Status ETIPI inválido: {status_codigo!r}")

        valor_raw = payload["valor_fixed_width"]
        try:
            valor = self._parse_decimal(valor_raw)
        except InvalidOperation as exc:
            raise ValueError(f"Valor inválido na linha {linha_numero}: {valor_raw!r}") from exc

        status_desconto = self.STATUS_CATEGORY_MAP[status_codigo]
        status_descricao = status_legend.get(status_codigo, "Status desconhecido")
        cpf = payload["cpf"]
        orgao_pagto_codigo = payload["orgao_pagto_codigo_fixed_width"]

        return {
            "linha_numero": linha_numero,
            "cpf_cnpj": cpf,
            "matricula_servidor": payload["matricula"],
            "nome_servidor": payload["nome"].strip().upper(),
            "cargo": payload["cargo"].strip() or "-",
            "competencia": competencia,
            "valor_descontado": valor,
            "status_codigo": status_codigo,
            "status_desconto": status_desconto,
            "status_descricao": status_descricao,
            "motivo_rejeicao": status_descricao if status_desconto == "rejeitado" else None,
            "orgao_codigo": payload["orgao_codigo"],
            "orgao_pagto_codigo": orgao_pagto_codigo,
            "orgao_pagto_nome": "",
            "payload_bruto": payload,
        }

    @staticmethod
    def _parse_decimal(value: str) -> Decimal:
        normalized = (value or "").strip()
        if not normalized:
            return Decimal("0")
        if "," in normalized:
            normalized = normalized.replace(".", "").replace(",", ".")
        return Decimal(normalized)
