from __future__ import annotations

from abc import ABC, abstractmethod

from apps.contratos.models import Ciclo, Contrato

from .payment_rules import (
    REFINANCIAMENTO_MENSALIDADES_NECESSARIAS,
    get_free_paid_pagamentos,
    has_active_refinanciamento,
)


class EligibilityStrategy(ABC):
    @abstractmethod
    def evaluate(self, contrato: Contrato) -> dict[str, object]:
        raise NotImplementedError


class StandardEligibilityStrategy(EligibilityStrategy):
    def evaluate(self, contrato: Contrato) -> dict[str, object]:
        ciclo_atual = (
            contrato.ciclos.exclude(status=Ciclo.Status.FUTURO).order_by("-numero").first()
            or contrato.ciclos.order_by("-numero").first()
        )
        if not ciclo_atual:
            return {
                "elegivel": False,
                "motivo": "Nenhum ciclo encontrado para o contrato.",
                "parcelas_pagas": 0,
                "mensalidades_livres": 0,
                "tem_refinanciamento_ativo": False,
            }

        pagamentos_livres = get_free_paid_pagamentos(contrato)
        parcelas_pagas = min(
            len(pagamentos_livres), REFINANCIAMENTO_MENSALIDADES_NECESSARIAS
        )
        mensalidades_livres = parcelas_pagas
        tem_refinanciamento_ativo = has_active_refinanciamento(contrato)

        if tem_refinanciamento_ativo:
            return {
                "elegivel": False,
                "motivo": "CPF já possui refinanciamento ativo ou pendente.",
                "parcelas_pagas": parcelas_pagas,
                "mensalidades_livres": mensalidades_livres,
                "tem_refinanciamento_ativo": tem_refinanciamento_ativo,
            }

        if len(pagamentos_livres) < REFINANCIAMENTO_MENSALIDADES_NECESSARIAS:
            return {
                "elegivel": False,
                "motivo": f"Apenas {parcelas_pagas}/3 pagamentos elegíveis foram identificados.",
                "parcelas_pagas": parcelas_pagas,
                "mensalidades_livres": mensalidades_livres,
                "tem_refinanciamento_ativo": tem_refinanciamento_ativo,
            }

        return {
            "elegivel": True,
            "motivo": "Apto a refinanciamento (3/3).",
            "parcelas_pagas": parcelas_pagas,
            "mensalidades_livres": mensalidades_livres,
            "tem_refinanciamento_ativo": tem_refinanciamento_ativo,
        }
