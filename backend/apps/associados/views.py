from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.permissions import IsAdmin, IsAgenteOrAdmin
from apps.contratos.models import Ciclo
from apps.contratos.serializers import CicloDetailSerializer
from core.pagination import StandardResultsSetPagination

from .filters import AssociadoFilter
from .models import Associado, only_digits
from .serializers import (
    AssociadoCreateSerializer,
    AssociadoDetailSerializer,
    AssociadoListSerializer,
    AssociadoMetricasSerializer,
    AssociadoUpdateSerializer,
    DocumentoCreateSerializer,
)
from .services import AssociadoService
from .strategies import build_duplicate_document_message


class AssociadoViewSet(ModelViewSet):
    filterset_class = AssociadoFilter
    pagination_class = StandardResultsSetPagination
    search_fields = ["nome_completo", "cpf_cnpj", "matricula"]
    ordering_fields = ["nome_completo", "matricula", "created_at", "status"]
    ordering = ["nome_completo"]

    def get_serializer_class(self):
        if self.action == "list":
            return AssociadoListSerializer
        if self.action == "retrieve":
            return AssociadoDetailSerializer
        if self.action == "create":
            return AssociadoCreateSerializer
        return AssociadoUpdateSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Associado.objects.none()

        queryset = (
            Associado.objects.select_related(
                "agente_responsavel",
                "endereco",
                "dados_bancarios",
                "contato_historico",
                "esteira_item",
                "esteira_item__analista_responsavel",
                "esteira_item__coordenador_responsavel",
                "esteira_item__tesoureiro_responsavel",
            )
            .prefetch_related(
                Prefetch("contratos__ciclos__parcelas"),
                Prefetch("documentos"),
                Prefetch("esteira_item__pendencias"),
                Prefetch("esteira_item__transicoes"),
            )
            .distinct()
        )
        if self.action == "list":
            queryset = AssociadoService.buscar_com_contagens(queryset)

        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(agente_responsavel=user)

        return queryset

    def get_permissions(self):
        if self.action in {
            "create",
            "documentos",
            "validar_documento",
            "retrieve",
            "ciclos",
            "update",
            "partial_update",
        }:
            return [permissions.IsAuthenticated(), IsAgenteOrAdmin()]
        return [permissions.IsAuthenticated(), IsAdmin()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def metricas(self, request):
        data = AssociadoService.calcular_metricas()
        return Response(AssociadoMetricasSerializer(data).data)

    @action(detail=False, methods=["get"], url_path="validar-documento")
    def validar_documento(self, request):
        documento = only_digits(request.query_params.get("cpf_cnpj"))
        if not documento:
            return Response(
                {"detail": "CPF/CNPJ é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        associado = (
            Associado.all_objects.select_related("agente_responsavel")
            .filter(cpf_cnpj=documento)
            .first()
        )
        agente_nome = (
            associado.agente_responsavel.full_name
            if associado and associado.agente_responsavel
            else None
        )

        return Response(
            {
                "exists": bool(associado),
                "associado_id": associado.id if associado else None,
                "agente_nome": agente_nome,
                "message": (
                    build_duplicate_document_message(associado)
                    if associado
                    else None
                ),
            }
        )

    @action(detail=True, methods=["get"])
    def ciclos(self, request, pk=None):
        associado = self.get_object()
        ciclos = (
            Ciclo.objects.filter(contrato__associado=associado)
            .prefetch_related("parcelas")
            .order_by("-numero")
        )
        serializer = CicloDetailSerializer(ciclos, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def documentos(self, request, pk=None):
        associado = self.get_object()
        serializer = DocumentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(associado=associado)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
