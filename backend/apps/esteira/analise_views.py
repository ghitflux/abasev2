from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import IsAnalistaOrAdmin
from core.pagination import StandardResultsSetPagination

from .analise_serializers import (
    AnaliseDadosSerializer,
    AnaliseDadosUpdateSerializer,
    AnaliseMargemSerializer,
    AnalisePagamentoDataSerializer,
    AnalisePagamentoSerializer,
)
from .analise_services import AnaliseService
from .serializers import EsteiraListSerializer


class AnaliseViewSet(GenericViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAnalistaOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == "filas":
            return EsteiraListSerializer
        if self.action == "ajustes":
            return AnalisePagamentoSerializer
        if self.action == "margem":
            return AnaliseMargemSerializer
        if self.action == "dados":
            return AnaliseDadosSerializer
        if self.action == "ajuste_data_pagamento":
            return AnalisePagamentoDataSerializer
        if self.action == "atualizar_nome":
            return AnaliseDadosUpdateSerializer
        return AnaliseDadosSerializer

    def _paginated_response(self, rows, serializer_class, *, meta: dict[str, object] | None = None):
        page = self.paginate_queryset(rows)
        serializer = serializer_class(
            page if page is not None else rows,
            many=True,
            context=self.get_serializer_context(),
        )
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            if meta is not None:
                response.data["meta"] = meta
            return response
        payload = {
            "count": len(serializer.data),
            "next": None,
            "previous": None,
            "results": serializer.data,
        }
        if meta is not None:
            payload["meta"] = meta
        return Response(payload)

    def list(self, request):
        payload = AnaliseService.resumo(
            request.user,
            search=request.query_params.get("search"),
            competencia=request.query_params.get("competencia"),
        )
        return Response(payload)

    @action(detail=False, methods=["get"])
    def filas(self, request):
        secao = request.query_params.get("secao", "ativos").strip().lower()
        queryset = AnaliseService.fila_queryset(
            secao,
            request.user,
            search=request.query_params.get("search"),
        )
        return self._paginated_response(
            queryset,
            EsteiraListSerializer,
            meta={"secao": secao},
        )

    @action(detail=False, methods=["get"])
    def ajustes(self, request):
        competencia = request.query_params.get("competencia")
        queryset = AnaliseService.ajustes_queryset(
            competencia,
            request.query_params.get("search"),
        )
        meta = {
            "competencia": AnaliseService.competencia_meta(competencia),
        }
        return self._paginated_response(queryset, AnalisePagamentoSerializer, meta=meta)

    @action(
        detail=False,
        methods=["patch"],
        url_path=r"ajustes/(?P<pagamento_id>[^/.]+)/data-pagamento",
    )
    def ajuste_data_pagamento(self, request, pagamento_id=None):
        payload = AnalisePagamentoDataSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        pagamento = AnaliseService.atualizar_data_pagamento(
            int(pagamento_id),
            payload.validated_data["new_date"],
        )
        return Response(AnalisePagamentoSerializer(pagamento).data)

    @action(detail=False, methods=["delete"], url_path=r"ajustes/(?P<pagamento_id>[^/.]+)")
    def excluir_ajuste(self, request, pagamento_id=None):
        AnaliseService.excluir_pagamento(int(pagamento_id))
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def margem(self, request):
        competencia = request.query_params.get("competencia")
        queryset = AnaliseService.margem_queryset(
            competencia,
            request.query_params.get("search"),
        )
        meta = {
            "competencia": AnaliseService.competencia_meta(competencia),
            "totais": AnaliseService.margem_totais(queryset),
        }
        return self._paginated_response(queryset, AnaliseMargemSerializer, meta=meta)

    @action(detail=False, methods=["get"])
    def dados(self, request):
        queryset = AnaliseService.dados_queryset(request.query_params.get("search"))
        return self._paginated_response(queryset, AnaliseDadosSerializer)

    @action(
        detail=False,
        methods=["patch"],
        url_path=r"dados/(?P<associado_id>[^/.]+)/nome",
    )
    def atualizar_nome(self, request, associado_id=None):
        payload = AnaliseDadosUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        associado = AnaliseService.atualizar_nome_associado(
            int(associado_id),
            payload.validated_data["nome_completo"],
        )
        return Response(AnaliseDadosSerializer(associado).data)
