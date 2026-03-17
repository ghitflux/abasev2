from __future__ import annotations

from rest_framework import serializers

from apps.associados.models import Associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_contract_visual_status_payload,
)
from apps.contratos.cycle_timeline import (
    get_contract_activation_payload,
    get_contract_cycle_size,
    get_cycle_activation_payload,
)
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.initial_payment import build_initial_payment_payload

from .models import Ciclo, Contrato, Parcela


def _projection_cache(
    context: dict[str, object],
) -> dict[int, dict[str, object]]:
    return context.setdefault("_contract_projection_cache", {})


def _get_contract_projection(
    context: dict[str, object],
    contrato: Contrato,
    *,
    include_documents: bool = False,
) -> dict[str, object]:
    cache = _projection_cache(context)
    if include_documents:
        key = -contrato.id
        if key not in cache:
            cache[key] = build_contract_cycle_projection(
                contrato,
                include_documents=True,
            )
        return cache[key]
    if contrato.id not in cache:
        cache[contrato.id] = build_contract_cycle_projection(contrato)
    return cache[contrato.id]


class AssociadoContratoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    nome_completo = serializers.CharField(read_only=True)
    matricula = serializers.CharField(read_only=True)
    matricula_display = serializers.CharField(read_only=True)
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


class ProjectedParcelaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.IntegerField()
    referencia_mes = serializers.DateField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = serializers.DateField()
    status = serializers.CharField()
    data_pagamento = serializers.DateField(allow_null=True)
    observacao = serializers.CharField()


class MesNaoPagoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    contrato_id = serializers.IntegerField()
    contrato_codigo = serializers.CharField()
    referencia_mes = serializers.DateField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=2)
    status = serializers.CharField()
    data_pagamento = serializers.DateField(allow_null=True)
    observacao = serializers.CharField()
    source = serializers.CharField(required=False)


class MovimentoFinanceiroAvulsoSerializer(MesNaoPagoSerializer):
    pass


class ProjectedComprovanteSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    tipo = serializers.CharField()
    papel = serializers.CharField()
    arquivo = serializers.CharField()
    arquivo_referencia = serializers.CharField()
    arquivo_disponivel_localmente = serializers.BooleanField()
    tipo_referencia = serializers.CharField()
    nome_original = serializers.CharField(allow_blank=True)
    mime = serializers.CharField(allow_blank=True)
    size_bytes = serializers.IntegerField(allow_null=True)
    data_pagamento = serializers.DateTimeField(allow_null=True)
    origem = serializers.CharField()
    created_at = serializers.DateTimeField(allow_null=True)
    legacy_comprovante_id = serializers.IntegerField(allow_null=True)


class EvidenceReferenceSerializer(serializers.Serializer):
    id = serializers.CharField()
    nome = serializers.CharField()
    url = serializers.CharField()
    arquivo_referencia = serializers.CharField()
    arquivo_disponivel_localmente = serializers.BooleanField()
    tipo_referencia = serializers.CharField()
    origem = serializers.CharField()
    papel = serializers.CharField()
    tipo = serializers.CharField()
    status = serializers.CharField()
    competencia = serializers.DateField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)


class InitialPaymentEvidenceSerializer(EvidenceReferenceSerializer):
    pass


class ProjectedCicloSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    contrato_id = serializers.IntegerField()
    contrato_codigo = serializers.CharField()
    contrato_status = serializers.CharField()
    numero = serializers.IntegerField()
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    status = serializers.CharField()
    fase_ciclo = serializers.CharField()
    situacao_financeira = serializers.CharField()
    status_visual_slug = serializers.CharField()
    status_visual_label = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_ativacao_ciclo = serializers.DateTimeField(allow_null=True)
    origem_data_ativacao = serializers.CharField()
    ativacao_inferida = serializers.BooleanField()
    data_solicitacao_renovacao = serializers.DateTimeField(allow_null=True)
    data_renovacao = serializers.DateTimeField(allow_null=True)
    origem_renovacao = serializers.CharField(allow_blank=True)
    primeira_competencia_ciclo = serializers.DateField()
    ultima_competencia_ciclo = serializers.DateField()
    resumo_referencias = serializers.CharField()
    refinanciamento_id = serializers.IntegerField(allow_null=True)
    legacy_refinanciamento_id = serializers.IntegerField(allow_null=True)
    comprovantes_ciclo = ProjectedComprovanteSerializer(many=True)
    termo_antecipacao = ProjectedComprovanteSerializer(allow_null=True)
    parcelas = ProjectedParcelaSerializer(many=True)


