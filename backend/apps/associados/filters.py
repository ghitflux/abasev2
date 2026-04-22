from __future__ import annotations

import django_filters

from .filter_helpers import (
    mensalidade_in_selected_ranges,
    normalize_multi_value_list,
    parcelas_pagas_in_selected_ranges,
)
from .models import Associado
from .services import AssociadoService


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
    status = django_filters.CharFilter(
        method="filter_status",
        help_text="Filtrar por status do associado ou liquidado",
    )
    agente = django_filters.NumberFilter(
        field_name="agente_responsavel_id",
        help_text="Filtrar por ID do agente responsável",
    )
    numero_ciclos = django_filters.NumberFilter(
        method="filter_numero_ciclos",
        help_text="Filtrar pelo total exato de ciclos lógicos",
    )
    perfil_ciclo = django_filters.CharFilter(
        method="filter_perfil_ciclo",
        help_text="Filtrar por perfil de ciclo: novo ou renovado",
    )
    faixa_parcelas = django_filters.CharFilter(
        method="filter_faixa_parcelas",
        help_text="Filtrar por faixas de parcelas pagas: 1_parcela_paga ou 3_parcelas_pagas",
    )
    faixa_mensalidade = django_filters.CharFilter(
        method="filter_faixa_mensalidade",
        help_text="Filtrar por faixas de mensalidade, com suporte a múltiplos valores",
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
            "numero_ciclos",
            "perfil_ciclo",
            "faixa_parcelas",
            "faixa_mensalidade",
            "orgao_publico",
            "data_cadastro_inicio",
            "data_cadastro_fim",
        ]

    def _get_multi_values(self, name, value):
        request_values = []
        if hasattr(self.data, "getlist"):
            request_values = list(self.data.getlist(name))
        return normalize_multi_value_list(value, request_values=request_values)

    def filter_status(self, queryset, name, value):
        normalized = (value or "").strip().lower()
        if not normalized:
            return queryset
        valid_statuses = {choice[0] for choice in Associado.Status.choices}
        if normalized == "liquidado":
            return queryset.filter(contratos__status="encerrado").distinct()
        if normalized in valid_statuses:
            return queryset.filter(status=normalized)
        return queryset

    def filter_numero_ciclos(self, queryset, name, value):
        if value in (None, ""):
            return queryset
        associados = list(queryset.distinct())
        filtered_ids = [
            associado.id
            for associado in associados
            if AssociadoService.total_ciclos_logicos(associado) == int(value)
        ]
        return queryset.filter(id__in=filtered_ids)

    def filter_perfil_ciclo(self, queryset, name, value):
        normalized = (value or "").strip().lower()
        if normalized not in {"novo", "renovado"}:
            return queryset
        associados = list(queryset.distinct())
        filtered_ids = []
        for associado in associados:
            renovado = AssociadoService.associado_eh_renovado(associado)
            if normalized == "renovado" and renovado:
                filtered_ids.append(associado.id)
            if normalized == "novo" and not renovado:
                filtered_ids.append(associado.id)
        return queryset.filter(id__in=filtered_ids)

    def filter_faixa_parcelas(self, queryset, name, value):
        selected_ranges = self._get_multi_values(name, value)
        if not selected_ranges:
            return queryset
        associados = list(queryset.distinct())
        filtered_ids = []
        for associado in associados:
            contrato = AssociadoService.resolve_report_like_contract_for_associado(associado)
            if contrato is None:
                continue
            parcelas_pagas = AssociadoService.count_paid_parcelas_for_contract(contrato)
            if parcelas_pagas_in_selected_ranges(parcelas_pagas, selected_ranges):
                filtered_ids.append(associado.id)
        return queryset.filter(id__in=filtered_ids)

    def filter_faixa_mensalidade(self, queryset, name, value):
        selected_ranges = self._get_multi_values(name, value)
        if not selected_ranges:
            return queryset
        associados = list(queryset.distinct())
        filtered_ids = []
        for associado in associados:
            contrato = AssociadoService.resolve_report_like_contract_for_associado(associado)
            if contrato is None:
                continue
            if mensalidade_in_selected_ranges(
                contrato.valor_mensalidade or 0,
                selected_ranges,
            ):
                filtered_ids.append(associado.id)
        return queryset.filter(id__in=filtered_ids)
