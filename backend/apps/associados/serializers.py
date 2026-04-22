from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import MobileAccessToken, User
from apps.contratos.canonicalization import (
    resolve_operational_contract_for_associado,
)
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_associado_visual_status_payload,
    resolve_associado_mother_status,
    resolve_associado_status_renovacao,
)
from apps.contratos.serializers import CicloDetailSerializer, ContratoResumoSerializer
from core.file_references import build_storage_reference

from .models import Associado, Documento
from .admin_override_service import AdminOverrideService
from .services import AssociadoService
from .strategies import (
    CadastroValidationStrategy,
    EdicaoValidationStrategy,
    calculate_contract_financials,
    validate_positive_mensalidade,
)


def _is_agent_restricted(context: dict) -> bool:
    if context.get("agent_correction_mode"):
        return False
    request = context.get("request")
    if not request or not getattr(request, "user", None):
        return False
    user = request.user
    if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
        return False
    return user.has_role("AGENTE") and not user.has_role("ADMIN")


def _can_manage_agent_assignment(context: dict) -> bool:
    request = context.get("request")
    if not request or not getattr(request, "user", None):
        return False
    user = request.user
    if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
        return False
    return user.has_role("ADMIN", "ANALISTA", "COORDENADOR", "TESOUREIRO")


def _can_override_percentual_repasse(context: dict) -> bool:
    request = context.get("request")
    if not request or not getattr(request, "user", None):
        return False
    user = request.user
    if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
        return False
    return user.has_role("ADMIN", "ANALISTA", "COORDENADOR")


def get_associado_cadastro_origin_payload(obj: Associado) -> dict[str, str]:
    observacao = (obj.observacao or "").casefold()
    if "associadodois_cadastros" in observacao:
        return {
            "origem_cadastro_slug": "mobile",
            "origem_cadastro_label": "Mobile",
        }

    user = getattr(obj, "user", None)
    if user is not None and user.has_role("ASSOCIADODOIS"):
        return {
            "origem_cadastro_slug": "mobile",
            "origem_cadastro_label": "Mobile",
        }

    return {
        "origem_cadastro_slug": "web",
        "origem_cadastro_label": "Web",
    }


def get_detail_visible_contracts_for_associado(obj: Associado):
    return AssociadoService.get_detail_visible_contracts_for_associado(obj)


class SimpleUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class EnderecoSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    cep = serializers.CharField(allow_blank=True, required=False)
    endereco = serializers.CharField(allow_blank=True, required=False)
    numero = serializers.CharField(allow_blank=True, required=False)
    complemento = serializers.CharField(allow_blank=True, required=False)
    bairro = serializers.CharField(allow_blank=True, required=False)
    cidade = serializers.CharField(allow_blank=True, required=False)
    uf = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.DateTimeField(allow_null=True, required=False)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)


class EnderecoWriteSerializer(serializers.Serializer):
    cep = serializers.CharField(required=False, allow_blank=True)
    endereco = serializers.CharField(source="logradouro")
    numero = serializers.CharField(required=False, allow_blank=True)
    complemento = serializers.CharField(required=False, allow_blank=True, default="")
    bairro = serializers.CharField(required=False, allow_blank=True)
    cidade = serializers.CharField(required=False, allow_blank=True)
    uf = serializers.CharField(required=False, allow_blank=True)


class DadosBancariosSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    associado = serializers.IntegerField(allow_null=True, required=False)
    banco = serializers.CharField(allow_blank=True, required=False)
    agencia = serializers.CharField(allow_blank=True, required=False)
    conta = serializers.CharField(allow_blank=True, required=False)
    tipo_conta = serializers.CharField(allow_blank=True, required=False)
    chave_pix = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.DateTimeField(allow_null=True, required=False)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)


class DadosBancariosWriteSerializer(serializers.Serializer):
    banco = serializers.CharField(required=False, allow_blank=True)
    agencia = serializers.CharField(required=False, allow_blank=True)
    conta = serializers.CharField(required=False, allow_blank=True)
    tipo_conta = serializers.CharField(required=False, allow_blank=True)
    chave_pix = serializers.CharField(required=False, allow_blank=True)


class ContatoHistoricoSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)
    associado = serializers.IntegerField(allow_null=True, required=False)
    celular = serializers.CharField(allow_blank=True, required=False)
    email = serializers.CharField(allow_blank=True, required=False)
    orgao_publico = serializers.CharField(allow_blank=True, required=False)
    situacao_servidor = serializers.CharField(allow_blank=True, required=False)
    matricula_servidor = serializers.CharField(allow_blank=True, required=False)
    nome_contato = serializers.CharField(allow_blank=True, required=False)
    parentesco = serializers.CharField(allow_blank=True, required=False)
    telefone_contato = serializers.CharField(allow_blank=True, required=False)
    ultima_interacao_em = serializers.DateTimeField(allow_null=True, required=False)
    observacao = serializers.CharField(allow_blank=True, required=False)
    created_at = serializers.DateTimeField(allow_null=True, required=False)
    updated_at = serializers.DateTimeField(allow_null=True, required=False)


class ContatoHistoricoWriteSerializer(serializers.Serializer):
    celular = serializers.CharField(required=False, allow_blank=True)
    email = serializers.CharField(required=False, allow_blank=True)
    orgao_publico = serializers.CharField(required=False, allow_blank=True)
    situacao_servidor = serializers.CharField(required=False, allow_blank=True)
    matricula_servidor = serializers.CharField(required=False, allow_blank=True)


class DocumentoSerializer(serializers.ModelSerializer):
    arquivo_referencia = serializers.SerializerMethodField()
    arquivo_disponivel_localmente = serializers.SerializerMethodField()
    tipo_referencia = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            "id",
            "associado",
            "tipo",
            "arquivo",
            "arquivo_referencia",
            "arquivo_disponivel_localmente",
            "tipo_referencia",
            "arquivo_referencia_path",
            "nome_original",
            "origem",
            "status",
            "observacao",
            "created_at",
            "updated_at",
        ]

    def _reference(self, obj: Documento):
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

    def get_arquivo_referencia(self, obj: Documento) -> str:
        return self._reference(obj).arquivo_referencia

    def get_arquivo_disponivel_localmente(self, obj: Documento) -> bool:
        return self._reference(obj).arquivo_disponivel_localmente

    def get_tipo_referencia(self, obj: Documento) -> str:
        return self._reference(obj).tipo_referencia


class DocumentoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = ["id", "tipo", "arquivo", "status", "observacao"]
        read_only_fields = ["id", "status"]

    def create(self, validated_data):
        associado = validated_data.pop("associado")

        return Documento.objects.create(
            associado=associado,
            status=Documento.Status.PENDENTE,
            **validated_data,
        )


class PendenciaResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    descricao = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class TransicaoResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    acao = serializers.CharField(read_only=True)
    de_status = serializers.CharField(read_only=True)
    para_status = serializers.CharField(read_only=True)
    de_situacao = serializers.CharField(read_only=True)
    para_situacao = serializers.CharField(read_only=True)
    observacao = serializers.CharField(read_only=True)
    realizado_em = serializers.DateTimeField(read_only=True)


class EsteiraItemResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    etapa_atual = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    prioridade = serializers.IntegerField(read_only=True)
    analista = SimpleUserSerializer(source="analista_responsavel", read_only=True)
    coordenador = SimpleUserSerializer(
        source="coordenador_responsavel", read_only=True
    )
    tesoureiro = SimpleUserSerializer(source="tesoureiro_responsavel", read_only=True)
    pendencias = PendenciaResumoSerializer(many=True, read_only=True)
    transicoes = TransicaoResumoSerializer(many=True, read_only=True)


