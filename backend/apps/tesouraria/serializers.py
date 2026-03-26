from __future__ import annotations

from datetime import date
from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.associados.serializers import DadosBancariosSerializer, SimpleUserSerializer
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_contract_visual_status_payload,
)
from apps.contratos.parcela_detail import _query_actual_parcela, _query_retorno_items
from apps.contratos.models import Contrato, Parcela
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetorno, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.refinanciamento.serializers import ComprovanteResumoSerializer
from apps.tesouraria.initial_payment import build_initial_payment_payload
from apps.tesouraria.models import LiquidacaoContrato
from apps.tesouraria.payment_evidence import (
    build_competencia_evidence_payload,
    canonicalize_pagamentos,
)
from apps.tesouraria.models import BaixaManual, DevolucaoAssociado
from core.file_references import build_filefield_reference, build_storage_reference


def _is_agent_restricted(context: dict) -> bool:
    request = context.get("request")
    if not request or not getattr(request, "user", None):
        return False
    user = request.user
    if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
        return False
    return user.has_role("AGENTE") and not user.has_role("ADMIN")


def _projection_cache(
    context: dict[str, object],
) -> dict[int, dict[str, object]]:
    return context.setdefault("_contract_projection_cache", {})


def _get_contract_projection(
    context: dict[str, object],
    contrato: Contrato,
) -> dict[str, object]:
    cache = _projection_cache(context)
    if contrato.id not in cache:
        cache[contrato.id] = build_contract_cycle_projection(contrato)
    return cache[contrato.id]


def _prefetched_pagamento_por_referencia(
    contrato: Contrato,
) -> dict[date, PagamentoMensalidade]:
    pagamentos = list(getattr(contrato.associado, "pagamentos_mensalidades").all())
    canonical = canonicalize_pagamentos(pagamentos)
    return {pagamento.referencia_month: pagamento for pagamento in canonical}


class TesourariaContratoListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    associado_id = serializers.IntegerField(source="associado.id", read_only=True)
    nome = serializers.CharField(source="associado.nome_completo", read_only=True)
    cpf_cnpj = serializers.CharField(source="associado.cpf_cnpj", read_only=True)
    matricula = serializers.SerializerMethodField()
    chave_pix = serializers.SerializerMethodField()
    codigo = serializers.CharField(read_only=True)
    data_assinatura = serializers.DateTimeField(source="created_at", read_only=True)
    status = serializers.SerializerMethodField()
    agente = SimpleUserSerializer(read_only=True)
    agente_nome = serializers.CharField(source="agente.full_name", read_only=True)
    percentual_repasse = serializers.SerializerMethodField()
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

    def get_matricula(self, obj) -> str:
        associado = obj.associado
        return associado.matricula_orgao or associado.matricula or ""

    def get_percentual_repasse(self, obj) -> str:
        associado = obj.associado
        return f"{associado.auxilio_taxa:.2f}"

    @extend_schema_field(ComprovanteResumoSerializer(many=True))
    def get_comprovantes(self, obj):
        comprovantes = obj.comprovantes.filter(refinanciamento__isnull=True)
        return ComprovanteResumoSerializer(comprovantes, many=True).data

    def get_chave_pix(self, obj) -> str:
        payload = obj.associado.build_dados_bancarios_payload() or {}
        return payload.get("chave_pix", "")

    @extend_schema_field(DadosBancariosSerializer(allow_null=True))
    def get_dados_bancarios(self, obj):
        payload = obj.associado.build_dados_bancarios_payload()
        if not payload:
            return None
        return DadosBancariosSerializer(payload).data


class EfetivarContratoSerializer(serializers.Serializer):
    comprovante_associado = serializers.FileField(required=True)
    comprovante_agente = serializers.FileField(required=True)


