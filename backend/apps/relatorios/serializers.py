from __future__ import annotations

from rest_framework import serializers

from .models import RelatorioGerado


class UltimaImportacaoResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    arquivo_nome = serializers.CharField()
    competencia = serializers.CharField()
    status = serializers.CharField()
    processado_em = serializers.DateTimeField(allow_null=True)


class RelatorioResumoSerializer(serializers.Serializer):
    associados_ativos = serializers.IntegerField()
    associados_em_analise = serializers.IntegerField()
    associados_inadimplentes = serializers.IntegerField()
    contratos_ativos = serializers.IntegerField()
    contratos_em_analise = serializers.IntegerField()
    pendencias_abertas = serializers.IntegerField()
    esteira_aguardando = serializers.IntegerField()
    refinanciamentos_pendentes = serializers.IntegerField()
    refinanciamentos_efetivados = serializers.IntegerField()
    importacoes_concluidas = serializers.IntegerField()
    baixas_mes = serializers.IntegerField()
    valor_baixado_mes = serializers.DecimalField(max_digits=12, decimal_places=2)
    ultima_importacao = UltimaImportacaoResumoSerializer(allow_null=True)


class RelatorioGeradoSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = RelatorioGerado
        fields = ["id", "nome", "formato", "created_at", "download_url"]

    def get_download_url(self, obj: RelatorioGerado) -> str:
        path = f"/api/v1/relatorios/{obj.pk}/download/"
        return path


class RelatorioExportarSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(
        choices=[
            ("associados", "Associados"),
            ("tesouraria", "Tesouraria"),
            ("refinanciamentos", "Refinanciamentos"),
            ("importacao", "Importacao"),
        ]
    )
    formato = serializers.ChoiceField(choices=[("csv", "CSV"), ("json", "JSON"), ("pdf", "PDF")])