class AssociadoListSerializer(serializers.ModelSerializer):
    agente = SimpleUserSerializer(source="agente_responsavel", read_only=True)
    ciclos_abertos = serializers.SerializerMethodField()
    ciclos_fechados = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    status_renovacao = serializers.SerializerMethodField()
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    possui_meses_nao_descontados = serializers.SerializerMethodField()
    meses_nao_descontados_count = serializers.SerializerMethodField()
    matricula_display = serializers.SerializerMethodField()

    class Meta:
        model = Associado
        fields = [
            "id",
            "nome_completo",
            "matricula",
            "matricula_orgao",
            "matricula_display",
            "cpf_cnpj",
            "status",
            "status_renovacao",
            "status_visual_slug",
            "status_visual_label",
            "possui_meses_nao_descontados",
            "meses_nao_descontados_count",
            "agente",
            "ciclos_abertos",
            "ciclos_fechados",
        ]

    def _get_active_contracts(self, obj: Associado):
        return get_detail_visible_contracts_for_associado(obj)

    def _contagens_ciclos(self, obj: Associado) -> dict[str, int]:
        cache = self.context.setdefault("_ciclos_cache", {})
        if obj.id not in cache:
            cache[obj.id] = AssociadoService.contar_ciclos_logicos(obj)
        return cache[obj.id]

    def get_ciclos_abertos(self, obj: Associado) -> int:
        return self._contagens_ciclos(obj)["ciclos_abertos"]

    def get_ciclos_fechados(self, obj: Associado) -> int:
        return self._contagens_ciclos(obj)["ciclos_fechados"]

    def get_status_renovacao(self, obj: Associado) -> str:
        return resolve_associado_status_renovacao(obj)

    def get_status(self, obj: Associado) -> str:
        return resolve_associado_mother_status(obj)

    def get_status_visual_slug(self, obj: Associado) -> str:
        return str(get_associado_visual_status_payload(obj)["status_visual_slug"])

    def get_status_visual_label(self, obj: Associado) -> str:
        return str(get_associado_visual_status_payload(obj)["status_visual_label"])

    def get_possui_meses_nao_descontados(self, obj: Associado) -> bool:
        return any(
            bool(build_contract_cycle_projection(contrato)["possui_meses_nao_descontados"])
            for contrato in self._get_active_contracts(obj)
        )

    def get_meses_nao_descontados_count(self, obj: Associado) -> int:
        return sum(
            int(build_contract_cycle_projection(contrato)["meses_nao_descontados_count"])
            for contrato in self._get_active_contracts(obj)
        )

    def get_matricula_display(self, obj: Associado) -> str:
        return obj.matricula_display


