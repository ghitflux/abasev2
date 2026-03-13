from __future__ import annotations

from rest_framework import serializers

from apps.associados.models import Associado
from apps.refinanciamento.models import Refinanciamento

from .models import Ciclo, Contrato, Parcela


class AssociadoContratoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome_completo = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    orgao_publico = serializers.CharField(read_only=True)
    matricula_orgao = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class ContratoAgenteSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class ParcelaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parcela
        fields = [
            "id",
            "numero",
            "referencia_mes",
            "valor",
            "data_vencimento",
            "status",
            "data_pagamento",
            "observacao",
        ]


class CicloDetailSerializer(serializers.ModelSerializer):
    parcelas = ParcelaSerializer(many=True, read_only=True)

    class Meta:
        model = Ciclo
        fields = [
            "id",
            "numero",
            "data_inicio",
            "data_fim",
            "status",
            "valor_total",
            "parcelas",
        ]


class ContratoResumoSerializer(serializers.ModelSerializer):
    ciclos = CicloDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Contrato
        fields = [
            "id",
            "codigo",
            "valor_bruto",
            "valor_liquido",
            "valor_mensalidade",
            "prazo_meses",
            "taxa_antecipacao",
            "margem_disponivel",
            "valor_total_antecipacao",
            "doacao_associado",
            "comissao_agente",
            "status",
            "data_contrato",
            "data_aprovacao",
            "data_primeira_mensalidade",
            "mes_averbacao",
            "contato_web",
            "termos_web",
            "auxilio_liberado_em",
            "ciclos",
        ]


class MensalidadesResumoSerializer(serializers.Serializer):
    pagas = serializers.IntegerField()
    total = serializers.IntegerField()
    descricao = serializers.CharField()
    apto_refinanciamento = serializers.BooleanField()
    refinanciamento_ativo = serializers.BooleanField()


class ContratoListSerializer(serializers.ModelSerializer):
    associado = AssociadoContratoSerializer(read_only=True)
    agente = ContratoAgenteSerializer(read_only=True)
    status_resumido = serializers.SerializerMethodField()
    status_contrato_visual = serializers.SerializerMethodField()
    etapa_fluxo = serializers.SerializerMethodField()
    mensalidades = serializers.SerializerMethodField()
    pode_solicitar_refinanciamento = serializers.SerializerMethodField()

    class Meta:
        model = Contrato
        fields = [
            "id",
            "codigo",
            "associado",
            "agente",
            "status",
            "status_resumido",
            "status_contrato_visual",
            "etapa_fluxo",
            "data_contrato",
            "valor_mensalidade",
            "comissao_agente",
            "mensalidades",
            "auxilio_liberado_em",
            "pode_solicitar_refinanciamento",
        ]

    def _parcelas(self, obj: Contrato):
        return [
            parcela
            for ciclo in obj.ciclos.all()
            for parcela in ciclo.parcelas.all()
        ]

    def get_status_resumido(self, obj: Contrato) -> str:
        return (
            "concluido"
            if obj.status in [Contrato.Status.ATIVO, Contrato.Status.ENCERRADO]
            else "pendente"
        )

    def get_status_contrato_visual(self, obj: Contrato) -> str:
        associado_status = getattr(obj.associado, "status", "")
        if associado_status == Associado.Status.INADIMPLENTE:
            return "inadimplente"
        if associado_status == Associado.Status.INATIVO or obj.status in [
            Contrato.Status.ENCERRADO,
            Contrato.Status.CANCELADO,
        ]:
            return "desativado"
        if obj.status == Contrato.Status.ATIVO:
            return "ativo"
        return "pendente"

    def get_etapa_fluxo(self, obj: Contrato) -> str:
        try:
            esteira = obj.associado.esteira_item
        except Associado.esteira_item.RelatedObjectDoesNotExist:
            esteira = None
        if esteira:
            return esteira.etapa_atual
        return "concluido" if obj.auxilio_liberado_em else "analise"

    def get_mensalidades(self, obj: Contrato) -> dict[str, object]:
        parcelas = self._parcelas(obj)
        pagas = len(
            [
                parcela
                for parcela in parcelas
                if parcela.status == Parcela.Status.DESCONTADO
            ]
        )
        total = len(parcelas)
        refinanciamento_ativo = obj.associado.refinanciamentos.exclude(
            status__in=[
                Refinanciamento.Status.BLOQUEADO,
                Refinanciamento.Status.REJEITADO,
                Refinanciamento.Status.REVERTIDO,
            ]
        ).exists()
        apto = pagas >= 3 and not refinanciamento_ativo
        return MensalidadesResumoSerializer(
            {
                "pagas": pagas,
                "total": total,
                "descricao": f"Mensalidades efetivadas: {pagas}/{total}",
                "apto_refinanciamento": apto,
                "refinanciamento_ativo": refinanciamento_ativo,
            }
        ).data

    def get_pode_solicitar_refinanciamento(self, obj: Contrato) -> bool:
        mensalidades = self.get_mensalidades(obj)
        return bool(mensalidades["apto_refinanciamento"])


class ContratoResumoCardsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    concluidos = serializers.IntegerField()
    ativos = serializers.IntegerField()
    pendentes = serializers.IntegerField()
    inadimplentes = serializers.IntegerField()


class RenovacaoCicloResumoSerializer(serializers.Serializer):
    competencia = serializers.CharField()
    total_associados = serializers.IntegerField()
    ciclo_renovado = serializers.IntegerField()
    apto_a_renovar = serializers.IntegerField()
    em_aberto = serializers.IntegerField()
    ciclo_iniciado = serializers.IntegerField()
    inadimplente = serializers.IntegerField()
    esperado_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    arrecadado_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    percentual_arrecadado = serializers.FloatField()


class RenovacaoCicloMesSerializer(serializers.Serializer):
    id = serializers.CharField()
    label = serializers.CharField()


class RenovacaoCicloItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    competencia = serializers.CharField()
    contrato_id = serializers.IntegerField()
    contrato_codigo = serializers.CharField()
    associado_id = serializers.IntegerField()
    nome_associado = serializers.CharField()
    cpf_cnpj = serializers.CharField()
    orgao_publico = serializers.CharField(allow_blank=True)
    ciclo_id = serializers.IntegerField()
    ciclo_numero = serializers.IntegerField()
    status_ciclo = serializers.CharField()
    status_parcela = serializers.CharField()
    status_visual = serializers.CharField()
    parcelas_pagas = serializers.IntegerField()
    parcelas_total = serializers.IntegerField()
    valor_mensalidade = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_parcela = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = serializers.DateField(allow_null=True)
    orgao_pagto_nome = serializers.CharField(allow_blank=True)
    resultado_importacao = serializers.CharField()
    status_codigo_etipi = serializers.CharField(allow_blank=True)
    gerou_encerramento = serializers.BooleanField()
    gerou_novo_ciclo = serializers.BooleanField()
