from __future__ import annotations

from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import IsTesoureiroOrAdmin
from core.pagination import StandardResultsSetPagination

from .models import ArquivoRetorno, ArquivoRetornoItem
from .financeiro import build_financeiro_payload
from .serializers import (
    ArquivoRetornoDetailSerializer,
    ArquivoRetornoFinanceiroPayloadSerializer,
    ArquivoRetornoItemSerializer,
    ArquivoRetornoListSerializer,
    ArquivoRetornoUploadSerializer,
)
from .services import ArquivoRetornoService


class UploadArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "20/hour"


class ReprocessarArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "30/hour"


def parse_competencia_query(value: str | None):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc


def parse_periodo_query(value: str | None):
    if not value:
        return None
    if value in {"mes", "trimestre"}:
        return value
    raise ValidationError("Período inválido. Use 'mes' ou 'trimestre'.")


class ArquivoRetornoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ArquivoRetorno.objects.none()

        queryset = ArquivoRetorno.objects.select_related("uploaded_by")
        competencia = parse_competencia_query(
            self.request.query_params.get("competencia")
        )
        periodo = parse_periodo_query(self.request.query_params.get("periodo"))

        if periodo and not competencia:
            raise ValidationError("O parâmetro periodo exige competencia.")

        if competencia:
            if periodo == "trimestre":
                quarter_start_month = ((competencia.month - 1) // 3) * 3 + 1
                quarter_end_month = quarter_start_month + 2
                queryset = queryset.filter(
                    competencia__year=competencia.year,
                    competencia__month__gte=quarter_start_month,
                    competencia__month__lte=quarter_end_month,
                )
            else:
                queryset = queryset.filter(
                    competencia__year=competencia.year,
                    competencia__month=competencia.month,
                )

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {
            "descontados",
            "nao_descontados",
            "pendencias_manuais",
            "encerramentos",
            "novos_ciclos",
            "aptos_renovar",
        }:
            return ArquivoRetornoItemSerializer
        if self.action == "upload":
            return ArquivoRetornoUploadSerializer
        if self.action == "retrieve":
            return ArquivoRetornoDetailSerializer
        return ArquivoRetornoListSerializer

    def get_throttles(self):
        if self.action == "upload":
            return [UploadArquivoRetornoRateThrottle()]
        if self.action == "reprocessar":
            return [ReprocessarArquivoRetornoRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="competencia",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Competência base no formato YYYY-MM.",
            ),
            OpenApiParameter(
                name="periodo",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Janela de filtro: mes ou trimestre.",
            ),
        ],
        responses=ArquivoRetornoListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=ArquivoRetornoUploadSerializer,
        responses=ArquivoRetornoDetailSerializer,
    )
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def upload(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        arquivo_retorno = ArquivoRetornoService().upload(
            serializer.validated_data["arquivo"],
            request.user,
        )
        return Response(ArquivoRetornoDetailSerializer(arquivo_retorno).data, status=201)

    @extend_schema(responses=ArquivoRetornoDetailSerializer)
    @action(detail=False, methods=["get"])
    def ultima(self, request):
        arquivo = self.get_queryset().first()
        if not arquivo:
            return Response(status=404)
        return Response(ArquivoRetornoDetailSerializer(arquivo).data)

    @extend_schema(responses=ArquivoRetornoDetailSerializer)
    @action(detail=True, methods=["post"])
    def reprocessar(self, request, pk=None):
        arquivo = ArquivoRetornoService().reprocessar(int(pk))
        return Response(ArquivoRetornoDetailSerializer(arquivo).data)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"])
    def descontados(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="nao-descontados")
    def nao_descontados(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="pendencias-manuais")
    def pendencias_manuais(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"])
    def encerramentos(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_encerramento=True)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="novos-ciclos")
    def novos_ciclos(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_novo_ciclo=True)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="aptos-renovar")
    def aptos_renovar(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_novo_ciclo=True)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoFinanceiroPayloadSerializer)
    @action(detail=True, methods=["get"])
    def financeiro(self, request, pk=None):
        arquivo = self.get_object()
        payload = build_financeiro_payload(competencia=arquivo.competencia)
        return Response(ArquivoRetornoFinanceiroPayloadSerializer(payload).data)

    def _filtrar_itens(self, pk: str, *, resultado: str | None = None, gerou_encerramento: bool | None = None, gerou_novo_ciclo: bool | None = None):
        queryset = ArquivoRetornoItem.objects.filter(arquivo_retorno_id=pk).select_related(
            "associado",
            "associado__agente_responsavel",
            "parcela",
            "parcela__ciclo",
            "parcela__ciclo__contrato",
            "parcela__ciclo__contrato__agente",
        )
        if resultado:
            queryset = queryset.filter(resultado_processamento=resultado)
        if gerou_encerramento is not None:
            queryset = queryset.filter(gerou_encerramento=gerou_encerramento)
        if gerou_novo_ciclo is not None:
            queryset = queryset.filter(gerou_novo_ciclo=gerou_novo_ciclo)
        return queryset.order_by("linha_numero")

    def _paginate_items(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