class AssociadoDetailSerializer(serializers.ModelSerializer):
    agente = SimpleUserSerializer(source="agente_responsavel", read_only=True)
    endereco = serializers.SerializerMethodField()
    dados_bancarios = serializers.SerializerMethodField()
    contato = serializers.SerializerMethodField()
    contratos = serializers.SerializerMethodField()
    documentos = DocumentoSerializer(many=True, read_only=True)
    esteira = EsteiraItemResumoSerializer(source="esteira_item", read_only=True)
    status = serializers.SerializerMethodField()
    status_renovacao = serializers.SerializerMethodField()
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    possui_meses_nao_descontados = serializers.SerializerMethodField()
    meses_nao_descontados_count = serializers.SerializerMethodField()
    matricula_display = serializers.SerializerMethodField()
    percentual_repasse = serializers.SerializerMethodField()
    mobile_sessions = serializers.SerializerMethodField()
    admin_history = serializers.SerializerMethodField()
    origem_cadastro_slug = serializers.SerializerMethodField()
    origem_cadastro_label = serializers.SerializerMethodField()

    class Meta:
        model = Associado
        fields = [
            "id",
            "matricula",
            "matricula_display",
            "tipo_documento",
            "nome_completo",
            "cpf_cnpj",
            "rg",
            "orgao_expedidor",
            "email",
            "telefone",
            "data_nascimento",
            "profissao",
            "estado_civil",
            "orgao_publico",
            "matricula_orgao",
            "cargo",
            "status",
            "arquivo_retorno_origem",
            "competencia_importacao_retorno",
            "data_geracao_importacao_retorno",
            "ultimo_arquivo_retorno",
            "status_renovacao",
            "status_visual_slug",
            "status_visual_label",
            "possui_meses_nao_descontados",
            "meses_nao_descontados_count",
            "percentual_repasse",
            "observacao",
            "agente",
            "endereco",
            "dados_bancarios",
            "contato",
            "contratos",
            "documentos",
            "esteira",
            "created_at",
            "updated_at",
            "mobile_sessions",
            "admin_history",
            "origem_cadastro_slug",
            "origem_cadastro_label",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _is_agent_restricted(self.context):
            for field_name in [
                "tipo_documento",
                "rg",
                "orgao_expedidor",
                "email",
                "telefone",
                "data_nascimento",
                "profissao",
                "estado_civil",
                "orgao_publico",
                "matricula_orgao",
                "cargo",
                "percentual_repasse",
                "observacao",
                "endereco",
                "dados_bancarios",
                "documentos",
                "esteira",
                "admin_history",
            ]:
                self.fields.pop(field_name, None)

    def _get_active_contracts(self, obj: Associado):
        return get_detail_visible_contracts_for_associado(obj)

    @extend_schema_field(ContratoResumoSerializer(many=True))
    def get_contratos(self, obj: Associado):
        contratos = self._get_active_contracts(obj)
        return ContratoResumoSerializer(
            contratos,
            many=True,
            context=self.context,
        ).data

    def get_status_renovacao(self, obj: Associado) -> str:
        return resolve_associado_status_renovacao(obj)

    def get_status(self, obj: Associado) -> str:
        return resolve_associado_mother_status(obj)

    def get_status_visual_slug(self, obj: Associado) -> str:
        return str(get_associado_visual_status_payload(obj)["status_visual_slug"])

    def get_status_visual_label(self, obj: Associado) -> str:
        return str(get_associado_visual_status_payload(obj)["status_visual_label"])

    def get_possui_meses_nao_descontados(self, obj: Associado) -> bool:
        return any(
            bool(build_contract_cycle_projection(contrato)["possui_meses_nao_descontados"])
            for contrato in self._get_active_contracts(obj)
        )

    def get_meses_nao_descontados_count(self, obj: Associado) -> int:
        return sum(
            int(build_contract_cycle_projection(contrato)["meses_nao_descontados_count"])
            for contrato in self._get_active_contracts(obj)
        )

    def get_matricula_display(self, obj: Associado) -> str:
        return obj.matricula_display

    def get_percentual_repasse(self, obj: Associado) -> str:
        return f"{obj.auxilio_taxa:.2f}"

    @extend_schema_field(EnderecoSerializer(allow_null=True))
    def get_endereco(self, obj: Associado):
        payload = obj.build_endereco_payload()
        if not payload:
            return None
        return EnderecoSerializer(payload).data

    @extend_schema_field(DadosBancariosSerializer(allow_null=True))
    def get_dados_bancarios(self, obj: Associado):
        payload = obj.build_dados_bancarios_payload()
        if not payload:
            return None
        return DadosBancariosSerializer(payload).data

    @extend_schema_field(ContatoHistoricoSerializer(allow_null=True))
    def get_contato(self, obj: Associado):
        payload = obj.build_contato_payload()
        if not payload:
            return None
        return ContatoHistoricoSerializer(payload).data

    def get_mobile_sessions(self, obj: Associado) -> list:
        user = getattr(obj, "user", None)
        if not user:
            return []
        qs = MobileAccessToken.objects.filter(
            user=user,
            revoked_at__isnull=True,
            deleted_at__isnull=True,
        ).order_by("-last_used_at")[:3]
        return [
            {
                "last_used_at": t.last_used_at,
                "is_active": t.is_active,
            }
            for t in qs
        ]

    def get_admin_history(self, obj: Associado) -> list:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or not user.has_role("ADMIN"):
            return []
        return AdminOverrideService.build_associado_history_payload(obj, request=request)

    def get_origem_cadastro_slug(self, obj: Associado) -> str:
        return get_associado_cadastro_origin_payload(obj)["origem_cadastro_slug"]

    def get_origem_cadastro_label(self, obj: Associado) -> str:
        return get_associado_cadastro_origin_payload(obj)["origem_cadastro_label"]


class AssociadoCreateSerializer(serializers.ModelSerializer):
    cpf_cnpj = serializers.CharField(validators=[])
    endereco = EnderecoWriteSerializer()
    dados_bancarios = DadosBancariosWriteSerializer()
    contato = ContatoHistoricoWriteSerializer()

    valor_bruto_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_liquido = serializers.DecimalField(max_digits=10, decimal_places=2)
    prazo_meses = serializers.IntegerField(min_value=3, max_value=4, default=3)
    taxa_antecipacao = serializers.DecimalField(
        max_digits=5, decimal_places=2, default=30
    )
    mensalidade = serializers.DecimalField(max_digits=10, decimal_places=2)
    margem_disponivel = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=0,
    )
    data_aprovacao = serializers.DateField(required=False, allow_null=True)
    data_primeira_mensalidade = serializers.DateField(required=False, allow_null=True)
    mes_averbacao = serializers.DateField(required=False, allow_null=True)
    doacao_associado = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        default=0,
    )
    documentos_payload = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
    )
    agente_responsavel_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True,
    )
    percentual_repasse = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Associado
        fields = [
            "id",
            "matricula",
            "tipo_documento",
            "cpf_cnpj",
            "nome_completo",
            "rg",
            "orgao_expedidor",
            "data_nascimento",
            "profissao",
            "estado_civil",
            "cargo",
            "observacao",
            "endereco",
            "dados_bancarios",
            "contato",
            "valor_bruto_total",
            "valor_liquido",
            "prazo_meses",
            "taxa_antecipacao",
            "mensalidade",
            "margem_disponivel",
            "data_aprovacao",
            "data_primeira_mensalidade",
            "mes_averbacao",
            "doacao_associado",
            "agente_responsavel_id",
            "percentual_repasse",
            "documentos_payload",
        ]
        read_only_fields = ["id", "matricula"]

    def validate_mensalidade(self, value):
        return validate_positive_mensalidade(value, field_name="mensalidade")

    def validate(self, attrs):
        agente_responsavel_id = attrs.get("agente_responsavel_id")
        sent_agente_responsavel = "agente_responsavel_id" in self.initial_data
        if sent_agente_responsavel and not _can_manage_agent_assignment(self.context):
            raise serializers.ValidationError(
                "Seu perfil não pode definir agente responsável."
            )
        if _can_manage_agent_assignment(self.context) and agente_responsavel_id is None:
            raise serializers.ValidationError(
                {"agente_responsavel_id": "Selecione o agente responsável."}
            )
        if agente_responsavel_id is not None and not User.objects.filter(
            id=agente_responsavel_id,
            is_active=True,
            user_roles__deleted_at__isnull=True,
            user_roles__role__codigo="AGENTE",
        ).exists():
            raise serializers.ValidationError(
                {"agente_responsavel_id": "Agente responsável inválido."}
            )
        sent_percentual_repasse = "percentual_repasse" in self.initial_data
        percentual_repasse = attrs.get("percentual_repasse")
        if sent_percentual_repasse and not _can_override_percentual_repasse(self.context):
            raise serializers.ValidationError(
                "Seu perfil não pode definir comissão manual no cadastro."
            )
        if percentual_repasse is not None and percentual_repasse < 0:
            raise serializers.ValidationError(
                {"percentual_repasse": "Informe um percentual válido."}
            )
        contrato = {
            "valor_bruto_total": attrs.pop("valor_bruto_total"),
            "valor_liquido": attrs.pop("valor_liquido"),
            "prazo_meses": attrs.pop("prazo_meses"),
            "taxa_antecipacao": attrs.pop("taxa_antecipacao"),
            "mensalidade": attrs.pop("mensalidade"),
            "margem_disponivel": attrs.pop("margem_disponivel", 0),
            "data_aprovacao": attrs.pop("data_aprovacao", None),
            "data_primeira_mensalidade": attrs.pop(
                "data_primeira_mensalidade", None
            ),
            "mes_averbacao": attrs.pop("mes_averbacao", None),
            "doacao_associado": attrs.pop("doacao_associado", 0),
            "percentual_repasse": attrs.pop("percentual_repasse", None),
        }
        attrs["contrato"] = contrato
        return CadastroValidationStrategy().validate(attrs)

    def create(self, validated_data):
        agente = self.context["request"].user
        return AssociadoService.criar_associado_completo(validated_data, agente)

    def to_representation(self, instance):
        return AssociadoDetailSerializer(instance, context=self.context).data


