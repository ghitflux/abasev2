from __future__ import annotations

from django.db.models import Count, Prefetch, Q
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.associados.serializers import AssociadoDetailSerializer
from core.pagination import StandardResultsSetPagination

from .models import EsteiraItem, Pendencia
from .serializers import (
    EsteiraDetailSerializer,
    EsteiraListSerializer,
    PendenciaActionSerializer,
    PendenciaSerializer,
    SolicitarCorrecaoSerializer,
    TransicaoSerializer,
)
from .services import EsteiraService


class EsteiraViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    ordering = ["prioridade", "created_at"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return EsteiraDetailSerializer
        return EsteiraListSerializer

    def _base_queryset(self):
        return EsteiraItem.objects.select_related(
            "associado",
            "associado__agente_responsavel",
            "associado__contato_historico",
            "analista_responsavel",
            "coordenador_responsavel",
            "tesoureiro_responsavel",
        )

    def _list_queryset(self):
        return (
            self._base_queryset()
            .prefetch_related(
                Prefetch("associado__documentos"),
                Prefetch("associado__doc_issues"),
                Prefetch("associado__contratos"),
                Prefetch("pendencias"),
            )
            .order_by("prioridade", "created_at")
        )

    def _detail_queryset(self):
        return (
            self._base_queryset()
            .prefetch_related(
                Prefetch("associado__documentos"),
                Prefetch("associado__doc_issues"),
                Prefetch("associado__contratos__ciclos__parcelas"),
                Prefetch("pendencias"),
                Prefetch("transicoes__realizado_por"),
            )
            .order_by("prioridade", "created_at")
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return EsteiraItem.objects.none()

        queryset = self._detail_queryset() if self.action == "retrieve" else self._list_queryset()

        user = self.request.user
        if user.has_role("ANALISTA") and not user.has_role("ADMIN"):
            if self.action in {"retrieve", "destroy"}:
                queryset = queryset.filter(
                    Q(analista_responsavel=user) | Q(analista_responsavel__isnull=True)
                )
            else:
                queryset = queryset.filter(etapa_atual=EsteiraItem.Etapa.ANALISE)
        elif user.has_role("COORDENADOR") and not user.has_role("ADMIN"):
            if self.action not in {"retrieve", "destroy"}:
                queryset = queryset.filter(etapa_atual=EsteiraItem.Etapa.COORDENACAO)
        elif user.has_role("TESOUREIRO") and not user.has_role("ADMIN"):
            queryset = queryset.filter(etapa_atual=EsteiraItem.Etapa.TESOURARIA)
        elif user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(associado__agente_responsavel=user)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
                | Q(associado__contratos__codigo__icontains=search)
            ).distinct()

        status_filtro = self.request.query_params.get("status")
        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        return queryset

    def _get_pendencias_queryset(self):
        queryset = Pendencia.objects.select_related(
            "esteira_item__associado",
            "esteira_item__associado__agente_responsavel",
        ).filter(status=Pendencia.Status.ABERTA)

        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(esteira_item__associado__agente_responsavel=user)

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(esteira_item__associado__nome_completo__icontains=search)
                | Q(esteira_item__associado__cpf_cnpj__icontains=search)
                | Q(esteira_item__associado__matricula__icontains=search)
                | Q(esteira_item__associado__contratos__codigo__icontains=search)
            ).distinct()

        return queryset

    def destroy(self, request, *args, **kwargs):
        user = request.user
        if not (
            user.has_role("ADMIN")
            or user.has_role("COORDENADOR")
            or user.has_role("ANALISTA")
        ):
            raise PermissionDenied(
                "Somente admin, coordenador ou analista podem excluir solicitações da esteira."
            )

        esteira_item = self.get_object()
        EsteiraService.excluir_solicitacao(esteira_item)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def assumir(self, request, pk=None):
        esteira_item = EsteiraService.assumir(self.get_object(), request.user)
        return Response(EsteiraDetailSerializer(esteira_item, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def aprovar(self, request, pk=None):
        esteira_item = EsteiraService.aprovar(
            self.get_object(),
            request.user,
            request.data.get("observacao", ""),
        )
        return Response(EsteiraDetailSerializer(esteira_item, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def pendenciar(self, request, pk=None):
        payload = PendenciaActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        esteira_item = EsteiraService.pendenciar(
            self.get_object(),
            request.user,
            payload.validated_data["tipo"],
            payload.validated_data["descricao"],
        )
        return Response(EsteiraDetailSerializer(esteira_item, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="validar-documento")
    def validar_documento(self, request, pk=None):
        esteira_item = EsteiraService.validar_documento_revisto(
            self.get_object(),
            request.user,
        )
        return Response(EsteiraDetailSerializer(esteira_item, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"], url_path="solicitar-correcao")
    def solicitar_correcao(self, request, pk=None):
        payload = SolicitarCorrecaoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        esteira_item = EsteiraService.solicitar_correcao(
            self.get_object(),
            request.user,
            payload.validated_data["observacao"],
        )
        return Response(EsteiraDetailSerializer(esteira_item, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def reprovar(self, request, pk=None):
        EsteiraService.reprovar(
            self.get_object(),
            request.user,
            request.data.get("observacao", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="correcao")
    def correcao(self, request, pk=None):
        esteira_item = self.get_object()
        user = request.user

        if not (user.has_role("AGENTE") or user.has_role("ADMIN")):
            raise PermissionDenied("Somente agente responsável ou admin podem revisar esta correção.")

        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            has_open_returned_pending = esteira_item.pendencias.filter(
                status=Pendencia.Status.ABERTA,
                retornado_para_agente=True,
            ).exists()
            if not has_open_returned_pending:
                raise ValidationError(
                    "Este item não possui pendência aberta retornada ao agente para correção."
                )

        serializer = AssociadoDetailSerializer(
            esteira_item.associado,
            context={
                **self.get_serializer_context(),
                "agent_correction_mode": True,
            },
        )
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def transicoes(self, request, pk=None):
        serializer = TransicaoSerializer(self.get_object().transicoes.all(), many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def pendencias(self, request):
        queryset = self._get_pendencias_queryset()
        page = self.paginate_queryset(queryset.order_by("-created_at"))
        if page is not None:
            serializer = PendenciaSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = PendenciaSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="pendencias-resumo")
    def pendencias_resumo(self, request):
        queryset = self._get_pendencias_queryset()
        resumo = queryset.aggregate(
            total=Count("id"),
            retornadas_agente=Count("id", filter=Q(retornado_para_agente=True)),
            internas=Count("id", filter=Q(retornado_para_agente=False)),
            associados_impactados=Count("esteira_item__associado_id", distinct=True),
        )
        return Response(resumo, status=status.HTTP_200_OK)
