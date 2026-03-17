from __future__ import annotations

from abc import ABC, abstractmethod

from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Contrato

from .payment_rules import has_active_refinanciamento
from .models import Refinanciamento


class EligibilityStrategy(ABC):
    @abstractmethod
    def evaluate(self, contrato: Contrato) -> dict[str, object]:
        raise NotImplementedError


class StandardEligibilityStrategy(EligibilityStrategy):
    def evaluate(self, contrato: Contrato) -> dict[str, object]:
        projection = build_contract_cycle_projection(contrato)
        ciclos = list(sorted(projection["cycles"], key=lambda item: item["numero"]))
        if not ciclos:
            return {
                "elegivel": False,
                "motivo": "Nenhum ciclo encontrado para o contrato.",
                "parcelas_pagas": 0,
                "mensalidades_livres": 0,
                "tem_refinanciamento_ativo": False,
            }

        total_parcelas = get_contract_cycle_size(contrato)
        ciclo_atual = ciclos[-1]
        parcelas_pagas = sum(
            1
            for parcela in ciclo_atual["parcelas"]
            if parcela["status"] == "descontado"
        )
        mensalidades_livres = parcelas_pagas
        status_renovacao = projection["status_renovacao"]
        tem_refinanciamento_ativo = bool(status_renovacao) and status_renovacao != Refinanciamento.Status.APTO_A_RENOVAR

        if tem_refinanciamento_ativo or has_active_refinanciamento(contrato):
            return {
                "elegivel": False,
                "motivo": "CPF já possui renovação em andamento.",
                "parcelas_pagas": parcelas_pagas,
                "mensalidades_livres": mensalidades_livres,
                "tem_refinanciamento_ativo": True,
            }

        limiar = max(total_parcelas - 1, 1)
        if parcelas_pagas < limiar:
            return {
                "elegivel": False,
                "motivo": (
                    f"Apenas {parcelas_pagas}/{total_parcelas} parcelas do ciclo atual foram quitadas."
                ),
                "parcelas_pagas": parcelas_pagas,
                "mensalidades_livres": mensalidades_livres,
                "tem_refinanciamento_ativo": False,
            }

        return {
            "elegivel": True,
            "motivo": (
                "Apto a renovar "
                f"({parcelas_pagas}/{total_parcelas} parcelas quitadas)."
            ),
            "parcelas_pagas": parcelas_pagas,
            "mensalidades_livres": mensalidades_livres,
            "tem_refinanciamento_ativo": False,
        }
