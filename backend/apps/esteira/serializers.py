from __future__ import annotations

from rest_framework import serializers

from .models import DocIssue, EsteiraItem, Pendencia, Transicao
from .services import EsteiraService


class SimpleUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class ContratoEsteiraSerializer(serializers.Serializer):
    codigo = serializers.CharField(read_only=True)
    associado_nome = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)


class DocumentoEsteiraSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    arquivo = serializers.FileField(read_only=True)
    observacao = serializers.CharField(read_only=True)


class PendenciaSerializer(serializers.ModelSerializer):
    associado_id = serializers.IntegerField(
        source="esteira_item.associado.id",
        read_only=True,
    )
    associado_nome = serializers.CharField(
        source="esteira_item.associado.nome_completo",
        read_only=True,
    )
    matricula = serializers.CharField(
        source="esteira_item.associado.matricula",
        read_only=True,
    )
    cpf_cnpj = serializers.CharField(
        source="esteira_item.associado.cpf_cnpj",
        read_only=True,
    )
    contrato_codigo = serializers.SerializerMethodField()

    class Meta:
        model = Pendencia
        fields = [
            "id",
            "tipo",
            "descricao",
            "status",
            "retornado_para_agente",
            "associado_id",
            "associado_nome",
            "matricula",
            "cpf_cnpj",
            "contrato_codigo",
            "created_at",
            "resolvida_em",
        ]

    def get_contrato_codigo(self, obj: Pendencia):
        contrato = obj.esteira_item.associado.contratos.order_by("-created_at").first()
        return contrato.codigo if contrato else None


class TransicaoSerializer(serializers.ModelSerializer):
    realizado_por = SimpleUserSerializer(read_only=True)

    class Meta:
        model = Transicao
        fields = [
            "id",
            "acao",
            "de_status",
            "para_status",
            "de_situacao",
            "para_situacao",
            "observacao",
            "realizado_em",
            "realizado_por",
        ]


class EsteiraListSerializer(serializers.ModelSerializer):
    ordem = serializers.IntegerField(source="prioridade", read_only=True)
    contrato = serializers.SerializerMethodField()
    data_assinatura = serializers.SerializerMethodField()
    valor_disponivel = serializers.SerializerMethodField()
    comissao_agente = serializers.SerializerMethodField()
    status_contrato = serializers.SerializerMethodField()
    status_documentacao = serializers.SerializerMethodField()
    contato_web = serializers.SerializerMethodField()
    termos_web = serializers.SerializerMethodField()
    agente = SimpleUserSerializer(source="associado.agente_responsavel", read_only=True)
    orgao_publico = serializers.SerializerMethodField()
    documentos_count = serializers.SerializerMethodField()
    acoes_disponiveis = serializers.SerializerMethodField()

    class Meta:
        model = EsteiraItem
        fields = [
            "id",
            "ordem",
            "contrato",
            "data_assinatura",
            "valor_disponivel",
            "comissao_agente",
            "status_contrato",
            "status_documentacao",
            "contato_web",
            "termos_web",
            "agente",
            "orgao_publico",
            "documentos_count",
            "acoes_disponiveis",
            "etapa_atual",
            "status",
            "assumido_em",
        ]

    def _get_contrato(self, obj: EsteiraItem):
        return obj.associado.contratos.order_by("-created_at").first()

    def get_contrato(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        if not contrato:
            return None
        return ContratoEsteiraSerializer(
            {
                "codigo": contrato.codigo,
                "associado_nome": obj.associado.nome_completo,
                "cpf_cnpj": obj.associado.cpf_cnpj,
                "matricula": obj.associado.matricula,
            }
        ).data

    def get_data_assinatura(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        return contrato.data_contrato if contrato else None

    def get_valor_disponivel(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        if not contrato:
            return None
        return contrato.margem_disponivel or contrato.valor_total_antecipacao

    def get_comissao_agente(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        return contrato.comissao_agente if contrato else None

    def get_status_contrato(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        return contrato.status if contrato else None

    def get_status_documentacao(self, obj: EsteiraItem):
        documentos = list(obj.associado.documentos.all())
        if any(pendencia.status == Pendencia.Status.ABERTA for pendencia in obj.pendencias.all()):
            return "reenvio_pendente"
        if any(
            issue.status == DocIssue.Status.INCOMPLETO
            for issue in obj.associado.doc_issues.all()
        ):
            return "reenvio_pendente"
        if not documentos:
            return "incompleta"
        return "completa"

    def get_contato_web(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        return bool(contrato and contrato.contato_web)

    def get_termos_web(self, obj: EsteiraItem):
        contrato = self._get_contrato(obj)
        return bool(contrato and contrato.termos_web)

    def get_orgao_publico(self, obj: EsteiraItem):
        return obj.associado.orgao_publico or getattr(
            obj.associado.contato_historico, "orgao_publico", ""
        )

    def get_documentos_count(self, obj: EsteiraItem):
        return obj.associado.documentos.count()

    def get_acoes_disponiveis(self, obj: EsteiraItem):
        return EsteiraService.TRANSICOES_VALIDAS.get((obj.etapa_atual, obj.status), [])


class EsteiraDetailSerializer(EsteiraListSerializer):
    documentos = serializers.SerializerMethodField()
    pendencias = PendenciaSerializer(many=True, read_only=True)
    transicoes = TransicaoSerializer(many=True, read_only=True)

    class Meta(EsteiraListSerializer.Meta):
        fields = EsteiraListSerializer.Meta.fields + [
            "documentos",
            "pendencias",
            "transicoes",
        ]

    def get_documentos(self, obj: EsteiraItem):
        return DocumentoEsteiraSerializer(obj.associado.documentos.all(), many=True).data


class PendenciaActionSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    descricao = serializers.CharField()


class SolicitarCorrecaoSerializer(serializers.Serializer):
    observacao = serializers.CharField()
