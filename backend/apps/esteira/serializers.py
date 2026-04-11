from __future__ import annotations

from datetime import date
from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.associados.models import Documento
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.cycle_projection import get_contract_visual_status_payload
from core.file_references import build_storage_reference

from .models import DocIssue, EsteiraItem, Pendencia, Transicao
from .services import EsteiraService


class EsteiraSimpleUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class EsteiraAssociadoCompatSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome_completo = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)
    matricula_display = serializers.CharField(read_only=True)


class ContratoEsteiraSerializer(serializers.Serializer):
    codigo = serializers.CharField(read_only=True)
    associado_nome = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)
    matricula_display = serializers.CharField(read_only=True)
    valor_mensalidade = serializers.DecimalField(
        max_digits=12, decimal_places=2, allow_null=True, read_only=True
    )


class DocumentoEsteiraSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    arquivo = serializers.SerializerMethodField()
    arquivo_referencia = serializers.SerializerMethodField()
    arquivo_disponivel_localmente = serializers.SerializerMethodField()
    tipo_referencia = serializers.SerializerMethodField()
    observacao = serializers.CharField(read_only=True)
    nome_original = serializers.CharField(read_only=True)

    def _reference(self, obj):
        request = self.context.get("request")
        current_path = str(getattr(obj.arquivo, "name", "") or "")
        reference = build_storage_reference(
            current_path,
            request=request,
            missing_type="legado_sem_arquivo",
        )
        if obj.arquivo_referencia and obj.arquivo_referencia != reference.arquivo_referencia:
            return reference.__class__(
                url=reference.url,
                arquivo_referencia=obj.arquivo_referencia,
                arquivo_disponivel_localmente=reference.arquivo_disponivel_localmente,
                tipo_referencia=reference.tipo_referencia,
            )
        return reference

    def get_arquivo(self, obj) -> str:
        return str(getattr(obj.arquivo, "name", "") or "")

    def get_arquivo_referencia(self, obj) -> str:
        return self._reference(obj).arquivo_referencia

    def get_arquivo_disponivel_localmente(self, obj) -> bool:
        return self._reference(obj).arquivo_disponivel_localmente

    def get_tipo_referencia(self, obj) -> str:
        return self._reference(obj).tipo_referencia


class PendenciaSerializer(serializers.ModelSerializer):
    esteira_item_id = serializers.IntegerField(source="esteira_item.id", read_only=True)
    associado_created_at = serializers.DateTimeField(
        source="esteira_item.associado.created_at",
        read_only=True,
    )
    associado_id = serializers.IntegerField(
        source="esteira_item.associado.id",
        read_only=True,
    )
    associado_nome = serializers.CharField(
        source="esteira_item.associado.nome_completo",
        read_only=True,
    )
    matricula = serializers.SerializerMethodField()
    matricula_display = serializers.SerializerMethodField()
    cpf_cnpj = serializers.CharField(
        source="esteira_item.associado.cpf_cnpj",
        read_only=True,
    )
    contrato_codigo = serializers.SerializerMethodField()

    class Meta:
        model = Pendencia
        fields = [
            "id",
            "esteira_item_id",
            "associado_created_at",
            "tipo",
            "descricao",
            "status",
            "retornado_para_agente",
            "associado_id",
            "associado_nome",
            "matricula",
            "matricula_display",
            "cpf_cnpj",
            "contrato_codigo",
            "created_at",
            "resolvida_em",
        ]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_contrato_codigo(self, obj: Pendencia):
        contrato = resolve_operational_contract_for_associado(obj.esteira_item.associado)
        return contrato.codigo if contrato else None

    def get_matricula(self, obj: Pendencia) -> str:
        return obj.esteira_item.associado.matricula

    def get_matricula_display(self, obj: Pendencia) -> str:
        return obj.esteira_item.associado.matricula_display


