from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from rest_framework.exceptions import ValidationError

from .models import Associado, only_digits


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
        mensalidade = Decimal(str(contrato.get("mensalidade") or 0))
        prazo_meses = int(contrato.get("prazo_meses") or 3)
        taxa_antecipacao = Decimal("30.00")
        valor_total_antecipacao = (mensalidade * Decimal(prazo_meses)).quantize(
            Decimal("0.01")
        )
        doacao_associado = (
            valor_total_antecipacao * Decimal("0.30")
        ).quantize(Decimal("0.01"))

        contrato["prazo_meses"] = prazo_meses
        contrato["taxa_antecipacao"] = taxa_antecipacao
        contrato["margem_disponivel"] = (
            valor_total_antecipacao - doacao_associado
        ).quantize(Decimal("0.01"))
        contrato["doacao_associado"] = doacao_associado

        contrato["comissao_agente"] = (
            mensalidade * Decimal("0.10")
        ).quantize(Decimal("0.01"))
        contrato["valor_total_antecipacao"] = valor_total_antecipacao

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
        if "cpf_cnpj" in data:
            raise ValidationError({"cpf_cnpj": "CPF/CNPJ não pode ser alterado."})
        if "matricula" in data:
            raise ValidationError({"matricula": "Matrícula não pode ser alterada."})
        return data
