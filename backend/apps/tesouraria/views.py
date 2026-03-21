from __future__ import annotations

from datetime import datetime

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.accounts.permissions import (
    IsAgenteOrTesoureiroOrAdmin,
    IsCoordenadorOrTesoureiroOrAdmin,
    IsTesoureiroOrAdmin,
)
from apps.associados.serializers import DadosBancariosSerializer
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.tesouraria.models import Confirmacao, Pagamento, PagamentoNotificacao
from core.pagination import StandardResultsSetPagination

from .serializers import (
    AgentePagamentoContratoSerializer,
    BaixaManualItemSerializer,
    ConfirmacaoLinkSerializer,
    ConfirmacaoListSerializer,
    CongelarContratoSerializer,
    DespesaAnexarSerializer,
    DespesaListSerializer,
    DespesaWriteSerializer,
    DarBaixaManualSerializer,
    EfetivarContratoSerializer,
    TesourariaContratoListSerializer,
)
from .services import (
    BaixaManualService,
    ConfirmacaoService,
    DespesaService,
    TesourariaService,
    parse_competencia,
)


def parse_month_filter(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None


class TesourariaContratoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = TesourariaContratoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        competencia = parse_competencia(self.request.query_params.get("competencia"))
        return TesourariaService.listar_contratos_pendentes(
            competencia=competencia,
            data_inicio=self.request.query_params.get("data_inicio"),
            data_fim=self.request.query_params.get("data_fim"),
            search=self.request.query_params.get("search"),
            pagamento=self.request.query_params.get("pagamento"),
        )

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def efetivar(self, request, pk=None):
        payload = EfetivarContratoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contrato = TesourariaService.efetivar_contrato(
            pk,
            payload.validated_data["comprovante_associado"],
            payload.validated_data["comprovante_agente"],
            request.user,
        )
        serializer = self.get_serializer(contrato)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def congelar(self, request, pk=None):
        payload = CongelarContratoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contrato = TesourariaService.congelar_contrato(
            pk, payload.validated_data["motivo"], request.user
        )
        serializer = self.get_serializer(contrato)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="dados-bancarios")
    def dados_bancarios(self, request, pk=None):
        dados = TesourariaService.obter_dados_bancarios(pk)
        serializer = DadosBancariosSerializer(dados)
        return Response(serializer.data)


