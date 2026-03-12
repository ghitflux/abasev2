from __future__ import annotations

from .models import Associado


class AssociadoFactory:
    """Factory para criação de diferentes tipos de associado."""

    @staticmethod
    def criar_pessoa_fisica(dados, agente):
        return Associado.objects.create(
            tipo_documento=Associado.TipoDocumento.CPF,
            agente_responsavel=agente,
            status=Associado.Status.EM_ANALISE,
            **dados,
        )

    @staticmethod
    def criar_pessoa_juridica(dados, agente):
        return Associado.objects.create(
            tipo_documento=Associado.TipoDocumento.CNPJ,
            agente_responsavel=agente,
            status=Associado.Status.EM_ANALISE,
            **dados,
        )