class AssociadoReativarSerializer(serializers.Serializer):
    valor_bruto_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_liquido = serializers.DecimalField(max_digits=10, decimal_places=2)
    prazo_meses = serializers.IntegerField(min_value=3, max_value=4, default=3)
    mensalidade = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_aprovacao = serializers.DateField(required=False, allow_null=True)
    agente_responsavel_id = serializers.IntegerField(required=True)
    percentual_repasse = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
    )

    def validate_mensalidade(self, value):
        return validate_positive_mensalidade(value, field_name="mensalidade")

    def validate(self, attrs):
        if not _can_manage_agent_assignment(self.context):
            raise serializers.ValidationError(
                "Seu perfil não pode definir agente responsável."
            )

        agente_responsavel_id = attrs.get("agente_responsavel_id")
        if not User.objects.filter(
            id=agente_responsavel_id,
            is_active=True,
            user_roles__deleted_at__isnull=True,
            user_roles__role__codigo="AGENTE",
        ).exists():
            raise serializers.ValidationError(
                {"agente_responsavel_id": "Agente responsável inválido."}
            )

        sent_percentual_repasse = "percentual_repasse" in self.initial_data
        percentual_repasse = attrs.get("percentual_repasse")
        if sent_percentual_repasse and not _can_override_percentual_repasse(self.context):
            raise serializers.ValidationError(
                "Seu perfil não pode definir comissão manual no cadastro."
            )
        if percentual_repasse is not None and percentual_repasse < 0:
            raise serializers.ValidationError(
                {"percentual_repasse": "Informe um percentual válido."}
            )

        contrato = {
            "valor_bruto_total": attrs.pop("valor_bruto_total"),
            "valor_liquido": attrs.pop("valor_liquido"),
            "prazo_meses": attrs.pop("prazo_meses"),
            "mensalidade": attrs.pop("mensalidade"),
            "data_aprovacao": attrs.pop("data_aprovacao", None),
            "percentual_repasse": attrs.pop("percentual_repasse", None),
        }
        contrato.update(
            calculate_contract_financials(
                mensalidade=contrato.get("mensalidade"),
                prazo_meses=contrato.get("prazo_meses"),
                percentual_repasse=contrato.get("percentual_repasse"),
            )
        )
        attrs["contrato"] = contrato
        return attrs