class SubstituirComprovanteSerializer(serializers.Serializer):
    papel = serializers.ChoiceField(
        choices=[
            Comprovante.Papel.ASSOCIADO,
            Comprovante.Papel.AGENTE,
        ]
    )
    arquivo = serializers.FileField(required=True)


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
    def get_comprovantes(self, obj: Parcela | dict[str, Any]) -> list[dict[str, object]]:
        referencia_mes = (
            obj.get("referencia_mes")
            if isinstance(obj, dict)
            else obj.referencia_mes
        )
        pagamento_mensalidade = None
        if isinstance(obj, dict):
            pagamento_mensalidade = obj.get("_pagamento_mensalidade")
        if pagamento_mensalidade is None:
            pagamentos_manuais = self.context.get("pagamentos_mensalidade_por_referencia", {})
            pagamento_mensalidade = pagamentos_manuais.get(referencia_mes)
        evidence_payload = build_competencia_evidence_payload(
            referencia_mes=referencia_mes,
            arquivo_items=(
                obj.get("_arquivo_items", [])
                if isinstance(obj, dict)
                else obj.itens_retorno.all()
            ),
            pagamento_mensalidade=pagamento_mensalidade,
            baixa_manual=(
                obj.get("_baixa_manual")
                if isinstance(obj, dict)
                else getattr(obj, "baixa_manual", None)
            ),
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
    status_visual_slug = serializers.CharField(read_only=True)
    status_visual_label = serializers.CharField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    parcelas = serializers.SerializerMethodField()

    @extend_schema_field(AgentePagamentoParcelaSerializer(many=True))
    def get_parcelas(self, obj) -> list[dict[str, object]]:
        competencia: date | None = self.context.get("mes_filter")
        parcelas = list(obj.get("parcelas", []))
        if competencia:
            parcelas = [
                parcela
                for parcela in parcelas
                if parcela["referencia_mes"].year == competencia.year
                and parcela["referencia_mes"].month == competencia.month
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
    agente_nome = serializers.CharField(source="agente.full_name", read_only=True, default="")
    status_contrato = serializers.CharField(source="status", read_only=True)
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    possui_meses_nao_descontados = serializers.SerializerMethodField()
    meses_nao_descontados_count = serializers.SerializerMethodField()
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
            "agente_nome",
            "status_contrato",
            "status_visual_slug",
            "status_visual_label",
            "possui_meses_nao_descontados",
            "meses_nao_descontados_count",
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
        projection = _get_contract_projection(self.context, obj)
        competencia: date | None = self.context.get("mes_filter")
        parcelas = [
            parcela
            for ciclo in projection["cycles"]
            for parcela in ciclo["parcelas"]
        ]
        if not competencia:
            return parcelas
        return [
            parcela
            for parcela in parcelas
            if parcela["referencia_mes"].year == competencia.year
            and parcela["referencia_mes"].month == competencia.month
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
        if _is_agent_restricted(self.context):
            comprovantes = [
                comprovante
                for comprovante in comprovantes
                if str(comprovante.get("papel", "")).lower() == "agente"
            ]
        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data

    @extend_schema_field(AgentePagamentoComprovanteSerializer(many=True))
    def get_pagamento_inicial_evidencias(self, obj: Contrato) -> list[dict[str, object]]:
        comprovantes = self._initial_payment_payload(obj).evidencias
        if _is_agent_restricted(self.context):
            comprovantes = [
                comprovante
                for comprovante in comprovantes
                if str(comprovante.get("papel", "")).lower() == "agente"
            ]
        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data

    def get_pagamento_inicial_status(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status)

    def get_pagamento_inicial_status_label(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status_label)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_pagamento_inicial_valor(self, obj: Contrato) -> str | None:
        valor = self._initial_payment_payload(obj).valor
        return f"{valor:.2f}" if valor is not None else None

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_pagamento_inicial_paid_at(self, obj: Contrato):
        return self._initial_payment_payload(obj).paid_at

    @extend_schema_field(AgentePagamentoCicloSerializer(many=True))
    def get_ciclos(self, obj: Contrato) -> list[dict[str, object]]:
        competencia: date | None = self.context.get("mes_filter")
        projection = _get_contract_projection(self.context, obj)
        ciclos = list(projection["cycles"])
        if competencia:
            ciclos = [
                ciclo
                for ciclo in ciclos
                if any(
                    parcela["referencia_mes"].year == competencia.year
                    and parcela["referencia_mes"].month == competencia.month
                    for parcela in ciclo["parcelas"]
                )
            ]

        pagamentos_por_referencia = _prefetched_pagamento_por_referencia(obj)
        ciclos_payload: list[dict[str, object]] = []
        for ciclo in ciclos:
            parcelas_payload: list[dict[str, object]] = []
            for parcela in ciclo["parcelas"]:
                referencia_mes = parcela["referencia_mes"]
                actual_parcela = _query_actual_parcela(
                    contrato=obj,
                    referencia_mes=referencia_mes,
                )
                parcelas_payload.append(
                    {
                        **parcela,
                        "_pagamento_mensalidade": pagamentos_por_referencia.get(
                            referencia_mes
                        ),
                        "_arquivo_items": _query_retorno_items(
                            contrato=obj,
                            referencia_mes=referencia_mes,
                            parcela=actual_parcela,
                        ),
                        "_baixa_manual": getattr(actual_parcela, "baixa_manual", None),
                    }
                )
            ciclos_payload.append(
                {
                    **ciclo,
                    "parcelas": parcelas_payload,
                }
            )

        serializer_context = {
            **self.context,
            "pagamentos_mensalidade_por_referencia": pagamentos_por_referencia,
        }
        return AgentePagamentoCicloSerializer(
            ciclos_payload,
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
                if parcela["status"] == Parcela.Status.DESCONTADO
            ]
        )

    def get_status_visual_slug(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(
                obj,
                projection=projection,
            )["status_visual_slug"]
        )

    def get_status_visual_label(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(
                obj,
                projection=projection,
            )["status_visual_label"]
        )

    def get_possui_meses_nao_descontados(self, obj: Contrato) -> bool:
        projection = _get_contract_projection(self.context, obj)
        return bool(projection["possui_meses_nao_descontados"])

    def get_meses_nao_descontados_count(self, obj: Contrato) -> int:
        projection = _get_contract_projection(self.context, obj)
        return int(projection["meses_nao_descontados_count"])


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


class LiquidacaoParcelaSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    numero = serializers.IntegerField(read_only=True)
    referencia_mes = serializers.DateField(read_only=True)
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    data_vencimento = serializers.DateField(read_only=True, allow_null=True)
    data_pagamento = serializers.DateField(read_only=True, allow_null=True)
    observacao = serializers.CharField(read_only=True)


class LiquidacaoComprovanteSerializer(serializers.Serializer):
    nome = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    arquivo_referencia = serializers.CharField(read_only=True)
    arquivo_disponivel_localmente = serializers.BooleanField(read_only=True)
    tipo_referencia = serializers.CharField(read_only=True)


class LiquidacaoAnexoSerializer(LiquidacaoComprovanteSerializer):
    pass


class LiquidacaoContratoListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    contrato_id = serializers.IntegerField(read_only=True, allow_null=True)
    liquidacao_id = serializers.IntegerField(read_only=True, allow_null=True)
    associado_id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)
    agente_nome = serializers.CharField(read_only=True, allow_blank=True)
    contrato_codigo = serializers.CharField(read_only=True, allow_blank=True)
    quantidade_parcelas = serializers.IntegerField(read_only=True)
    quantidade_parcelas_contrato = serializers.IntegerField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    referencia_inicial = serializers.DateField(read_only=True, allow_null=True)
    referencia_final = serializers.DateField(read_only=True, allow_null=True)
    status_liquidacao = serializers.CharField(read_only=True)
    status_operacional = serializers.CharField(read_only=True, allow_blank=True)
    pode_liquidar_agora = serializers.BooleanField(read_only=True)
    status_associado = serializers.CharField(read_only=True, allow_blank=True)
    status_associado_label = serializers.CharField(read_only=True, allow_blank=True)
    status_contrato = serializers.CharField(read_only=True, allow_blank=True)
    status_renovacao = serializers.CharField(read_only=True, allow_blank=True)
    origem_solicitacao = serializers.CharField(read_only=True, allow_blank=True)
    data_liquidacao = serializers.DateField(read_only=True, allow_null=True)
    observacao = serializers.CharField(read_only=True, allow_blank=True)
    realizado_por = SimpleUserSerializer(read_only=True, allow_null=True)
    revertida_em = serializers.DateTimeField(read_only=True, allow_null=True)
    revertida_por = SimpleUserSerializer(read_only=True, allow_null=True)
    motivo_reversao = serializers.CharField(read_only=True, allow_blank=True)
    comprovante = serializers.SerializerMethodField()
    anexos = serializers.SerializerMethodField()
    parcelas = LiquidacaoParcelaSerializer(many=True, read_only=True)
    pode_reverter = serializers.SerializerMethodField()

    @extend_schema_field(LiquidacaoComprovanteSerializer(allow_null=True))
    def get_comprovante(self, obj: dict[str, Any]) -> dict[str, object] | None:
        comprovante = obj.get("comprovante_obj")
        if not comprovante:
            return None
        reference = build_filefield_reference(
            comprovante,
            request=self.context.get("request"),
            missing_type="legado_sem_arquivo",
        )
        return {
            "nome": obj.get("nome_comprovante") or comprovante.name.rsplit("/", 1)[-1],
            "url": reference.url,
            "arquivo_referencia": reference.arquivo_referencia,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
        }

    @extend_schema_field(LiquidacaoAnexoSerializer(many=True))
    def get_anexos(self, obj: dict[str, Any]) -> list[dict[str, object]]:
        anexos: list[dict[str, object]] = []
        comprovante = self.get_comprovante(obj)
        if comprovante:
            anexos.append(comprovante)

        request = self.context.get("request")
        for anexo in obj.get("anexos_obj", []):
            reference = build_filefield_reference(
                anexo.arquivo,
                request=request,
                missing_type="legado_sem_arquivo",
            )
            anexos.append(
                {
                    "nome": anexo.nome_arquivo or anexo.arquivo.name.rsplit("/", 1)[-1],
                    "url": reference.url,
                    "arquivo_referencia": reference.arquivo_referencia,
                    "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                    "tipo_referencia": reference.tipo_referencia,
                }
            )
        return anexos

    def get_pode_reverter(self, obj: dict[str, Any]) -> bool:
        return obj.get("status_liquidacao") == "liquidado"

class LiquidacaoKpisSerializer(serializers.Serializer):
    total_contratos = serializers.IntegerField(read_only=True)
    total_parcelas = serializers.IntegerField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    associados_impactados = serializers.IntegerField(read_only=True)
    revertidas = serializers.IntegerField(read_only=True)
    ativas = serializers.IntegerField(read_only=True)
    liquidaveis_agora = serializers.IntegerField(read_only=True)
    sem_parcelas_elegiveis = serializers.IntegerField(read_only=True)
    por_status_associado = serializers.DictField(
        child=serializers.IntegerField(read_only=True),
        read_only=True,
    )


class LiquidarContratoSerializer(serializers.Serializer):
    origem_solicitacao = serializers.ChoiceField(
        choices=LiquidacaoContrato.OrigemSolicitacao.choices,
        required=True,
    )
    data_liquidacao = serializers.DateField(required=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    observacao = serializers.CharField(required=True, allow_blank=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        files = []
        if request is not None:
            files.extend(request.FILES.getlist("comprovantes"))
            single = request.FILES.get("comprovante")
            if single is not None and single not in files:
                files.append(single)
        if not files:
            raise serializers.ValidationError(
                {"comprovantes": "Envie pelo menos um comprovante."}
            )
        attrs["comprovantes"] = files
        return attrs


class ReverterLiquidacaoSerializer(serializers.Serializer):
    motivo_reversao = serializers.CharField(required=True, allow_blank=False)


class ExcluirLiquidacaoSerializer(serializers.Serializer):
    motivo_exclusao = serializers.CharField(required=True, allow_blank=False)


class DevolucaoContratoListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    contrato_id = serializers.IntegerField(read_only=True)
    associado_id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True, allow_blank=True)
    agente_nome = serializers.CharField(read_only=True, allow_blank=True)
    contrato_codigo = serializers.CharField(read_only=True)
    status_contrato = serializers.CharField(read_only=True)
    data_contrato = serializers.DateField(read_only=True)
    mes_averbacao = serializers.DateField(read_only=True, allow_null=True)


class DevolucaoComprovanteSerializer(serializers.Serializer):
    nome = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    arquivo_referencia = serializers.CharField(read_only=True)
    arquivo_disponivel_localmente = serializers.BooleanField(read_only=True)
    tipo_referencia = serializers.CharField(read_only=True)


class DevolucaoAnexoSerializer(DevolucaoComprovanteSerializer):
    pass


class DevolucaoAssociadoListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    devolucao_id = serializers.IntegerField(read_only=True)
    contrato_id = serializers.IntegerField(read_only=True)
    associado_id = serializers.IntegerField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    status_devolucao = serializers.CharField(read_only=True)
    data_devolucao = serializers.DateField(read_only=True)
    quantidade_parcelas = serializers.IntegerField(read_only=True)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    motivo = serializers.CharField(read_only=True)
    competencia_referencia = serializers.DateField(read_only=True, allow_null=True)
    nome = serializers.CharField(read_only=True)
    cpf_cnpj = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True, allow_blank=True)
    agente_nome = serializers.CharField(read_only=True, allow_blank=True)
    contrato_codigo = serializers.CharField(read_only=True)
    status_contrato = serializers.CharField(read_only=True)
    realizado_por = SimpleUserSerializer(read_only=True, allow_null=True)
    revertida_em = serializers.DateTimeField(read_only=True, allow_null=True)
    revertida_por = SimpleUserSerializer(read_only=True, allow_null=True)
    motivo_reversao = serializers.CharField(read_only=True, allow_blank=True)
    comprovante = serializers.SerializerMethodField()
    anexos = serializers.SerializerMethodField()
    pode_reverter = serializers.SerializerMethodField()

    @extend_schema_field(DevolucaoComprovanteSerializer(allow_null=True))
    def get_comprovante(self, obj: dict[str, Any]) -> dict[str, object] | None:
        comprovante = obj.get("comprovante_obj")
        if not comprovante:
            return None
        reference = build_filefield_reference(
            comprovante,
            request=self.context.get("request"),
            missing_type="legado_sem_arquivo",
        )
        return {
            "nome": obj.get("nome_comprovante") or comprovante.name.rsplit("/", 1)[-1],
            "url": reference.url,
            "arquivo_referencia": reference.arquivo_referencia,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
        }

    @extend_schema_field(DevolucaoAnexoSerializer(many=True))
    def get_anexos(self, obj: dict[str, Any]) -> list[dict[str, object]]:
        anexos: list[dict[str, object]] = []
        comprovante = self.get_comprovante(obj)
        if comprovante:
            anexos.append(comprovante)

        request = self.context.get("request")
        for anexo in obj.get("anexos_obj", []):
            reference = build_filefield_reference(
                anexo.arquivo,
                request=request,
                missing_type="legado_sem_arquivo",
            )
            anexos.append(
                {
                    "nome": anexo.nome_arquivo or anexo.arquivo.name.rsplit("/", 1)[-1],
                    "url": reference.url,
                    "arquivo_referencia": reference.arquivo_referencia,
                    "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                    "tipo_referencia": reference.tipo_referencia,
                }
            )
        return anexos

    def get_pode_reverter(self, obj: dict[str, Any]) -> bool:
        return obj.get("status_devolucao") == "registrada"


class DevolucaoKpisSerializer(serializers.Serializer):
    total_contratos = serializers.IntegerField(read_only=True)
    associados_impactados = serializers.IntegerField(read_only=True)
    ativos = serializers.IntegerField(read_only=True)
    encerrados = serializers.IntegerField(read_only=True)
    cancelados = serializers.IntegerField(read_only=True)
    total_registros = serializers.IntegerField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    registradas = serializers.IntegerField(read_only=True)
    revertidas = serializers.IntegerField(read_only=True)


class RegistrarDevolucaoSerializer(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=DevolucaoAssociado.Tipo.choices, required=True)
    data_devolucao = serializers.DateField(required=True)
    quantidade_parcelas = serializers.IntegerField(required=True, min_value=1)
    valor = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    motivo = serializers.CharField(required=True, allow_blank=False)
    competencia_referencia = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        files = []
        if request is not None:
            files.extend(request.FILES.getlist("comprovantes"))
            single = request.FILES.get("comprovante")
            if single is not None and single not in files:
                files.append(single)
        if not files:
            raise serializers.ValidationError(
                {"comprovantes": "Envie pelo menos um anexo."}
            )
        attrs["comprovantes"] = files
        return attrs


class ReverterDevolucaoSerializer(serializers.Serializer):
    motivo_reversao = serializers.CharField(required=True, allow_blank=False)


class ExcluirDevolucaoSerializer(serializers.Serializer):
    motivo_exclusao = serializers.CharField(required=True, allow_blank=False)


class DespesaAnexoSerializer(serializers.Serializer):
    nome = serializers.CharField(read_only=True)
    url = serializers.CharField(read_only=True)
    arquivo_referencia = serializers.CharField(read_only=True)
    arquivo_disponivel_localmente = serializers.BooleanField(read_only=True)
    tipo_referencia = serializers.CharField(read_only=True)


class DespesaListSerializer(serializers.ModelSerializer):
    lancado_por = SimpleUserSerializer(source="user", read_only=True)
    anexo = serializers.SerializerMethodField()

    class Meta:
        model = Despesa
        fields = [
            "id",
            "categoria",
            "descricao",
            "valor",
            "data_despesa",
            "data_pagamento",
            "status",
            "tipo",
            "recorrencia",
            "recorrencia_ativa",
            "observacoes",
            "status_anexo",
            "anexo",
            "lancado_por",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(DespesaAnexoSerializer(allow_null=True))
    def get_anexo(self, obj: Despesa) -> dict[str, object] | None:
        if not obj.anexo:
            return None

        reference = build_filefield_reference(
            obj.anexo,
            request=self.context.get("request"),
            missing_type="legado_sem_arquivo",
        )
        return {
            "nome": obj.nome_anexo or obj.anexo.name.rsplit("/", 1)[-1],
            "url": reference.url,
            "arquivo_referencia": reference.arquivo_referencia,
            "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
            "tipo_referencia": reference.tipo_referencia,
        }


class DespesaKpisSerializer(serializers.Serializer):
    total_despesas = serializers.IntegerField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    valor_pago = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    valor_pendente = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    pendentes_anexo = serializers.IntegerField(read_only=True)


class DespesaWriteSerializer(serializers.ModelSerializer):
    anexo = serializers.FileField(required=False, allow_null=True)
    data_pagamento = serializers.DateField(required=False, allow_null=True)
    tipo = serializers.ChoiceField(
        choices=Despesa.Tipo.choices,
        required=False,
        allow_blank=True,
    )
    recorrencia = serializers.ChoiceField(
        choices=Despesa.Recorrencia.choices,
        required=False,
    )

    class Meta:
        model = Despesa
        fields = [
            "categoria",
            "descricao",
            "valor",
            "data_despesa",
            "data_pagamento",
            "status",
            "tipo",
            "recorrencia",
            "recorrencia_ativa",
            "observacoes",
            "anexo",
        ]

    def validate(self, attrs):
        instance: Despesa | None = getattr(self, "instance", None)
        resolved_status = attrs.get(
            "status",
            instance.status if instance else Despesa.Status.PENDENTE,
        )
        resolved_data_pagamento = attrs.get(
            "data_pagamento",
            instance.data_pagamento if instance else None,
        )

        if resolved_status == Despesa.Status.PAGO and resolved_data_pagamento is None:
            raise serializers.ValidationError(
                {
                    "data_pagamento": "A data de pagamento é obrigatória quando a despesa estiver paga."
                }
            )

        if resolved_status == Despesa.Status.PENDENTE:
            attrs["data_pagamento"] = None

        return attrs

    def create(self, validated_data):
        anexo = validated_data.pop("anexo", None)
        request = self.context["request"]
        validated_data.setdefault("status", Despesa.Status.PENDENTE)
        validated_data.setdefault("recorrencia", Despesa.Recorrencia.NENHUMA)
        validated_data.setdefault("recorrencia_ativa", True)
        despesa = Despesa(user=request.user, **validated_data)
        if anexo:
            despesa.anexo = anexo
            despesa.nome_anexo = getattr(anexo, "name", "")[:255]
            despesa.status_anexo = Despesa.StatusAnexo.ANEXADO
        else:
            despesa.status_anexo = Despesa.StatusAnexo.PENDENTE
        despesa.save()
        return despesa

    def update(self, instance, validated_data):
        anexo = validated_data.pop("anexo", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        if anexo:
            instance.anexo = anexo
            instance.nome_anexo = getattr(anexo, "name", "")[:255]
            instance.status_anexo = Despesa.StatusAnexo.ANEXADO

        if not instance.anexo:
            instance.status_anexo = Despesa.StatusAnexo.PENDENTE
            instance.nome_anexo = ""

        instance.save()
        return instance


class DespesaAnexarSerializer(serializers.Serializer):
    anexo = serializers.FileField(required=True)
