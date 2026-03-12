from __future__ import annotations

from rest_framework import serializers

from apps.associados.models import Associado
from apps.contratos.models import Contrato

from .serializers import SimpleUserSerializer


class AnalisePagamentoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    cadastro_id = serializers.IntegerField(allow_null=True)
    contrato_codigo = serializers.CharField(allow_blank=True)
    full_name = serializers.CharField()
    cpf_cnpj = serializers.CharField()
    agente_responsavel = serializers.CharField()
    status = serializers.CharField()
    valor_pago = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    contrato_valor_antecipacao = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
    )
    contrato_margem_disponivel = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
    )
    paid_at = serializers.DateTimeField(allow_null=True)
    referencia_at = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    created_by_name = serializers.SerializerMethodField()
    notes = serializers.CharField(allow_blank=True)

    def get_created_by_name(self, obj) -> str:
        created_by = getattr(obj, "created_by", None)
        return created_by.full_name if created_by else ""

    def get_referencia_at(self, obj):
        return getattr(obj, "referencia_at", None) or obj.paid_at or obj.created_at


class AnalisePagamentoDataSerializer(serializers.Serializer):
    new_date = serializers.CharField()


class AnaliseMargemSerializer(serializers.ModelSerializer):
    associado_id = serializers.IntegerField(read_only=True)
    nome_completo = serializers.CharField(source="associado.nome_completo", read_only=True)
    cpf_cnpj = serializers.CharField(source="associado.cpf_cnpj", read_only=True)
    agente = SimpleUserSerializer(read_only=True)
    calc_trinta_bruto = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    calc_margem = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    calc_valor_antecipacao = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    calc_doacao_fundo = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    calc_pode_prosseguir = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contrato
        fields = [
            "id",
            "associado_id",
            "codigo",
            "nome_completo",
            "cpf_cnpj",
            "agente",
            "valor_bruto",
            "valor_liquido",
            "valor_mensalidade",
            "prazo_meses",
            "calc_trinta_bruto",
            "calc_margem",
            "calc_valor_antecipacao",
            "calc_doacao_fundo",
            "calc_pode_prosseguir",
            "created_at",
        ]


class AnaliseDadosSerializer(serializers.ModelSerializer):
    agente = SimpleUserSerializer(source="agente_responsavel", read_only=True)
    contrato_codigo = serializers.SerializerMethodField()

    class Meta:
        model = Associado
        fields = [
            "id",
            "nome_completo",
            "cpf_cnpj",
            "matricula",
            "agente",
            "contrato_codigo",
            "created_at",
        ]

    def get_contrato_codigo(self, obj: Associado) -> str | None:
        contrato = next(iter(obj.contratos.all()), None)
        return contrato.codigo if contrato else None


class AnaliseDadosUpdateSerializer(serializers.Serializer):
    nome_completo = serializers.CharField(max_length=255)