class AssociadoCiclosPayloadSerializer(serializers.Serializer):
    ciclos = ProjectedCicloSerializer(many=True)
    meses_nao_pagos = MesNaoPagoSerializer(many=True)


class ParcelaDetailQuerySerializer(serializers.Serializer):
    contrato_id = serializers.IntegerField()
    referencia_mes = serializers.DateField()
    kind = serializers.ChoiceField(choices=["cycle", "unpaid"])


class ParcelaDetailSerializer(serializers.Serializer):
    contrato_id = serializers.IntegerField()
    contrato_codigo = serializers.CharField()
    cycle_number = serializers.IntegerField(allow_null=True)
    numero_parcela = serializers.IntegerField(allow_null=True)
    kind = serializers.ChoiceField(choices=["cycle", "unpaid"])
    referencia_mes = serializers.DateField()
    status = serializers.CharField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = serializers.DateField(allow_null=True)
    observacao = serializers.CharField()
    data_pagamento = serializers.DateField(allow_null=True)
    data_importacao_arquivo = serializers.DateTimeField(allow_null=True)
    data_baixa_manual = serializers.DateField(allow_null=True)
    data_pagamento_tesouraria = serializers.DateTimeField(allow_null=True)
    origem_quitacao = serializers.CharField()
    origem_quitacao_label = serializers.CharField()
    competencia_evidencias = EvidenceReferenceSerializer(many=True)
    documentos_ciclo = EvidenceReferenceSerializer(many=True)
    termo_antecipacao = EvidenceReferenceSerializer(allow_null=True)


class CicloDetailSerializer(serializers.ModelSerializer):
    contrato_id = serializers.IntegerField(source="contrato.id", read_only=True)
    contrato_codigo = serializers.CharField(source="contrato.codigo", read_only=True)
    contrato_status = serializers.CharField(source="contrato.status", read_only=True)
    parcelas = ParcelaSerializer(many=True, read_only=True)
    data_ativacao_ciclo = serializers.SerializerMethodField()
    origem_data_ativacao = serializers.SerializerMethodField()
    ativacao_inferida = serializers.SerializerMethodField()
    data_solicitacao_renovacao = serializers.SerializerMethodField()
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()

    class Meta:
        model = Ciclo
        fields = [
            "id",
            "contrato_id",
            "contrato_codigo",
            "contrato_status",
            "numero",
            "data_inicio",
            "data_fim",
            "status",
            "status_visual_slug",
            "status_visual_label",
            "valor_total",
            "data_ativacao_ciclo",
            "origem_data_ativacao",
            "ativacao_inferida",
            "data_solicitacao_renovacao",
            "parcelas",
        ]

    def get_data_ativacao_ciclo(self, obj: Ciclo):
        return get_cycle_activation_payload(obj)["data_ativacao_ciclo"]

    def get_origem_data_ativacao(self, obj: Ciclo) -> str:
        return str(get_cycle_activation_payload(obj)["origem_data_ativacao"])

    def get_ativacao_inferida(self, obj: Ciclo) -> bool:
        return bool(get_cycle_activation_payload(obj)["ativacao_inferida"])

    def get_data_solicitacao_renovacao(self, obj: Ciclo):
        return get_cycle_activation_payload(obj)["data_solicitacao_renovacao"]

    def _projection_cycle(self, obj: Ciclo) -> dict[str, object] | None:
        projection = build_contract_cycle_projection(obj.contrato)
        return next(
            (cycle for cycle in projection["cycles"] if int(cycle["numero"]) == obj.numero),
            None,
        )

    def get_status_visual_slug(self, obj: Ciclo) -> str:
        cycle = self._projection_cycle(obj)
        return str(cycle["status_visual_slug"]) if cycle else ""

    def get_status_visual_label(self, obj: Ciclo) -> str:
        cycle = self._projection_cycle(obj)
        return str(cycle["status_visual_label"]) if cycle else ""