class ConfirmacaoViewSet(GenericViewSet):
    queryset = Confirmacao.objects.none()
    serializer_class = ConfirmacaoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def list(self, request):
        competencia = parse_competencia(request.query_params.get("competencia"))
        search = request.query_params.get("search", "").strip().lower()
        rows = ConfirmacaoService.listar_por_competencia(competencia)
        if search:
            rows = [row for row in rows if search in row["nome"].lower()]

        page = self.paginate_queryset(rows)
        serializer = self.get_serializer(page if page is not None else rows, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def link(self, request, pk=None):
        payload = ConfirmacaoLinkSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = ConfirmacaoService.salvar_link_chamada(pk, payload.validated_data["link"])
        return Response(self.get_serializer(row).data)

    @action(detail=True, methods=["post"], url_path="confirmar-ligacao")
    def confirmar_ligacao(self, request, pk=None):
        row = ConfirmacaoService.confirmar_ligacao(pk, request.user)
        return Response(self.get_serializer(row).data)

    @action(detail=True, methods=["post"], url_path="confirmar-averbacao")
    def confirmar_averbacao(self, request, pk=None):
        row = ConfirmacaoService.confirmar_averbacao(pk, request.user)
        return Response(self.get_serializer(row).data)


class AgentePagamentoViewSet(mixins.ListModelMixin, GenericViewSet):
    serializer_class = AgentePagamentoContratoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgenteOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Contrato.objects.none()

        competencia = parse_month_filter(self.request.query_params.get("mes"))
        queryset = (
            Contrato.objects.select_related("associado", "agente")
            .prefetch_related(
                Prefetch(
                    "comprovantes",
                    queryset=Comprovante.objects.filter(
                        refinanciamento__isnull=True
                    ).select_related("enviado_por"),
                ),
                Prefetch(
                    "ciclos",
                    queryset=Ciclo.objects.prefetch_related(
                        Prefetch(
                            "parcelas",
                            queryset=Parcela.objects.prefetch_related(
                                Prefetch(
                                    "itens_retorno",
                                    queryset=ArquivoRetornoItem.objects.select_related(
                                        "arquivo_retorno"
                                    ).order_by("-created_at"),
                                )
                            ).order_by("numero"),
                        )
                    ).order_by("numero"),
                ),
                Prefetch(
                    "associado__pagamentos_mensalidades",
                    queryset=PagamentoMensalidade.objects.order_by("-referencia_month"),
                ),
                Prefetch(
                    "associado__tesouraria_pagamentos",
                    queryset=Pagamento.all_objects.order_by("created_at", "id"),
                ),
            )
            .order_by("-created_at")
            .distinct()
        )

        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(agente=user)

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(codigo__icontains=search)
                | Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
            )

        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter in {choice[0] for choice in Contrato.Status.choices}:
            queryset = queryset.filter(status=status_filter)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["mes_filter"] = parse_month_filter(
            self.request.query_params.get("mes")
        )
        if hasattr(self, "_contract_projection_cache"):
            context["_contract_projection_cache"] = self._contract_projection_cache
        return context

    def _notification_queryset(self):
        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            return PagamentoNotificacao.objects.filter(
                agente=user,
                lida_em__isnull=True,
            )
        return PagamentoNotificacao.objects.none()

    def list(self, request, *args, **kwargs):  # noqa: A003
        queryset = self.filter_queryset(self.get_queryset())
        competencia = parse_month_filter(request.query_params.get("mes"))

        contratos = list(queryset)
        projection_cache = {
            contrato.id: build_contract_cycle_projection(contrato)
            for contrato in contratos
        }
        self._contract_projection_cache = projection_cache

        def parcela_no_recorte(parcela: dict[str, object]) -> bool:
            if competencia is None:
                return True
            referencia_mes = parcela["referencia_mes"]
            return (
                referencia_mes.year == competencia.year
                and referencia_mes.month == competencia.month
            )

        if competencia is not None:
            contratos = [
                contrato
                for contrato in contratos
                if any(
                    parcela_no_recorte(parcela)
                    for ciclo in projection_cache[contrato.id]["cycles"]
                    for parcela in ciclo["parcelas"]
                )
                or (
                    contrato.data_contrato.year == competencia.year
                    and contrato.data_contrato.month == competencia.month
                )
            ]

        resumo = {
            "total": len(contratos),
            "efetivados": sum(
                1 for contrato in contratos if contrato.auxilio_liberado_em is not None
            ),
            "com_anexos": sum(
                1
                for contrato in contratos
                if contrato.comprovantes.filter(refinanciamento__isnull=True).exists()
            ),
            "parcelas_pagas": sum(
                1
                for contrato in contratos
                for ciclo in projection_cache[contrato.id]["cycles"]
                for parcela in ciclo["parcelas"]
                if parcela_no_recorte(parcela)
                and parcela["status"] == Parcela.Status.DESCONTADO
            ),
            "parcelas_total": sum(
                1
                for contrato in contratos
                for ciclo in projection_cache[contrato.id]["cycles"]
                for parcela in ciclo["parcelas"]
                if parcela_no_recorte(parcela)
            ),
        }

        page = self.paginate_queryset(contratos)
        serializer = self.get_serializer(page if page is not None else contratos, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["resumo"] = resumo
            return response
        return Response({"results": serializer.data, "resumo": resumo})

    @action(detail=False, methods=["get"], url_path="notificacoes")
    def notificacoes(self, request):
        return Response({"unread_count": self._notification_queryset().count()})

    @action(detail=False, methods=["post"], url_path="notificacoes/marcar-lidas")
    def marcar_notificacoes_lidas(self, request):
        now = timezone.now()
        marked_count = self._notification_queryset().update(
            lida_em=now,
            updated_at=now,
        )
        return Response({"marked_count": marked_count})


class BaixaManualViewSet(mixins.ListModelMixin, GenericViewSet):
    serializer_class = BaixaManualItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        competencia = parse_month_filter(self.request.query_params.get("competencia"))
        return BaixaManualService.listar_parcelas_pendentes(
            search=self.request.query_params.get("search"),
            status_filter=self.request.query_params.get("status"),
            competencia=competencia,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        kpis = BaixaManualService.kpis()
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="dar-baixa", parser_classes=[MultiPartParser])
    def dar_baixa(self, request, pk=None):
        payload = DarBaixaManualSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        baixa = BaixaManualService.dar_baixa(
            int(pk),
            payload.validated_data["comprovante"],
            payload.validated_data["valor_pago"],
            payload.validated_data.get("observacao", ""),
            request.user,
        )
        return Response(
            {"id": baixa.id, "message": "Baixa manual registrada com sucesso."},
            status=201,
        )


class DespesaViewSet(ModelViewSet):
    queryset = Despesa.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        competencia_param = self.request.query_params.get("competencia")
        competencia = parse_competencia(competencia_param) if competencia_param else None
        return DespesaService.listar_despesas(
            competencia=competencia,
            search=self.request.query_params.get("search"),
            status=self.request.query_params.get("status"),
            status_anexo=self.request.query_params.get("status_anexo"),
            tipo=self.request.query_params.get("tipo"),
        )

    def get_serializer_class(self):
        if self.action in {"create", "partial_update", "update"}:
            return DespesaWriteSerializer
        return DespesaListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):  # noqa: A003
        queryset = self.filter_queryset(self.get_queryset())
        kpis = DespesaService.kpis(queryset)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data, status=201)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="anexar")
    def anexar(self, request, pk=None):
        payload = DespesaAnexarSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        despesa = DespesaService.anexar(self.get_object(), payload.validated_data["anexo"])
        serializer = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(serializer.data)
