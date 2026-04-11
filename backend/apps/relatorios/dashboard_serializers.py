from __future__ import annotations

from rest_framework import serializers


class DashboardMetricCardSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.CharField()
    numeric_value = serializers.FloatField()
    format = serializers.ChoiceField(choices=["integer", "currency"])
    tone = serializers.ChoiceField(choices=["neutral", "positive", "warning", "danger"])
    description = serializers.CharField(allow_blank=True)
    detail_metric = serializers.CharField()


class DashboardValuePointSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.IntegerField()
    detail_metric = serializers.CharField()


class DashboardPiePointSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.IntegerField()
    detail_metric = serializers.CharField()


class DashboardTrendPointSerializer(serializers.Serializer):
    bucket = serializers.CharField()
    label = serializers.CharField()
    cadastros = serializers.IntegerField()
    efetivados = serializers.IntegerField()
    renovacoes = serializers.IntegerField(required=False)
    cadastros_metric = serializers.CharField()
    efetivados_metric = serializers.CharField()
    renovacoes_metric = serializers.CharField(required=False)


class DashboardProjectionPointSerializer(serializers.Serializer):
    bucket = serializers.CharField()
    label = serializers.CharField()
    recebido = serializers.FloatField()
    projetado = serializers.FloatField()
    recebido_metric = serializers.CharField()
    projetado_metric = serializers.CharField()


class DashboardRadialPointSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.FloatField()
    detail_metric = serializers.CharField()


class DashboardAgentRankingSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    agent_name = serializers.CharField()
    volume_financeiro = serializers.FloatField()
    participacao_volume = serializers.FloatField()
    efetivados = serializers.IntegerField()
    cadastros = serializers.IntegerField()
    em_processo = serializers.IntegerField()
    renovados = serializers.IntegerField()
    aptos_renovar = serializers.IntegerField()
    inadimplentes = serializers.IntegerField()
    devolvidos = serializers.IntegerField()
    cadastrado = serializers.IntegerField()
    em_analise = serializers.IntegerField()
    pendente = serializers.IntegerField()
    ativo = serializers.IntegerField()
    inadimplente = serializers.IntegerField()
    inativo = serializers.IntegerField()
    participacao = serializers.FloatField()
    detail_metric = serializers.CharField()


class DashboardResumoGeralSerializer(serializers.Serializer):
    competencia = serializers.CharField()
    kpis = DashboardMetricCardSerializer(many=True)
    flow_bars = DashboardValuePointSerializer(many=True)
    status_pie = DashboardPiePointSerializer(many=True)
    trend_lines = DashboardTrendPointSerializer(many=True)


class DashboardTesourariaSerializer(serializers.Serializer):
    competencia = serializers.CharField()
    cards = DashboardMetricCardSerializer(many=True)
    projection_area = DashboardProjectionPointSerializer(many=True)
    movement_bars = DashboardValuePointSerializer(many=True)
    composition_radial = DashboardRadialPointSerializer(many=True)


class DashboardResumoMensalAssociacaoRowSerializer(serializers.Serializer):
    mes = serializers.DateField()
    complementos_receita = serializers.DecimalField(max_digits=15, decimal_places=2)
    saldo_positivo = serializers.DecimalField(max_digits=15, decimal_places=2)
    novos_associados = serializers.IntegerField()
    desvinculados = serializers.IntegerField()
    renovacoes_associado = serializers.IntegerField()


class DashboardResumoMensalAssociacaoSerializer(serializers.Serializer):
    competencia = serializers.CharField()
    rows = DashboardResumoMensalAssociacaoRowSerializer(many=True)


class DashboardNovosAssociadosSerializer(serializers.Serializer):
    date_start = serializers.DateField()
    date_end = serializers.DateField()
    cards = DashboardMetricCardSerializer(many=True)
    trend_area = DashboardTrendPointSerializer(many=True)
    status_pie = DashboardPiePointSerializer(many=True)


class DashboardAgentesSerializer(serializers.Serializer):
    competencia = serializers.CharField()
    date_start = serializers.DateField()
    date_end = serializers.DateField()
    cards = DashboardMetricCardSerializer(many=True)
    ranking = DashboardAgentRankingSerializer(many=True)


class DashboardDetailRowSerializer(serializers.Serializer):
    id = serializers.CharField()
    associado_id = serializers.IntegerField(required=False, allow_null=True)
    associado_nome = serializers.CharField(allow_blank=True)
    cpf_cnpj = serializers.CharField(allow_blank=True)
    matricula = serializers.CharField(allow_blank=True)
    data_nascimento = serializers.CharField(required=False, allow_blank=True)
    status = serializers.CharField(allow_blank=True)
    agente_nome = serializers.CharField(allow_blank=True)
    contrato_codigo = serializers.CharField(allow_blank=True)
    etapa = serializers.CharField(allow_blank=True)
    competencia = serializers.CharField(allow_blank=True)
    valor = serializers.CharField(allow_blank=True)
    valor_associado = serializers.CharField(allow_blank=True, required=False)
    valor_agente = serializers.CharField(allow_blank=True, required=False)
    valor_total = serializers.CharField(allow_blank=True, required=False)
    origem = serializers.CharField(allow_blank=True)
    data_referencia = serializers.CharField(allow_blank=True)
    observacao = serializers.CharField(allow_blank=True)
