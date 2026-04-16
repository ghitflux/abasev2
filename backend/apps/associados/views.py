from __future__ import annotations

from django.db.models import Prefetch
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import (
    IsAdmin,
    IsAgenteOrAdmin,
    IsAgenteOrAnalistaOrCoordenadorOrAdmin,
    IsCoordenadorOrAdmin,
    IsOperacionalOrAdmin,
)
from apps.contratos.canonicalization import (
    get_operational_contracts_for_associado,
    operational_contracts_queryset,
)
from apps.contratos.parcela_detail import build_parcela_detail_payload
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Contrato
from apps.contratos.serializers import (
    AssociadoCiclosPayloadSerializer,
    ParcelaDetailQuerySerializer,
    ParcelaDetailSerializer,
)
from apps.refinanciamento.models import Comprovante
from apps.tesouraria.models import Pagamento
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
    queryset = Associado.objects.none()
    filterset_class = AssociadoFilter
    pagination_class = StandardResultsSetPagination
    search_fields = ["nome_completo", "cpf_cnpj", "matricula", "matricula_orgao"]
    ordering_fields = ["nome_completo", "matricula", "created_at", "status"]
    ordering = ["nome_completo"]

    @staticmethod
    def _operational_contracts_prefetch():
        return Prefetch(
            "contratos",
            queryset=operational_contracts_queryset(
                Contrato.objects.exclude(status=Contrato.Status.CANCELADO)
                .select_related("agente")
                .prefetch_related(
                    "ciclos__parcelas",
                    Prefetch(
                        "comprovantes",
                        queryset=Comprovante.objects.filter(
                            refinanciamento__isnull=True
                        ).select_related("enviado_por"),
                    ),
                )
                .order_by("-created_at", "-id")
            ),
        )

    def get_serializer_class(self):
        if self.action == "list":
            return AssociadoListSerializer
        if self.action == "retrieve":
            return AssociadoDetailSerializer
        if self.action == "create":
            return AssociadoCreateSerializer
        return AssociadoUpdateSerializer

    def _base_queryset(self):
        return Associado.objects.select_related("agente_responsavel", "user").distinct()

    def _list_queryset(self):
        return self._base_queryset().prefetch_related(
            self._operational_contracts_prefetch(),
        )

    def _detail_queryset(self):
        return (
            self._base_queryset()
            .select_related(
                "endereco",
                "dados_bancarios",
                "contato_historico",
                "esteira_item",
                "esteira_item__analista_responsavel",
                "esteira_item__coordenador_responsavel",
                "esteira_item__tesoureiro_responsavel",
            )
            .prefetch_related(
                self._operational_contracts_prefetch(),
                Prefetch("documentos"),
                Prefetch("esteira_item__pendencias"),
                Prefetch("esteira_item__transicoes"),
                Prefetch(
                    "tesouraria_pagamentos",
                    queryset=Pagamento.all_objects.order_by("created_at", "id"),
                ),
            )
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Associado.objects.none()

        if self.action in {"retrieve", "ciclos", "parcela_detalhe"}:
            queryset = self._detail_queryset()
        elif self.action == "list":
            queryset = self._list_queryset()
        else:
            queryset = self._base_queryset()

        if self.action == "list":
            queryset = AssociadoService.buscar_com_contagens(queryset)

        user = self.request.user
        if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
            return Associado.objects.none()
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(agente_responsavel=user)

        return queryset

    def get_permissions(self):
        if self.action in {
            "create",
            "documentos",
            "validar_documento",
            "update",
            "partial_update",
        }:
            if self.action == "create":
                return [
                    permissions.IsAuthenticated(),
                    IsAgenteOrAnalistaOrCoordenadorOrAdmin(),
                ]
            return [permissions.IsAuthenticated(), IsAgenteOrAdmin()]
        if self.action == "list":
            return [permissions.IsAuthenticated(), IsCoordenadorOrAdmin()]
        if self.action == "agentes":
            return [permissions.IsAuthenticated(), IsOperacionalOrAdmin()]
        if self.action in {"retrieve", "ciclos", "parcela_detalhe"}:
            return [permissions.IsAuthenticated(), IsOperacionalOrAdmin()]
        if self.action == "inativar":
            return [permissions.IsAuthenticated(), IsCoordenadorOrAdmin()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdmin()]

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "DELETE",
            detail="Associado não pode ser excluído. Utilize a inativação.",
        )

    @action(detail=True, methods=["post"])
    def inativar(self, request, pk=None):
        associado = AssociadoService.inativar_associado(self.get_object())
        serializer = AssociadoDetailSerializer(
            associado,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def metricas(self, request):
        data = AssociadoService.calcular_metricas(
            self.filter_queryset(self.get_queryset())
        )
        return Response(AssociadoMetricasSerializer(data).data)

    @action(detail=False, methods=["get"], url_path="agentes")
    def agentes(self, request):
        agentes = (
            User.objects.filter(
                is_active=True,
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo="AGENTE",
            )
            .distinct()
            .order_by("first_name", "last_name", "email")
        )
        return Response(
            [{"id": agente.id, "full_name": agente.full_name} for agente in agentes]
        )

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
        contratos = get_operational_contracts_for_associado(associado)
        payload = {"ciclos": [], "meses_nao_pagos": []}
        for contrato in contratos:
            projection = build_contract_cycle_projection(
                contrato,
                include_documents=True,
            )
            payload["ciclos"].extend(projection["cycles"])
            payload["meses_nao_pagos"].extend(projection["unpaid_months"])
        payload["ciclos"].sort(key=lambda item: item["numero"], reverse=True)
        payload["meses_nao_pagos"].sort(
            key=lambda item: item["referencia_mes"], reverse=True
        )
        serializer = AssociadoCiclosPayloadSerializer(payload)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="parcela-detalhe")
    def parcela_detalhe(self, request, pk=None):
        associado = self.get_object()
        query_serializer = ParcelaDetailQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        contrato_id = query_serializer.validated_data["contrato_id"]
        referencia_mes = query_serializer.validated_data["referencia_mes"]
        kind = query_serializer.validated_data["kind"]

        contrato = (
            associado.contratos.exclude(status=Contrato.Status.CANCELADO)
            .filter(id=contrato_id)
            .first()
        )
        if contrato is None:
            return Response(
                {"detail": "Contrato não encontrado para o associado informado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payload = build_parcela_detail_payload(
                contrato=contrato,
                referencia_mes=referencia_mes,
                kind=kind,
                request=request,
            )
        except LookupError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_404_NOT_FOUND,
            )

        user = request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            payload["competencia_evidencias"] = []
            payload["termo_antecipacao"] = None
            payload["documentos_ciclo"] = [
                evidence
                for evidence in payload["documentos_ciclo"]
                if str(evidence.get("papel", "")).lower() == "agente"
            ]

        serializer = ParcelaDetailSerializer(payload)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def documentos(self, request, pk=None):
        associado = self.get_object()
        serializer = DocumentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(associado=associado)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
