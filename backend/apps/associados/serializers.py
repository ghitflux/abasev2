from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.contratos.serializers import CicloDetailSerializer, ContratoResumoSerializer

from .models import Associado, ContatoHistorico, DadosBancarios, Documento, Endereco
from .services import AssociadoService
from .strategies import CadastroValidationStrategy, EdicaoValidationStrategy


class SimpleUserSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class EnderecoSerializer(serializers.ModelSerializer):
    endereco = serializers.CharField(source="logradouro")

    class Meta:
        model = Endereco
        fields = [
            "id",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
            "created_at",
            "updated_at",
        ]


class EnderecoWriteSerializer(serializers.ModelSerializer):
    endereco = serializers.CharField(source="logradouro")
    numero = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Endereco
        fields = ["cep", "endereco", "numero", "complemento", "bairro", "cidade", "uf"]


class DadosBancariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = DadosBancarios
        fields = "__all__"


class DadosBancariosWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DadosBancarios
        fields = ["banco", "agencia", "conta", "tipo_conta", "chave_pix"]


class ContatoHistoricoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContatoHistorico
        fields = "__all__"


class ContatoHistoricoWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContatoHistorico
        fields = [
            "celular",
            "email",
            "orgao_publico",
            "situacao_servidor",
            "matricula_servidor",
        ]


class DocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = "__all__"


class DocumentoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Documento
        fields = ["id", "tipo", "arquivo", "status", "observacao"]
        read_only_fields = ["id", "status"]

    def create(self, validated_data):
        associado = validated_data.pop("associado")
        tipo = validated_data["tipo"]
        arquivo = validated_data["arquivo"]
        observacao = validated_data.get("observacao", "")

        documento_existente = Documento.objects.filter(
            associado=associado,
            tipo=tipo,
        ).first()
        if documento_existente:
            if documento_existente.arquivo:
                documento_existente.arquivo.delete(save=False)
            documento_existente.arquivo = arquivo
            documento_existente.status = Documento.Status.PENDENTE
            documento_existente.observacao = observacao
            documento_existente.save()
            return documento_existente

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
    ciclos_abertos = serializers.IntegerField(read_only=True)
    ciclos_fechados = serializers.IntegerField(read_only=True)

    class Meta:
        model = Associado
        fields = [
            "id",
            "nome_completo",
            "matricula",
            "cpf_cnpj",
            "status",
            "agente",
            "ciclos_abertos",
            "ciclos_fechados",
        ]


class AssociadoDetailSerializer(serializers.ModelSerializer):
    agente = SimpleUserSerializer(source="agente_responsavel", read_only=True)
    endereco = EnderecoSerializer(read_only=True)
    dados_bancarios = DadosBancariosSerializer(read_only=True)
    contato = ContatoHistoricoSerializer(source="contato_historico", read_only=True)
    contratos = ContratoResumoSerializer(many=True, read_only=True)
    documentos = DocumentoSerializer(many=True, read_only=True)
    esteira = EsteiraItemResumoSerializer(source="esteira_item", read_only=True)

    class Meta:
        model = Associado
        fields = [
            "id",
            "matricula",
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
        ]


class AssociadoCreateSerializer(serializers.ModelSerializer):
    cpf_cnpj = serializers.CharField(validators=[])
    endereco = EnderecoWriteSerializer()
    dados_bancarios = DadosBancariosWriteSerializer()
    contato = ContatoHistoricoWriteSerializer()

    valor_bruto_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_liquido = serializers.DecimalField(max_digits=10, decimal_places=2)
    prazo_meses = serializers.IntegerField(min_value=1, default=3)
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
            "documentos_payload",
        ]
        read_only_fields = ["id", "matricula"]

    def validate(self, attrs):
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
        }
        attrs["contrato"] = contrato
        return CadastroValidationStrategy().validate(attrs)

    def create(self, validated_data):
        agente = self.context["request"].user
        return AssociadoService.criar_associado_completo(validated_data, agente)

    def to_representation(self, instance):
        return AssociadoDetailSerializer(instance, context=self.context).data


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
    prazo_meses = serializers.IntegerField(required=False, source="contrato.prazo_meses")
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
        ]
        read_only_fields = ["id", "matricula", "cpf_cnpj"]

    def validate(self, attrs):
        return EdicaoValidationStrategy().validate(attrs)

    def update(self, instance, validated_data):
        endereco_data = validated_data.pop("endereco", None)
        dados_bancarios_data = validated_data.pop("dados_bancarios", None)
        contato_data = validated_data.pop("contato", None)
        contrato_data = validated_data.pop("contrato", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()

        if endereco_data:
            Endereco.objects.update_or_create(
                associado=instance,
                defaults=endereco_data,
            )

        if dados_bancarios_data:
            DadosBancarios.objects.update_or_create(
                associado=instance,
                defaults=dados_bancarios_data,
            )

        if contato_data:
            ContatoHistorico.objects.update_or_create(
                associado=instance,
                defaults={
                    **contato_data,
                    "nome_contato": instance.nome_completo,
                    "telefone_contato": contato_data.get("celular", ""),
                },
            )
            instance.email = contato_data.get("email", instance.email)
            instance.telefone = contato_data.get("celular", instance.telefone)
            instance.orgao_publico = contato_data.get(
                "orgao_publico", instance.orgao_publico
            )
            instance.matricula_orgao = contato_data.get(
                "matricula_servidor", instance.matricula_orgao
            )
            instance.save(
                update_fields=[
                    "email",
                    "telefone",
                    "orgao_publico",
                    "matricula_orgao",
                    "updated_at",
                ]
            )

        if contrato_data:
            contrato = instance.contratos.order_by("-created_at").first()
            if contrato:
                for field, value in contrato_data.items():
                    setattr(contrato, field, value)
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
