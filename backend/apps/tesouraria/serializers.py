from __future__ import annotations

from datetime import date

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers

from apps.associados.serializers import DadosBancariosSerializer, SimpleUserSerializer
from apps.contratos.models import Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.serializers import ComprovanteResumoSerializer
from apps.tesouraria.models import BaixaManual


def _build_absolute_url(request, path: str) -> str:
    if path.startswith(("http://", "https://")):
        return path
    if request:
        return request.build_absolute_uri(path)
    return path


def _build_storage_url(request, path: str | None) -> str:
    if not path:
        return ""
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith(settings.MEDIA_URL):
        return _build_absolute_url(request, path)
    normalized_path = path.lstrip("/")
    try:
        return _build_absolute_url(request, default_storage.url(normalized_path))
    except Exception:
        return _build_absolute_url(
            request,
            f"{settings.MEDIA_URL.rstrip('/')}/{normalized_path}",
        )


def _build_filefield_url(request, arquivo) -> str:
    if not arquivo:
        return ""
    try:
        return _build_absolute_url(request, arquivo.url)
    except Exception:
        return _build_storage_url(request, getattr(arquivo, "name", ""))


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

    def get_comprovantes(self, obj: Parcela) -> list[dict[str, object]]:
        request = self.context.get("request")
        comprovantes: list[dict[str, object]] = []

        for item in obj.itens_retorno.all():
            arquivo = getattr(item, "arquivo_retorno", None)
            if not arquivo or not arquivo.arquivo_url:
                continue
            comprovantes.append(
                {
                    "id": f"retorno-{item.id}",
                    "nome": arquivo.arquivo_nome or f"Arquivo retorno {obj.referencia_mes:%m/%Y}",
                    "url": _build_storage_url(request, arquivo.arquivo_url),
                    "origem": "arquivo_retorno",
                    "papel": "",
                    "tipo": "arquivo_retorno",
                    "status": item.resultado_processamento or "",
                    "competencia": obj.referencia_mes,
                    "created_at": arquivo.created_at,
                }
            )

        pagamentos_manuais = self.context.get("pagamentos_mensalidade_por_referencia", {})
        pagamento_mensalidade: PagamentoMensalidade | None = pagamentos_manuais.get(
            obj.referencia_mes
        )
        if pagamento_mensalidade and pagamento_mensalidade.manual_comprovante_path:
            comprovantes.append(
                {
                    "id": f"manual-{pagamento_mensalidade.id}",
                    "nome": (
                        pagamento_mensalidade.manual_forma_pagamento
                        or "Comprovante manual"
                    ),
                    "url": _build_storage_url(
                        request, pagamento_mensalidade.manual_comprovante_path
                    ),
                    "origem": "manual",
                    "papel": "",
                    "tipo": "manual",
                    "status": pagamento_mensalidade.manual_status or "",
                    "competencia": obj.referencia_mes,
                    "created_at": (
                        pagamento_mensalidade.manual_paid_at
                        or pagamento_mensalidade.created_at
                    ),
                }
            )

        baixa_manual: BaixaManual | None = getattr(obj, "baixa_manual", None)
        if baixa_manual and baixa_manual.comprovante:
            comprovantes.append(
                {
                    "id": f"baixa-manual-{baixa_manual.id}",
                    "nome": baixa_manual.nome_comprovante or "Comprovante baixa manual",
                    "url": _build_filefield_url(request, baixa_manual.comprovante),
                    "origem": "baixa_manual",
                    "papel": "",
                    "tipo": "baixa_manual",
                    "status": "baixa_efetuada",
                    "competencia": obj.referencia_mes,
                    "created_at": baixa_manual.created_at,
                }
            )

        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data


class AgentePagamentoCicloSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    numero = serializers.IntegerField(read_only=True)
    data_inicio = serializers.DateField(read_only=True)
    data_fim = serializers.DateField(read_only=True)
    status = serializers.CharField(read_only=True)
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    parcelas = serializers.SerializerMethodField()

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
    comprovantes_efetivacao = serializers.SerializerMethodField()
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
            "data_contrato",
            "auxilio_liberado_em",
            "valor_mensalidade",
            "comissao_agente",
            "parcelas_total",
            "parcelas_pagas",
            "comprovantes_efetivacao",
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

    def get_comprovantes_efetivacao(self, obj: Contrato) -> list[dict[str, object]]:
        request = self.context.get("request")
        comprovantes = [
            {
                "id": f"contrato-{comprovante.id}",
                "nome": (
                    comprovante.nome_original
                    or f"Comprovante {comprovante.get_papel_display()}"
                ),
                "url": _build_filefield_url(request, comprovante.arquivo),
                "origem": "efetivacao_contrato",
                "papel": comprovante.papel,
                "tipo": comprovante.tipo,
                "status": "",
                "competencia": None,
                "created_at": comprovante.created_at,
            }
            for comprovante in obj.comprovantes.all()
            if comprovante.refinanciamento_id is None
        ]
        return AgentePagamentoComprovanteSerializer(comprovantes, many=True).data

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
