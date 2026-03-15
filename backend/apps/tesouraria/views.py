from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Prefetch, Q
from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import (
    IsAgenteOrTesoureiroOrAdmin,
    IsCoordenadorOrTesoureiroOrAdmin,
    IsTesoureiroOrAdmin,
)
from apps.associados.serializers import DadosBancariosSerializer
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.tesouraria.models import Confirmacao
from core.pagination import StandardResultsSetPagination

from .serializers import (
    AgentePagamentoContratoSerializer,
    BaixaManualItemSerializer,
    ConfirmacaoLinkSerializer,
    ConfirmacaoListSerializer,
    CongelarContratoSerializer,
    DarBaixaManualSerializer,
    EfetivarContratoSerializer,
    TesourariaContratoListSerializer,
)
from .services import BaixaManualService, ConfirmacaoService, TesourariaService, parse_competencia


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
                    queryset=PagamentoMensalidade.objects.exclude(
                        manual_comprovante_path=""
                    ).order_by("-referencia_month"),
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

        if competencia:
            queryset = queryset.filter(
                Q(
                    ciclos__parcelas__referencia_mes__year=competencia.year,
                    ciclos__parcelas__referencia_mes__month=competencia.month,
                )
                | Q(data_contrato__year=competencia.year, data_contrato__month=competencia.month)
            )

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["mes_filter"] = parse_month_filter(
            self.request.query_params.get("mes")
        )
        return context

    def list(self, request, *args, **kwargs):  # noqa: A003
        queryset = self.filter_queryset(self.get_queryset())
        competencia = parse_month_filter(request.query_params.get("mes"))

        parcelas_filter = Q()
        if competencia:
            parcelas_filter &= Q(
                ciclos__parcelas__referencia_mes__year=competencia.year,
                ciclos__parcelas__referencia_mes__month=competencia.month,
            )

        resumo = queryset.aggregate(
            total=Count("id", distinct=True),
            efetivados=Count(
                "id", filter=Q(auxilio_liberado_em__isnull=False), distinct=True
            ),
            com_anexos=Count(
                "id",
                filter=Q(comprovantes__id__isnull=False, comprovantes__refinanciamento__isnull=True),
                distinct=True,
            ),
            parcelas_pagas=Count(
                "ciclos__parcelas",
                filter=parcelas_filter & Q(ciclos__parcelas__status=Parcela.Status.DESCONTADO),
                distinct=True,
            ),
            parcelas_total=Count(
                "ciclos__parcelas",
                filter=parcelas_filter,
                distinct=True,
            ),
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["resumo"] = resumo
            return response
        return Response({"results": serializer.data, "resumo": resumo})


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
