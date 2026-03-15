from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import IsAdmin
from apps.associados.models import Associado
from core.pagination import StandardResultsSetPagination

from .dashboard_serializers import (
    DashboardAgentesSerializer,
    DashboardDetailRowSerializer,
    DashboardNovosAssociadosSerializer,
    DashboardResumoGeralSerializer,
    DashboardTesourariaSerializer,
)
from .dashboard_service import AdminDashboardService


class DashboardDetailPagination(StandardResultsSetPagination):
    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get(self.page_size_query_param) == "all":
            self.page_size = max(len(queryset), 1)
        return super().paginate_queryset(queryset, request, view=view)


class AdminDashboardViewSet(GenericViewSet):
    queryset = Associado.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    pagination_class = DashboardDetailPagination

    @staticmethod
    def _filters(request):
        return AdminDashboardService.build_filters(
            competencia=request.query_params.get("competencia"),
            date_start=request.query_params.get("date_start"),
            date_end=request.query_params.get("date_end"),
            agent_id=request.query_params.get("agent_id"),
            status=request.query_params.get("status"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("competencia", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_start", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_end", str, OpenApiParameter.QUERY),
            OpenApiParameter("agent_id", int, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
        ],
        responses=DashboardResumoGeralSerializer,
    )
    @action(detail=False, methods=["get"], url_path="resumo-geral")
    def resumo_geral(self, request):
        payload = AdminDashboardService.resumo_geral(self._filters(request))
        return Response(DashboardResumoGeralSerializer(payload).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("competencia", str, OpenApiParameter.QUERY),
            OpenApiParameter("agent_id", int, OpenApiParameter.QUERY),
        ],
        responses=DashboardTesourariaSerializer,
    )
    @action(detail=False, methods=["get"])
    def tesouraria(self, request):
        payload = AdminDashboardService.tesouraria(self._filters(request))
        return Response(DashboardTesourariaSerializer(payload).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("date_start", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_end", str, OpenApiParameter.QUERY),
            OpenApiParameter("agent_id", int, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
        ],
        responses=DashboardNovosAssociadosSerializer,
    )
    @action(detail=False, methods=["get"], url_path="novos-associados")
    def novos_associados(self, request):
        payload = AdminDashboardService.novos_associados(self._filters(request))
        return Response(DashboardNovosAssociadosSerializer(payload).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("date_start", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_end", str, OpenApiParameter.QUERY),
            OpenApiParameter("agent_id", int, OpenApiParameter.QUERY),
        ],
        responses=DashboardAgentesSerializer,
    )
    @action(detail=False, methods=["get"])
    def agentes(self, request):
        payload = AdminDashboardService.agentes(self._filters(request))
        return Response(DashboardAgentesSerializer(payload).data)

    @extend_schema(
        parameters=[
            OpenApiParameter("section", str, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("metric", str, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("competencia", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_start", str, OpenApiParameter.QUERY),
            OpenApiParameter("date_end", str, OpenApiParameter.QUERY),
            OpenApiParameter("agent_id", int, OpenApiParameter.QUERY),
            OpenApiParameter("status", str, OpenApiParameter.QUERY),
            OpenApiParameter("page", int, OpenApiParameter.QUERY),
            OpenApiParameter("page_size", str, OpenApiParameter.QUERY),
        ],
        responses=DashboardDetailRowSerializer(many=True),
    )
    @action(detail=False, methods=["get"])
    def detalhes(self, request):
        rows = AdminDashboardService.detalhes(
            self._filters(request),
            section=request.query_params.get("section", ""),
            metric=request.query_params.get("metric", ""),
        )
        page = self.paginate_queryset(rows)
        serializer = DashboardDetailRowSerializer(page if page is not None else rows, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)