class ContratoResumoSerializer(serializers.ModelSerializer):
    ciclos = serializers.SerializerMethodField()
    meses_nao_pagos = serializers.SerializerMethodField()
    movimentos_financeiros_avulsos = serializers.SerializerMethodField()
    data_primeiro_ciclo_ativado = serializers.SerializerMethodField()
    origem_data_primeiro_ciclo = serializers.SerializerMethodField()
    primeiro_ciclo_ativacao_inferida = serializers.SerializerMethodField()
    status_renovacao = serializers.SerializerMethodField()
    refinanciamento_id = serializers.SerializerMethodField()
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()
    pagamento_inicial_status = serializers.SerializerMethodField()
    pagamento_inicial_status_label = serializers.SerializerMethodField()
    pagamento_inicial_valor = serializers.SerializerMethodField()
    pagamento_inicial_paid_at = serializers.SerializerMethodField()
    pagamento_inicial_evidencias = serializers.SerializerMethodField()

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
            "data_primeiro_ciclo_ativado",
            "origem_data_primeiro_ciclo",
            "primeiro_ciclo_ativacao_inferida",
            "status_visual_slug",
            "status_visual_label",
            "pagamento_inicial_status",
            "pagamento_inicial_status_label",
            "pagamento_inicial_valor",
            "pagamento_inicial_paid_at",
            "pagamento_inicial_evidencias",
            "status_renovacao",
            "refinanciamento_id",
            "meses_nao_pagos",
            "movimentos_financeiros_avulsos",
            "ciclos",
        ]

    def _initial_payment_payload(self, obj: Contrato):
        cache = self.context.setdefault("_initial_payment_payloads", {})
        if obj.pk not in cache:
            cache[obj.pk] = build_initial_payment_payload(
                obj,
                request=self.context.get("request"),
            )
        return cache[obj.pk]

    def get_data_primeiro_ciclo_ativado(self, obj: Contrato):
        return get_contract_activation_payload(obj)["data_primeiro_ciclo_ativado"]

    def get_origem_data_primeiro_ciclo(self, obj: Contrato) -> str:
        return str(get_contract_activation_payload(obj)["origem_data_primeiro_ciclo"])

    def get_primeiro_ciclo_ativacao_inferida(self, obj: Contrato) -> bool:
        return bool(get_contract_activation_payload(obj)["primeiro_ciclo_ativacao_inferida"])

    def get_ciclos(self, obj: Contrato):
        projection = _get_contract_projection(
            self.context,
            obj,
            include_documents=True,
        )
        return ProjectedCicloSerializer(projection["cycles"], many=True).data

    def get_meses_nao_pagos(self, obj: Contrato):
        projection = _get_contract_projection(self.context, obj)
        return MesNaoPagoSerializer(projection["unpaid_months"], many=True).data

    def get_movimentos_financeiros_avulsos(self, obj: Contrato):
        projection = _get_contract_projection(self.context, obj)
        return MovimentoFinanceiroAvulsoSerializer(
            projection["movimentos_financeiros_avulsos"],
            many=True,
        ).data

    def get_status_renovacao(self, obj: Contrato) -> str:
        return str(_get_contract_projection(self.context, obj)["status_renovacao"])

    def get_refinanciamento_id(self, obj: Contrato):
        return _get_contract_projection(self.context, obj)["refinanciamento_id"]

    def get_status_visual_slug(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(obj, projection=projection)["status_visual_slug"]
        )

    def get_status_visual_label(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(obj, projection=projection)["status_visual_label"]
        )

    def get_pagamento_inicial_status(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status)

    def get_pagamento_inicial_status_label(self, obj: Contrato) -> str:
        return str(self._initial_payment_payload(obj).status_label)

    def get_pagamento_inicial_valor(self, obj: Contrato):
        valor = self._initial_payment_payload(obj).valor
        return f"{valor:.2f}" if valor is not None else None

    def get_pagamento_inicial_paid_at(self, obj: Contrato):
        return self._initial_payment_payload(obj).paid_at

    def get_pagamento_inicial_evidencias(self, obj: Contrato):
        return InitialPaymentEvidenceSerializer(
            self._initial_payment_payload(obj).evidencias,
            many=True,
        ).data


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
    status_renovacao = serializers.SerializerMethodField()
    refinanciamento_id = serializers.SerializerMethodField()
    status_visual_slug = serializers.SerializerMethodField()
    status_visual_label = serializers.SerializerMethodField()

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
            "status_visual_slug",
            "status_visual_label",
            "etapa_fluxo",
            "data_contrato",
            "valor_mensalidade",
            "comissao_agente",
            "mensalidades",
            "auxilio_liberado_em",
            "pode_solicitar_refinanciamento",
            "status_renovacao",
            "refinanciamento_id",
        ]

    def get_status_resumido(self, obj: Contrato) -> str:
        return (
            "concluido"
            if obj.status in [Contrato.Status.ATIVO, Contrato.Status.ENCERRADO]
            else "pendente"
        )

    def get_status_contrato_visual(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        visual_slug = str(
            get_contract_visual_status_payload(obj, projection=projection)["status_visual_slug"]
        )
        if "ciclo_inadimplente" in visual_slug:
            return "inadimplente"
        if visual_slug in {"contrato_desativado", "contrato_encerrado"}:
            return "desativado"
        if visual_slug == "em_analise":
            return "pendente"
        return "ativo"

    def get_etapa_fluxo(self, obj: Contrato) -> str:
        try:
            esteira = obj.associado.esteira_item
        except Associado.esteira_item.RelatedObjectDoesNotExist:
            esteira = None
        if esteira:
            return esteira.etapa_atual
        return "concluido" if obj.auxilio_liberado_em else "analise"

    def get_mensalidades(self, obj: Contrato) -> dict[str, object]:
        projection = _get_contract_projection(self.context, obj)
        total = get_contract_cycle_size(obj)
        cycles = list(sorted(projection["cycles"], key=lambda item: item["numero"]))
        current_cycle = cycles[-1] if cycles else None
        pagas = (
            sum(
                1
                for parcela in current_cycle["parcelas"]
                if parcela["status"] == Parcela.Status.DESCONTADO
            )
            if current_cycle
            else 0
        )
        status_renovacao = str(projection["status_renovacao"])
        refinanciamento_ativo = bool(status_renovacao) and status_renovacao != Refinanciamento.Status.APTO_A_RENOVAR
        apto = status_renovacao == Refinanciamento.Status.APTO_A_RENOVAR
        return MensalidadesResumoSerializer(
            {
                "pagas": pagas,
                "total": total,
                "descricao": f"Parcelas quitadas no ciclo atual: {pagas}/{total}",
                "apto_refinanciamento": apto,
                "refinanciamento_ativo": refinanciamento_ativo,
            }
        ).data

    def get_pode_solicitar_refinanciamento(self, obj: Contrato) -> bool:
        return False

    def get_status_renovacao(self, obj: Contrato) -> str:
        return str(_get_contract_projection(self.context, obj)["status_renovacao"])

    def get_refinanciamento_id(self, obj: Contrato):
        return _get_contract_projection(self.context, obj)["refinanciamento_id"]

    def get_status_visual_slug(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(obj, projection=projection)["status_visual_slug"]
        )

    def get_status_visual_label(self, obj: Contrato) -> str:
        projection = _get_contract_projection(self.context, obj)
        return str(
            get_contract_visual_status_payload(obj, projection=projection)["status_visual_label"]
        )


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
    status_explicacao = serializers.CharField(allow_blank=True)
    data_primeiro_ciclo_ativado = serializers.DateTimeField(allow_null=True)
    data_ativacao_ciclo = serializers.DateTimeField(allow_null=True)
    origem_data_ativacao = serializers.CharField()
    data_solicitacao_renovacao = serializers.DateTimeField(allow_null=True)
    ativacao_inferida = serializers.BooleanField()
    matricula = serializers.CharField()
    agente_responsavel = serializers.CharField()
    parcelas_pagas = serializers.IntegerField()
    parcelas_total = serializers.IntegerField()
    contrato_referencia_renovacao_id = serializers.IntegerField()
    contrato_referencia_renovacao_codigo = serializers.CharField()
    possui_multiplos_contratos = serializers.BooleanField()
    valor_mensalidade = serializers.DecimalField(max_digits=10, decimal_places=2)
    valor_parcela = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = serializers.DateField(allow_null=True)
    orgao_pagto_nome = serializers.CharField(allow_blank=True)
    resultado_importacao = serializers.CharField()
    status_codigo_etipi = serializers.CharField(allow_blank=True)
    status_descricao_etipi = serializers.CharField(allow_blank=True)
    gerou_encerramento = serializers.BooleanField()
    gerou_novo_ciclo = serializers.BooleanField()
