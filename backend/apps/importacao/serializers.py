from __future__ import annotations

from rest_framework import serializers

from .financeiro import build_financeiro_payload, build_financeiro_resumo
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


class ArquivoRetornoFinanceiroGrupoSerializer(serializers.Serializer):
    esperado = serializers.DecimalField(max_digits=12, decimal_places=2)
    recebido = serializers.DecimalField(max_digits=12, decimal_places=2)
    ok = serializers.IntegerField()
    total = serializers.IntegerField()
    faltando = serializers.IntegerField()
    pendente = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentual = serializers.FloatField()


class ArquivoRetornoFinanceiroResumoSerializer(ArquivoRetornoFinanceiroGrupoSerializer):
    mensalidades = ArquivoRetornoFinanceiroGrupoSerializer()
    valores_30_50 = ArquivoRetornoFinanceiroGrupoSerializer()


class ArquivoRetornoFinanceiroItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    associado_id = serializers.IntegerField(required=False, allow_null=True)
    associado_nome = serializers.CharField()
    agente_responsavel = serializers.CharField(required=False, allow_blank=True)
    matricula = serializers.CharField(required=False, allow_blank=True)
    cpf_cnpj = serializers.CharField()
    valor = serializers.DecimalField(max_digits=12, decimal_places=2)
    esperado = serializers.DecimalField(max_digits=12, decimal_places=2)
    recebido = serializers.DecimalField(max_digits=12, decimal_places=2)
    status_code = serializers.CharField(required=False, allow_blank=True)
    status_label = serializers.CharField(required=False, allow_blank=True)
    ok = serializers.BooleanField()
    situacao_code = serializers.CharField()
    situacao_label = serializers.CharField()
    orgao_pagto = serializers.CharField(required=False, allow_blank=True)
    relatorio = serializers.CharField(required=False, allow_blank=True)
    manual_status = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    manual_valor = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    manual_forma_pagamento = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    manual_paid_at = serializers.DateTimeField(required=False, allow_null=True)
    manual_comprovante_path = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    categoria = serializers.CharField()


class ArquivoRetornoFinanceiroPayloadSerializer(serializers.Serializer):
    resumo = ArquivoRetornoFinanceiroResumoSerializer()
    rows = ArquivoRetornoFinanceiroItemSerializer(many=True)


class ArquivoRetornoUploadSerializer(serializers.Serializer):
    arquivo = serializers.FileField()


class ArquivoRetornoItemSerializer(serializers.ModelSerializer):
    associado_nome = serializers.CharField(source="associado.nome_completo", read_only=True)
    contrato_codigo = serializers.CharField(source="parcela.ciclo.contrato.codigo", read_only=True)
    associado_id = serializers.IntegerField(read_only=True)
    associado_matricula = serializers.SerializerMethodField()
    agente_responsavel = serializers.SerializerMethodField()

    def get_associado_matricula(self, obj: ArquivoRetornoItem) -> str:
        associado = obj.associado
        if associado:
            return associado.matricula_orgao or associado.matricula or obj.matricula_servidor
        return obj.matricula_servidor

    def get_agente_responsavel(self, obj: ArquivoRetornoItem) -> str:
        associado = obj.associado
        if associado and associado.agente_responsavel:
            return associado.agente_responsavel.full_name

        contrato = getattr(getattr(getattr(obj.parcela, "ciclo", None), "contrato", None), "agente", None)
        return contrato.full_name if contrato else ""

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
            "associado_id",
            "associado_nome",
            "associado_matricula",
            "agente_responsavel",
            "contrato_codigo",
        ]


class ArquivoRetornoListSerializer(serializers.ModelSerializer):
    competencia_display = serializers.SerializerMethodField()
    sistema_origem = serializers.CharField(source="orgao_origem", read_only=True)
    uploaded_by_nome = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    resumo = serializers.SerializerMethodField()
    financeiro = serializers.SerializerMethodField()

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
            "financeiro",
            "uploaded_by_nome",
            "created_at",
            "processado_em",
        ]

    def get_competencia_display(self, obj: ArquivoRetorno) -> str:
        return obj.competencia.strftime("%m/%Y")

    def get_resumo(self, obj: ArquivoRetorno) -> dict:
        return ArquivoRetornoResumoSerializer(obj.resultado_resumo).data

    def get_financeiro(self, obj: ArquivoRetorno) -> dict:
        cache = self.context.setdefault("_financeiro_cache", {})
        if obj.competencia not in cache:
            cache[obj.competencia] = build_financeiro_resumo(competencia=obj.competencia)
        return ArquivoRetornoFinanceiroResumoSerializer(cache[obj.competencia]).data


class ArquivoRetornoDetailSerializer(ArquivoRetornoListSerializer):
    class Meta(ArquivoRetornoListSerializer.Meta):
        fields = ArquivoRetornoListSerializer.Meta.fields + ["arquivo_url"]