class TransicaoSerializer(serializers.ModelSerializer):
    realizado_por = EsteiraSimpleUserSerializer(read_only=True)

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
    associado_id = serializers.IntegerField(source="associado.id", read_only=True)
    associado = EsteiraAssociadoCompatSerializer(read_only=True)
    ordem = serializers.IntegerField(source="prioridade", read_only=True)
    contrato = serializers.SerializerMethodField()
    data_assinatura = serializers.SerializerMethodField()
    valor_disponivel = serializers.SerializerMethodField()
    comissao_agente = serializers.SerializerMethodField()
    status_contrato = serializers.SerializerMethodField()
    status_contrato_visual_slug = serializers.SerializerMethodField()
    status_contrato_visual_label = serializers.SerializerMethodField()
    status_documentacao = serializers.SerializerMethodField()
    contato_web = serializers.SerializerMethodField()
    termos_web = serializers.SerializerMethodField()
    agente = EsteiraSimpleUserSerializer(
        source="associado.agente_responsavel",
        read_only=True,
    )
    analista_responsavel = EsteiraSimpleUserSerializer(read_only=True)
    orgao_publico = serializers.SerializerMethodField()
    documentos_count = serializers.SerializerMethodField()
    acoes_disponiveis = serializers.SerializerMethodField()

    class Meta:
        model = EsteiraItem
        fields = [
            "id",
            "associado_id",
            "associado",
            "ordem",
            "contrato",
            "data_assinatura",
            "valor_disponivel",
            "comissao_agente",
            "status_contrato",
            "status_contrato_visual_slug",
            "status_contrato_visual_label",
            "status_documentacao",
            "contato_web",
            "termos_web",
            "agente",
            "analista_responsavel",
            "orgao_publico",
            "documentos_count",
            "acoes_disponiveis",
            "etapa_atual",
            "status",
            "assumido_em",
        ]

    def _get_contrato(self, obj: EsteiraItem):
        return resolve_operational_contract_for_associado(obj.associado)

    @extend_schema_field(ContratoEsteiraSerializer(allow_null=True))
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
                "matricula_display": obj.associado.matricula_display,
                "valor_mensalidade": contrato.valor_mensalidade,
            }
        ).data

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_data_assinatura(self, obj: EsteiraItem) -> date | None:
        contrato = self._get_contrato(obj)
        return contrato.data_contrato if contrato else None

    @extend_schema_field(
        serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    )
    def get_valor_disponivel(self, obj: EsteiraItem) -> Decimal | None:
        contrato = self._get_contrato(obj)
        if not contrato:
            return None
        return contrato.margem_disponivel or contrato.valor_total_antecipacao

    @extend_schema_field(
        serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    )
    def get_comissao_agente(self, obj: EsteiraItem) -> Decimal | None:
        contrato = self._get_contrato(obj)
        return contrato.comissao_agente if contrato else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_status_contrato(self, obj: EsteiraItem) -> str | None:
        contrato = self._get_contrato(obj)
        return contrato.status if contrato else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_status_contrato_visual_slug(self, obj: EsteiraItem) -> str | None:
        contrato = self._get_contrato(obj)
        if not contrato:
            return None
        return get_contract_visual_status_payload(contrato)["status_visual_slug"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_status_contrato_visual_label(self, obj: EsteiraItem) -> str | None:
        contrato = self._get_contrato(obj)
        if not contrato:
            return None
        return get_contract_visual_status_payload(contrato)["status_visual_label"]

    def get_status_documentacao(self, obj: EsteiraItem) -> str:
        documentos = [
            documento
            for documento in obj.associado.documentos.all()
            if not Documento.is_free_attachment_type(documento.tipo)
        ]
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

    def get_contato_web(self, obj: EsteiraItem) -> bool:
        contrato = self._get_contrato(obj)
        return bool(contrato and contrato.contato_web)

    def get_termos_web(self, obj: EsteiraItem) -> bool:
        contrato = self._get_contrato(obj)
        return bool(contrato and contrato.termos_web)

    def get_orgao_publico(self, obj: EsteiraItem) -> str:
        contato = obj.associado.build_contato_payload() or {}
        return obj.associado.orgao_publico or contato.get("orgao_publico", "")

    def get_documentos_count(self, obj: EsteiraItem) -> int:
        return obj.associado.documentos.count()

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_acoes_disponiveis(self, obj: EsteiraItem) -> list[str]:
        return EsteiraService.get_available_actions(obj)


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

    @extend_schema_field(DocumentoEsteiraSerializer(many=True))
    def get_documentos(self, obj: EsteiraItem):
        return DocumentoEsteiraSerializer(obj.associado.documentos.all(), many=True).data


class PendenciaActionSerializer(serializers.Serializer):
    tipo = serializers.CharField()
    descricao = serializers.CharField()


class SolicitarCorrecaoSerializer(serializers.Serializer):
    observacao = serializers.CharField()
