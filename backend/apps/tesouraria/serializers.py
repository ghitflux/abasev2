from __future__ import annotations

from datetime import date

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.associados.serializers import DadosBancariosSerializer, SimpleUserSerializer
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_contract_visual_status_payload,
)
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, PagamentoMensalidade
from apps.refinanciamento.serializers import ComprovanteResumoSerializer
from apps.tesouraria.initial_payment import build_initial_payment_payload
from apps.tesouraria.payment_evidence import build_competencia_evidence_payload
from apps.tesouraria.models import BaixaManual
from core.file_references import build_filefield_reference, build_storage_reference


class TesourariaContratoListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    associado_id = serializers.IntegerField(source="associado.id", read_only=True)
    nome = serializers.CharField(source="associado.nome_completo", read_only=True)
    cpf_cnpj = serializers.CharField(source="associado.cpf_cnpj", read_only=True)
    chave_pix = serializers.SerializerMethodField()
    codigo = serializers.CharField(read_only=True)
    data_assinatura = serializers.DateField(source="data_contrato", read_only=True)
    status = serializers.SerializerMethodField()
    agente = SimpleUserSerializer(read_only=True)
    agente_nome = serializers.CharField(source="agente.full_name", read_only=True)
    comissao_agente = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    margem_disponivel = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    comprovantes = serializers.SerializerMethodField()
    dados_bancarios = serializers.SerializerMethodField()
    observacao_tesouraria = serializers.CharField(
        source="associado.esteira_item.observacao", read_only=True
    )
    etapa_atual = serializers.CharField(
        source="associado.esteira_item.etapa_atual", read_only=True
    )
    situacao_esteira = serializers.CharField(
        source="associado.esteira_item.status", read_only=True
    )

    def get_status(self, obj) -> str:
        esteira = getattr(obj.associado, "esteira_item", None)
        if obj.status == obj.Status.CANCELADO:
            return "cancelado"
        if esteira and esteira.etapa_atual == "concluido":
            return "concluido"
        if esteira and esteira.status == "pendenciado":
            return "congelado"
        return "pendente"

    def get_comprovantes(self, obj):
        comprovantes = obj.comprovantes.filter(refinanciamento__isnull=True)
        return ComprovanteResumoSerializer(comprovantes, many=True).data

    def get_chave_pix(self, obj) -> str:
        payload = obj.associado.build_dados_bancarios_payload() or {}
        return payload.get("chave_pix", "")

    def get_dados_bancarios(self, obj):
        payload = obj.associado.build_dados_bancarios_payload()
        if not payload:
            return None
        return DadosBancariosSerializer(payload).data


class EfetivarContratoSerializer(serializers.Serializer):
    comprovante_associado = serializers.FileField(required=True)
    comprovante_agente = serializers.FileField(required=True)


class CongelarContratoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class ConfirmacaoListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    contrato_id = serializers.IntegerField()
    associado_id = serializers.IntegerField()
    nome = serializers.CharField()
    cpf_cnpj = serializers.CharField()
    agente_nome = serializers.CharField(allow_blank=True)
    competencia = serializers.DateField()
    link_chamada = serializers.CharField(allow_blank=True)
    ligacao_confirmada = serializers.BooleanField()
    averbacao_confirmada = serializers.BooleanField()
    status_visual = serializers.CharField()


class ConfirmacaoLinkSerializer(serializers.Serializer):
    link = serializers.URLField()


class AgentePagamentoComprovanteSerializer(serializers.Serializer):
    id = serializers.CharField(read_only=True)
    nome = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    arquivo_referencia = serializers.CharField(read_only=True)
    arquivo_disponivel_localmente = serializers.BooleanField(read_only=True)
    tipo_referencia = serializers.CharField(read_only=True)
    origem = serializers.CharField(read_only=True)
    papel = serializers.CharField(read_only=True, allow_blank=True)
    tipo = serializers.CharField(read_only=True, allow_blank=True)
    status = serializers.CharField(read_only=True, allow_blank=True)
    competencia = serializers.DateField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True, allow_null=True)


class AgentePagamentoParcelaSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    numero = serializers.IntegerField(read_only=True)
    referencia_mes = serializers.DateField(read_only=True)
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    data_vencimento = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    data_pagamento = serializers.DateField(read_only=True, allow_null=True)
    observacao = serializers.CharField(read_only=True)
    comprovantes = serializers.SerializerMethodField()

    @extend_schema_field(AgentePagamentoComprovanteSerializer(many=True))
    def get_comprovantes(self, obj: Parcela) -> list[dict[str, object]]:
        pagamentos_manuais = self.context.get("pagamentos_mensalidade_por_referencia", {})
        pagamento_mensalidade: PagamentoMensalidade | None = pagamentos_manuais.get(
            obj.referencia_mes
        )
        evidence_payload = build_competencia_evidence_payload(
            referencia_mes=obj.referencia_mes,
            arquivo_items=obj.itens_retorno.all(),
            pagamento_mensalidade=pagamento_mensalidade,
            baixa_manual=getattr(obj, "baixa_manual", None),
            request=self.context.get("request"),
        )
        return AgentePagamentoComprovanteSerializer(
            evidence_payload.evidencias,
            many=True,
        ).data


class AgentePagamentoCicloSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    numero = serializers.IntegerField(read_only=True)
    data_inicio = serializers.DateField(read_only=True)
    data_fim = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    parcelas = serializers.SerializerMethodField()

    def _projection_cycle(self, obj) -> dict[str, object] | None:
        projection = build_contract_cycle_projection(obj.contrato)
        return next(
            (cycle for cycle in projection["cycles"] if int(cycle["numero"]) == obj.numero),
            None,
        )

    def get_status_visual_slug(self, obj) -> str:
        cycle = self._projection_cycle(obj)
        return str(cycle["status_visual_slug"]) if cycle else ""

    def get_status_visual_label(self, obj) -> str:
        cycle = self._projection_cycle(obj)
        return str(cycle["status_visual_label"]) if cycle else ""

    @extend_schema_field(AgentePagamentoParcelaSerializer(many=True))
    def get_parcelas(self, obj) -> list[dict[str, object]]:
        competencia: date | None = self.context.get("mes_filter")
        parcelas = list(obj.parcelas.all())
        if competencia:
            parcelas = [
                parcela
                for parcela in parcelas
                if parcela.referencia_mes.year == competencia.year
                and parcela.referencia_mes.month == competencia.month
            ]
        return AgentePagamentoParcelaSerializer(
            parcelas,
            many=True,
            context=self.context,
        ).data


