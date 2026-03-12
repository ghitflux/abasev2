from __future__ import annotations

from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.utils import extend_schema

from apps.accounts.permissions import IsTesoureiroOrAdmin
from core.pagination import StandardResultsSetPagination

from .models import ArquivoRetorno, ArquivoRetornoItem
from .serializers import (
    ArquivoRetornoDetailSerializer,
    ArquivoRetornoItemSerializer,
    ArquivoRetornoListSerializer,
    ArquivoRetornoUploadSerializer,
)
from .services import ArquivoRetornoService


class UploadArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "20/hour"


class ReprocessarArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "30/hour"


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
        return ArquivoRetorno.objects.select_related("uploaded_by").order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {"descontados", "nao_descontados", "pendencias_manuais", "encerramentos", "novos_ciclos"}:
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

    def _filtrar_itens(self, pk: str, *, resultado: str | None = None, gerou_encerramento: bool | None = None, gerou_novo_ciclo: bool | None = None):
        queryset = ArquivoRetornoItem.objects.filter(arquivo_retorno_id=pk).select_related(
            "associado",
            "parcela",
            "parcela__ciclo",
            "parcela__ciclo__contrato",
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
