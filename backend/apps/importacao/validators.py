from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import re

from rest_framework.exceptions import ValidationError

from .parsers import ETIPITxtRetornoParser, fold_text


class ArquivoRetornoValidator:
    STATUS_CODES = set(ETIPITxtRetornoParser.STATUS_CATEGORY_MAP)

    @staticmethod
    def validar_formato(arquivo_nome: str) -> str:
        extensao = Path(arquivo_nome or "").suffix.lower()
        if extensao != ".txt":
            raise ValidationError({"arquivo": "Nesta semana o arquivo retorno deve ser .txt."})
        return "txt"

    @staticmethod
    def validar_tamanho(arquivo, max_mb: int = 20) -> int:
        size = getattr(arquivo, "size", 0) or 0
        if size <= 0:
            raise ValidationError({"arquivo": "O arquivo enviado está vazio."})
        limite = max_mb * 1024 * 1024
        if size > limite:
            raise ValidationError({"arquivo": f"O arquivo excede o limite de {max_mb} MB."})
        return size

    @staticmethod
    def validar_cabecalho(lines: list[str]) -> None:
        folded_lines = [fold_text(line) for line in lines]
        has_entidade = any("entidade:" in line and "referencia:" in line for line in folded_lines)
        has_colunas = any(
            "status matricula nome" in line and "orgao pagto cpf" in line
            for line in folded_lines
        )
        if not has_entidade or not has_colunas:
            raise ValidationError(
                {
                    "arquivo": (
                        "Cabeçalho ETIPI inválido. O arquivo precisa conter Entidade, "
                        "Referência e a linha de colunas STATUS/MATRICULA/CPF."
                    )
                }
            )

    @classmethod
    def validar_item(cls, item: dict) -> None:
        errors: dict[str, str] = {}

        if item.get("status_codigo") not in cls.STATUS_CODES:
            errors["status_codigo"] = "Código de status ETIPI inválido."

        cpf = re.sub(r"\D", "", str(item.get("cpf_cnpj", "")))
        if len(cpf) != 11:
            errors["cpf_cnpj"] = "CPF deve conter 11 dígitos."

        competencia = str(item.get("competencia", ""))
        try:
            datetime.strptime(competencia, "%m/%Y")
        except ValueError:
            errors["competencia"] = "Competência inválida. Use MM/YYYY."

        try:
            valor = Decimal(str(item.get("valor_descontado", "0")))
        except Exception:
            errors["valor_descontado"] = "Valor descontado inválido."
        else:
            if valor < 0:
                errors["valor_descontado"] = "Valor descontado não pode ser negativo."

        if errors:
            raise ValidationError(errors)
