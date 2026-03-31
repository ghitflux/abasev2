from __future__ import annotations

from django.http import FileResponse
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import RelatorioGerado
from .serializers import (
    RelatorioExportarSerializer,
    RelatorioGeradoSerializer,
    RelatorioResumoSerializer,
)
from .services import RelatorioService


class RelatorioViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = RelatorioGerado.objects.order_by("-created_at")
    serializer_class = RelatorioGeradoSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    @action(detail=False, methods=["get"])
    def resumo(self, request):
        payload = RelatorioService.resumo()
        serializer = RelatorioResumoSerializer(payload)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def exportar(self, request):
        payload = RelatorioExportarSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        relatorio = RelatorioService.exportar(
            payload.validated_data.get("rota") or payload.validated_data["tipo"],
            payload.validated_data["formato"],
            payload.validated_data.get("filtros") or {},
        )
        serializer = self.get_serializer(relatorio)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        relatorio = self.get_object()
        response = FileResponse(
            relatorio.arquivo.open("rb"),
            as_attachment=True,
            filename=RelatorioService.download_filename(relatorio),
            content_type=RelatorioService.content_type(relatorio.formato),
        )
        return response
