from __future__ import annotations

from rest_framework import serializers

from .models import ArquivoRetorno, ArquivoRetornoItem


class ArquivoRetornoResumoSerializer(serializers.Serializer):
    competencia = serializers.CharField(required=False, allow_blank=True)
    data_geracao = serializers.CharField(required=False, allow_blank=True)
    entidade = serializers.CharField(required=False, allow_blank=True)
    sistema_origem = serializers.CharField(required=False, allow_blank=True)
    baixa_efetuada = serializers.IntegerField(required=False)
    nao_descontado = serializers.IntegerField(required=False)
    pendencias_manuais = serializers.IntegerField(required=False)
    nao_encontrado = serializers.IntegerField(required=False)
    erro = serializers.IntegerField(required=False)
    ciclo_aberto = serializers.IntegerField(required=False)
    encerramentos = serializers.IntegerField(required=False)
    novos_ciclos = serializers.IntegerField(required=False)
    efetivados = serializers.IntegerField(required=False)
    nao_descontados = serializers.IntegerField(required=False)
    cpfs_duplicados_arquivo = serializers.IntegerField(required=False)
    linhas_duplicadas_ignoradas = serializers.IntegerField(required=False)
    pm_cpfs_duplicados_arquivo = serializers.IntegerField(required=False)
    pm_linhas_duplicadas_ignoradas = serializers.IntegerField(required=False)


class ArquivoRetornoUploadSerializer(serializers.Serializer):
    arquivo = serializers.FileField()


class ArquivoRetornoItemSerializer(serializers.ModelSerializer):
    associado_nome = serializers.CharField(source="associado.nome_completo", read_only=True)
    contrato_codigo = serializers.CharField(source="parcela.ciclo.contrato.codigo", read_only=True)

    class Meta:
        model = ArquivoRetornoItem
        fields = [
            "id",
            "linha_numero",
            "cpf_cnpj",
            "matricula_servidor",
            "nome_servidor",
            "cargo",
            "competencia",
            "valor_descontado",
            "status_codigo",
            "status_desconto",
            "status_descricao",
            "motivo_rejeicao",
            "orgao_codigo",
            "orgao_pagto_codigo",
            "orgao_pagto_nome",
            "resultado_processamento",
            "observacao",
            "gerou_encerramento",
            "gerou_novo_ciclo",
            "associado_nome",
            "contrato_codigo",
        ]


class ArquivoRetornoListSerializer(serializers.ModelSerializer):
    competencia_display = serializers.SerializerMethodField()
    sistema_origem = serializers.CharField(source="orgao_origem", read_only=True)
    uploaded_by_nome = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    resumo = serializers.SerializerMethodField()

    class Meta:
        model = ArquivoRetorno
        fields = [
            "id",
            "arquivo_nome",
            "formato",
            "sistema_origem",
            "competencia",
            "competencia_display",
            "total_registros",
            "processados",
            "nao_encontrados",
            "erros",
            "status",
            "resumo",
            "uploaded_by_nome",
            "created_at",
            "processado_em",
        ]

    def get_competencia_display(self, obj: ArquivoRetorno) -> str:
        return obj.competencia.strftime("%m/%Y")

    def get_resumo(self, obj: ArquivoRetorno) -> dict:
        return ArquivoRetornoResumoSerializer(obj.resultado_resumo).data


class ArquivoRetornoDetailSerializer(ArquivoRetornoListSerializer):
    class Meta(ArquivoRetornoListSerializer.Meta):
        fields = ArquivoRetornoListSerializer.Meta.fields + ["arquivo_url"]
