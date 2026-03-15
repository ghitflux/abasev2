from __future__ import annotations

from django.db.models import Prefetch, Q
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import (
    IsAgenteOrAdmin,
    IsCoordenadorOrAdmin,
    IsTesoureiroOrAdmin,
)
from core.pagination import StandardResultsSetPagination

from .models import Refinanciamento
from .serializers import (
    BloquearRefinanciamentoSerializer,
    EfetivarRefinanciamentoSerializer,
    ElegibilidadeRefinanciamentoSerializer,
    RefinanciamentoDetailSerializer,
    RefinanciamentoListSerializer,
)
from .services import RefinanciamentoService


class BaseRefinanciamentoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    queryset = Refinanciamento.objects.none()
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return RefinanciamentoDetailSerializer
        return RefinanciamentoListSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Refinanciamento.objects.none()

        queryset = (
            Refinanciamento.objects.select_related(
                "associado",
                "contrato_origem",
                "contrato_origem__agente",
                "solicitado_por",
                "aprovado_por",
                "bloqueado_por",
                "efetivado_por",
                "ciclo_origem",
                "ciclo_destino",
            )
            .prefetch_related(
                Prefetch("ciclo_destino__parcelas"),
                Prefetch("ciclo_origem__parcelas"),
                Prefetch("comprovantes__enviado_por"),
                Prefetch("itens__pagamento_mensalidade"),
            )
            .order_by("-created_at")
        )

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(contrato_origem__codigo__icontains=search)
            )

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        user = self.request.user
        if user.has_role("ADMIN"):
            return queryset
        if user.has_role("AGENTE"):
            return queryset.filter(contrato_origem__agente=user)
        if user.has_role("COORDENADOR"):
            return queryset
        if user.has_role("TESOUREIRO"):
            return queryset.filter(
                status__in=[
                    Refinanciamento.Status.CONCLUIDO,
                    Refinanciamento.Status.EFETIVADO,
                ]
            )
        return queryset.none()


class RefinanciamentoViewSet(BaseRefinanciamentoViewSet):
    def get_permissions(self):
        if self.action == "solicitar" or self.action == "eligibilidade":
            return [permissions.IsAuthenticated(), IsAgenteOrAdmin()]
        if self.action in ["aprovar", "bloquear", "reverter"]:
            return [permissions.IsAuthenticated(), IsCoordenadorOrAdmin()]
        if self.action == "efetivar":
            return [permissions.IsAuthenticated(), IsTesoureiroOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["get"])
    def elegibilidade(self, request, pk=None):
        payload = RefinanciamentoService.verificar_elegibilidade(int(pk))
        return Response(ElegibilidadeRefinanciamentoSerializer(payload).data)

    @action(detail=True, methods=["post"])
    def solicitar(self, request, pk=None):
        refinanciamento = RefinanciamentoService.solicitar(int(pk), request.user)
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def aprovar(self, request, pk=None):
        refinanciamento = RefinanciamentoService.aprovar(int(pk), request.user)
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def bloquear(self, request, pk=None):
        payload = BloquearRefinanciamentoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        refinanciamento = RefinanciamentoService.bloquear(
            int(pk), payload.validated_data["motivo"], request.user
        )
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reverter(self, request, pk=None):
        refinanciamento = RefinanciamentoService.reverter(int(pk), request.user)
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def efetivar(self, request, pk=None):
        payload = EfetivarRefinanciamentoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        refinanciamento = RefinanciamentoService.efetivar(
            int(pk),
            payload.validated_data["comprovante_associado"],
            payload.validated_data["comprovante_agente"],
            request.user,
        )
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data)


class CoordenadorRefinanciadosViewSet(BaseRefinanciamentoViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            status__in=[
                Refinanciamento.Status.CONCLUIDO,
                Refinanciamento.Status.EFETIVADO,
            ]
        )
        year = self.request.query_params.get("year")
        if year and year.isdigit():
            queryset = queryset.filter(competencia_solicitada__year=int(year))
        return queryset


class CoordenadorRefinanciamentoViewSet(BaseRefinanciamentoViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            status__in=[
                Refinanciamento.Status.PENDENTE_APTO,
                Refinanciamento.Status.BLOQUEADO,
            ]
        )
        year = self.request.query_params.get("year")
        if year and year.isdigit():
            queryset = queryset.filter(competencia_solicitada__year=int(year))
        return queryset


class TesourariaRefinanciamentoViewSet(BaseRefinanciamentoViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]

    def get_queryset(self):
        queryset = super().get_queryset().filter(
            status__in=[
                Refinanciamento.Status.CONCLUIDO,
                Refinanciamento.Status.EFETIVADO,
            ]
        )

        date_start = self.request.query_params.get("data_inicio")
        if date_start:
            queryset = queryset.filter(created_at__date__gte=date_start)

        date_end = self.request.query_params.get("data_fim")
        if date_end:
            queryset = queryset.filter(created_at__date__lte=date_end)

        return queryset

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def efetivar(self, request, pk=None):
        payload = EfetivarRefinanciamentoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        refinanciamento = RefinanciamentoService.efetivar(
            int(pk),
            payload.validated_data["comprovante_associado"],
            payload.validated_data["comprovante_agente"],
            request.user,
        )
        serializer = RefinanciamentoDetailSerializer(
            refinanciamento, context=self.get_serializer_context()
        )
        return Response(serializer.data)
