from __future__ import annotations

import django_filters

from .models import Associado


class AssociadoFilter(django_filters.FilterSet):
    """Filtros avançados para listagem de associados."""

    nome = django_filters.CharFilter(
        field_name="nome_completo",
        lookup_expr="icontains",
        help_text="Busca parcial por nome",
    )
    cpf_cnpj = django_filters.CharFilter(
        field_name="cpf_cnpj",
        lookup_expr="icontains",
        help_text="Busca parcial por CPF/CNPJ",
    )
    matricula = django_filters.CharFilter(
        field_name="matricula",
        lookup_expr="icontains",
    )
    status = django_filters.ChoiceFilter(
        choices=Associado.Status.choices,
        help_text="Filtrar por status do associado",
    )
    agente = django_filters.NumberFilter(
        field_name="agente_responsavel_id",
        help_text="Filtrar por ID do agente responsável",
    )
    orgao_publico = django_filters.CharFilter(
        field_name="orgao_publico",
        lookup_expr="icontains",
        help_text="Filtrar por órgão público",
    )
    data_cadastro_inicio = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__gte",
    )
    data_cadastro_fim = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="date__lte",
    )

    class Meta:
        model = Associado
        fields = [
            "nome",
            "cpf_cnpj",
            "matricula",
            "status",
            "agente",
            "orgao_publico",
            "data_cadastro_inicio",
            "data_cadastro_fim",
        ]