class AgentePagamentoContratoSerializer(serializers.ModelSerializer):
    associado_id = serializers.IntegerField(source="associado.id", read_only=True)
    nome = serializers.CharField(source="associado.nome_completo", read_only=True)
    cpf_cnpj = serializers.CharField(source="associado.cpf_cnpj", read_only=True)
    contrato_codigo = serializers.CharField(source="codigo", read_only=True)
    status_contrato = serializers.CharField(source="status", read_only=True)
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    comprovantes_efetivacao = serializers.SerializerMethodField()
    pagamento_inicial_status = serializers.SerializerMethodField()
    pagamento_inicial_status_label = serializers.SerializerMethodField()
    pagamento_inicial_valor = serializers.SerializerMethodField()
    pagamento_inicial_paid_at = serializers.SerializerMethodField()
    pagamento_inicial_evidencias = serializers.SerializerMethodField()
    ciclos = serializers.SerializerMethodField()
    parcelas_total = serializers.SerializerMethodField()
    parcelas_pagas = serializers.SerializerMethodField()

    class Meta:
        model = Contrato
        fields = [
            "id",
            "associado_id",
            "nome",
            "cpf_cnpj",
            "contrato_codigo",
            "status_contrato",
            "status_visual_slug",
            "status_visual_label",
            "data_contrato",
            "auxilio_liberado_em",
            "pagamento_inicial_status",
            "pagamento_inicial_status_label",
            "pagamento_inicial_valor",
            "pagamento_inicial_paid_at",
            "valor_mensalidade",
            "comissao_agente",
            "parcelas_total",
            "parcelas_pagas",
            "comprovantes_efetivacao",
            "pagamento_inicial_evidencias",
            "ciclos",
        ]

    def _parcelas_visiveis(self, obj: Contrato) -> list[Parcela]:
        competencia: date | None = self.context.get("mes_filter")
        parcelas = [
            parcela
            for ciclo in obj.ciclos.all()
            for parcela in ciclo.parcelas.all()
        ]
        if not competencia:
            return parcelas
        return [
            parcela
            for parcela in parcelas
            if parcela.referencia_mes.year == competencia.year
            and parcela.referencia_mes.month == competencia.month
        ]

    def _initial_payment_payload(self, obj: Contrato):
        cache = self.context.setdefault("_initial_payment_payloads", {})
        if obj.pk not in cache:
            cache[obj.pk] = build_initial_payment_payload(
                obj,
                request=self.context.get("request"),
            )
        return cache[obj.pk]

    @extend_schema_field(AgentePagamentoComprovanteSerializer(many=True))
    def get_comprovantes_efetivacao(self, obj: Contrato) -> list[dict[str, object]]:
        comprovantes = self._initial_payment_payload(obj).evidencias
        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data

    @extend_schema_field(AgentePagamentoComprovanteSerializer(many=True))
    def get_pagamento_inicial_evidencias(self, obj: Contrato) -> list[dict[str, object]]:
        comprovantes = self._initial_payment_payload(obj).evidencias
        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data

    def get_pagamento_inicial_status(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status)

    def get_pagamento_inicial_status_label(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status_label)

    def get_pagamento_inicial_valor(self, obj: Contrato):
        valor = self._initial_payment_payload(obj).valor
        return f"{valor:.2f}" if valor is not None else None

    def get_pagamento_inicial_paid_at(self, obj: Contrato):
        return self._initial_payment_payload(obj).paid_at

    @extend_schema_field(AgentePagamentoCicloSerializer(many=True))
    def get_ciclos(self, obj: Contrato) -> list[dict[str, object]]:
        competencia: date | None = self.context.get("mes_filter")
        ciclos = list(obj.ciclos.all())
        if competencia:
            ciclos = [
                ciclo
                for ciclo in ciclos
                if any(
                    parcela.referencia_mes.year == competencia.year
                    and parcela.referencia_mes.month == competencia.month
                    for parcela in ciclo.parcelas.all()
                )
            ]

        pagamentos_por_referencia = {
            pagamento.referencia_month: pagamento
            for pagamento in obj.associado.pagamentos_mensalidades.all()
            if pagamento.manual_comprovante_path
        }
        serializer_context = {
            **self.context,
            "pagamentos_mensalidade_por_referencia": pagamentos_por_referencia,
        }
        return AgentePagamentoCicloSerializer(
            ciclos,
            many=True,
            context=serializer_context,
        ).data

    def get_parcelas_total(self, obj: Contrato) -> int:
        return len(self._parcelas_visiveis(obj))

    def get_parcelas_pagas(self, obj: Contrato) -> int:
        return len(
            [
                parcela
                for parcela in self._parcelas_visiveis(obj)
                if parcela.status == Parcela.Status.DESCONTADO
            ]
        )

    def get_status_visual_slug(self, obj: Contrato) -> str:
        return str(get_contract_visual_status_payload(obj)["status_visual_slug"])

    def get_status_visual_label(self, obj: Contrato) -> str:
        return str(get_contract_visual_status_payload(obj)["status_visual_label"])


class BaixaManualItemSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    associado_id = serializers.SerializerMethodField()
    nome = serializers.SerializerMethodField()
    cpf_cnpj = serializers.SerializerMethodField()
    matricula = serializers.SerializerMethodField()
    agente_nome = serializers.SerializerMethodField()
    contrato_id = serializers.SerializerMethodField()
    contrato_codigo = serializers.SerializerMethodField()
    referencia_mes = serializers.DateField(read_only=True)
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    data_vencimento = serializers.DateField(read_only=True)
    observacao = serializers.CharField(read_only=True)

    def _contrato(self, obj):
        return obj.ciclo.contrato

    def get_associado_id(self, obj) -> int:
        return self._contrato(obj).associado.id

    def get_nome(self, obj) -> str:
        return self._contrato(obj).associado.nome_completo

    def get_cpf_cnpj(self, obj) -> str:
        return self._contrato(obj).associado.cpf_cnpj

    def get_matricula(self, obj) -> str:
        assoc = self._contrato(obj).associado
        return assoc.matricula_orgao or assoc.matricula

    def get_agente_nome(self, obj) -> str:
        agente = self._contrato(obj).agente
        return agente.full_name if agente else ""

    def get_contrato_id(self, obj) -> int:
        return self._contrato(obj).id

    def get_contrato_codigo(self, obj) -> str:
        return self._contrato(obj).codigo


class DarBaixaManualSerializer(serializers.Serializer):
    comprovante = serializers.FileField(required=True)
    valor_pago = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    observacao = serializers.CharField(required=False, allow_blank=True, default="")
