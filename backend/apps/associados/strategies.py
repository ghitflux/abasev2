from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal, InvalidOperation

from rest_framework.exceptions import ValidationError

from .models import Associado, only_digits

VALID_PRAZO_ANTECIPACAO = {3, 4}
TAXA_ANTECIPACAO_PADRAO = Decimal("30.00")
DOACAO_ASSOCIADO_PERCENTUAL = Decimal("0.30")
PERCENTUAL_REPASSE_PADRAO = Decimal("10.00")


def validate_positive_mensalidade(value, *, field_name: str = "mensalidade"):
    mensalidade = Decimal(str(value or 0))
    if mensalidade <= 0:
        raise ValidationError(
            {field_name: "A mensalidade deve ser maior que zero."}
        )
    return mensalidade


def validate_prazo_meses(value, *, field_name: str = "prazo_meses") -> int:
    prazo_meses = int(value or 3)
    if prazo_meses not in VALID_PRAZO_ANTECIPACAO:
        raise ValidationError(
            {field_name: "O prazo do ciclo deve ser 3 ou 4 meses."}
        )
    return prazo_meses


def _parse_percentual_repasse(value) -> Decimal:
    if value in (None, ""):
        return PERCENTUAL_REPASSE_PADRAO
    try:
        percentual = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(
            {"percentual_repasse": "Informe um percentual válido."}
        ) from exc
    if percentual < 0:
        raise ValidationError(
            {"percentual_repasse": "Informe um percentual válido."}
        )
    return percentual


def calculate_contract_financials(
    *,
    mensalidade,
    prazo_meses,
    percentual_repasse=None,
) -> dict[str, Decimal | int]:
    mensalidade_decimal = validate_positive_mensalidade(
        mensalidade,
        field_name="mensalidade",
    )
    prazo_meses_value = validate_prazo_meses(prazo_meses)
    percentual_repasse_decimal = _parse_percentual_repasse(percentual_repasse)

    valor_total_antecipacao = (
        mensalidade_decimal * Decimal(prazo_meses_value)
    ).quantize(Decimal("0.01"))
    doacao_associado = (
        valor_total_antecipacao * DOACAO_ASSOCIADO_PERCENTUAL
    ).quantize(Decimal("0.01"))
    margem_disponivel = (
        valor_total_antecipacao - doacao_associado
    ).quantize(Decimal("0.01"))
    comissao_agente = (
        margem_disponivel * (percentual_repasse_decimal / Decimal("100"))
    ).quantize(Decimal("0.01"))

    return {
        "prazo_meses": prazo_meses_value,
        "taxa_antecipacao": TAXA_ANTECIPACAO_PADRAO,
        "valor_total_antecipacao": valor_total_antecipacao,
        "doacao_associado": doacao_associado,
        "margem_disponivel": margem_disponivel,
        "comissao_agente": comissao_agente,
    }


def build_duplicate_document_message(associado: Associado) -> str:
    agente = associado.agente_responsavel
    agente_nome = (
        agente.full_name
        if agente and agente.full_name
        else "agente não identificado"
    )
    return (
        "CPF/CNPJ já cadastrado no sistema. "
        f"Cadastro criado por {agente_nome}."
    )


class ValidationStrategy(ABC):
    """Strategy para validação de dados do associado conforme contexto."""

    @abstractmethod
    def validate(self, data: dict) -> dict:
        raise NotImplementedError


class CadastroValidationStrategy(ValidationStrategy):
    """Validação no momento do cadastro."""

    def validate(self, data):
        cpf_cnpj = only_digits(data.get("cpf_cnpj"))
        if not cpf_cnpj:
            raise ValidationError({"cpf_cnpj": "CPF/CNPJ é obrigatório."})
        if not data.get("nome_completo"):
            raise ValidationError({"nome_completo": "Nome completo é obrigatório."})
        associado_existente = (
            Associado.all_objects.select_related("agente_responsavel")
            .filter(cpf_cnpj=cpf_cnpj)
            .first()
        )
        if associado_existente:
            raise ValidationError(
                {"cpf_cnpj": build_duplicate_document_message(associado_existente)}
            )

        contrato = data.setdefault("contrato", {})
        contrato.update(
            calculate_contract_financials(
                mensalidade=contrato.get("mensalidade"),
                prazo_meses=contrato.get("prazo_meses"),
                percentual_repasse=contrato.get("percentual_repasse"),
            )
        )

        data["cpf_cnpj"] = cpf_cnpj
        data["tipo_documento"] = (
            Associado.TipoDocumento.CNPJ
            if len(cpf_cnpj) == 14
            else Associado.TipoDocumento.CPF
        )
        return data


class EdicaoValidationStrategy(ValidationStrategy):
    """Validação no momento da edição."""

    def validate(self, data):
        contrato = data.get("contrato")
        if isinstance(contrato, dict) and "valor_mensalidade" in contrato:
            validate_positive_mensalidade(
                contrato.get("valor_mensalidade"),
                field_name="mensalidade",
            )
        return data