class AssociadoUpdateSerializer(serializers.ModelSerializer):
    endereco = EnderecoWriteSerializer(required=False)
    dados_bancarios = DadosBancariosWriteSerializer(required=False)
    contato = ContatoHistoricoWriteSerializer(required=False)

    valor_bruto_total = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        source="contrato.valor_bruto",
    )
    valor_liquido = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        source="contrato.valor_liquido",
    )
    prazo_meses = serializers.IntegerField(
        required=False,
        min_value=3,
        max_value=4,
        source="contrato.prazo_meses",
    )
    taxa_antecipacao = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        source="contrato.taxa_antecipacao",
    )
    mensalidade = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        source="contrato.valor_mensalidade",
    )
    margem_disponivel = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        source="contrato.margem_disponivel",
    )
    agente_responsavel_id = serializers.IntegerField(required=False, allow_null=True)
    percentual_repasse = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = Associado
        fields = [
            "id",
            "matricula",
            "tipo_documento",
            "cpf_cnpj",
            "nome_completo",
            "rg",
            "orgao_expedidor",
            "data_nascimento",
            "profissao",
            "estado_civil",
            "cargo",
            "status",
            "observacao",
            "endereco",
            "dados_bancarios",
            "contato",
            "valor_bruto_total",
            "valor_liquido",
            "prazo_meses",
            "taxa_antecipacao",
            "mensalidade",
            "margem_disponivel",
            "agente_responsavel_id",
            "percentual_repasse",
        ]
        read_only_fields = ["id", "matricula", "cpf_cnpj"]

    def validate_mensalidade(self, value):
        return validate_positive_mensalidade(value, field_name="mensalidade")

    def validate(self, attrs):
        if "percentual_repasse" in self.initial_data:
            raise serializers.ValidationError(
                {"percentual_repasse": "A comissão manual só pode ser definida no cadastro."}
            )
        if "agente_responsavel_id" in attrs and not _can_manage_agent_assignment(self.context):
            raise serializers.ValidationError(
                "Seu perfil não pode definir agente responsável."
            )
        agente_responsavel_id = attrs.get("agente_responsavel_id")
        if agente_responsavel_id is not None and not User.objects.filter(
            id=agente_responsavel_id,
            is_active=True,
            user_roles__deleted_at__isnull=True,
            user_roles__role__codigo="AGENTE",
        ).exists():
            raise serializers.ValidationError(
                {"agente_responsavel_id": "Agente responsável inválido."}
            )
        return EdicaoValidationStrategy().validate(attrs)

    def update(self, instance, validated_data):
        endereco_data = validated_data.pop("endereco", None)
        dados_bancarios_data = validated_data.pop("dados_bancarios", None)
        contato_data = validated_data.pop("contato", None)
        contrato_data = validated_data.pop("contrato", None)
        agente_responsavel_id = validated_data.pop("agente_responsavel_id", None)
        validated_data.pop("percentual_repasse", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if agente_responsavel_id is not None:
            instance.agente_responsavel_id = agente_responsavel_id
        if endereco_data:
            instance.cep = endereco_data.get("cep", instance.cep)
            instance.logradouro = endereco_data.get("logradouro", instance.logradouro)
            instance.numero = endereco_data.get("numero", instance.numero)
            instance.complemento = endereco_data.get(
                "complemento", instance.complemento
            )
            instance.bairro = endereco_data.get("bairro", instance.bairro)
            instance.cidade = endereco_data.get("cidade", instance.cidade)
            instance.uf = endereco_data.get("uf", instance.uf)

        if dados_bancarios_data:
            instance.banco = dados_bancarios_data.get("banco", instance.banco)
            instance.agencia = dados_bancarios_data.get("agencia", instance.agencia)
            instance.conta = dados_bancarios_data.get("conta", instance.conta)
            instance.tipo_conta = dados_bancarios_data.get(
                "tipo_conta", instance.tipo_conta
            )
            instance.chave_pix = dados_bancarios_data.get(
                "chave_pix", instance.chave_pix
            )

        if contato_data:
            instance.email = contato_data.get("email", instance.email)
            instance.telefone = contato_data.get("celular", instance.telefone)
            instance.orgao_publico = contato_data.get(
                "orgao_publico", instance.orgao_publico
            )
            instance.situacao_servidor = contato_data.get(
                "situacao_servidor", instance.situacao_servidor
            )
            instance.matricula_orgao = contato_data.get(
                "matricula_servidor", instance.matricula_orgao
            )

        instance.save()

        if contrato_data:
            contrato = resolve_operational_contract_for_associado(instance)
            if contrato:
                for field, value in contrato_data.items():
                    setattr(contrato, field, value)
                if agente_responsavel_id is not None:
                    contrato.agente_id = agente_responsavel_id
                contrato.save()
        elif agente_responsavel_id is not None:
            contrato = resolve_operational_contract_for_associado(instance)
            if contrato:
                if agente_responsavel_id is not None:
                    contrato.agente_id = agente_responsavel_id
                contrato.save()

        return instance

    def to_representation(self, instance):
        return AssociadoDetailSerializer(instance, context=self.context).data


class MetricaSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    variacao_percentual = serializers.FloatField()


class AssociadoMetricasSerializer(serializers.Serializer):
    total = MetricaSerializer()
    ativos = MetricaSerializer()
    em_analise = MetricaSerializer()
    inativos = MetricaSerializer()
    liquidados = MetricaSerializer()
