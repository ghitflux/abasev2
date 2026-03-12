from __future__ import annotations

from abc import ABC, abstractmethod

from apps.contratos.models import Ciclo, Contrato, Parcela

from .models import Refinanciamento


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

        parcelas_pagas = ciclo_atual.parcelas.filter(
            status=Parcela.Status.DESCONTADO
        ).count()
        mensalidades_livres = 3 if parcelas_pagas >= 3 else 0
        tem_refinanciamento_ativo = Refinanciamento.objects.filter(
            contrato_origem__associado__cpf_cnpj=contrato.associado.cpf_cnpj,
            status__in=[
                Refinanciamento.Status.PENDENTE_APTO,
                Refinanciamento.Status.CONCLUIDO,
                Refinanciamento.Status.EFETIVADO,
                Refinanciamento.Status.SOLICITADO,
                Refinanciamento.Status.EM_ANALISE,
                Refinanciamento.Status.APROVADO,
            ],
        ).exists()

        if tem_refinanciamento_ativo:
            return {
                "elegivel": False,
                "motivo": "CPF já possui refinanciamento ativo ou pendente.",
                "parcelas_pagas": parcelas_pagas,
                "mensalidades_livres": mensalidades_livres,
                "tem_refinanciamento_ativo": tem_refinanciamento_ativo,
            }

        if parcelas_pagas < 3:
            return {
                "elegivel": False,
                "motivo": f"Apenas {parcelas_pagas}/3 parcelas foram descontadas.",
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
