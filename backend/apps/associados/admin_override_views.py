from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import IsCoordenadorOrAdmin
from apps.contratos.models import Ciclo, Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento

from .admin_override_serializers import (
    AdminOverrideSaveAllWriteSerializer,
    AdminOverrideEditorPayloadSerializer,
    AdminOverrideEventReadSerializer,
    AdminOverrideReverterWriteSerializer,
    AssociadoCoreOverrideWriteSerializer,
    ComprovanteCreateWriteSerializer,
    ComprovanteVersionWriteSerializer,
    ContratoCoreOverrideWriteSerializer,
    CycleLayoutOverrideWriteSerializer,
    DocumentoVersionWriteSerializer,
    EsteiraOverrideWriteSerializer,
    RenewalStageTransitionWriteSerializer,
    RefinanciamentoOverrideWriteSerializer,
)
from .serializers import DocumentoSerializer
from .admin_override_service import AdminOverrideConflict, AdminOverrideService
from .models import AdminOverrideEvent, Associado, Documento


def _conflict_response(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


def _validation_error_response(exc: DjangoValidationError) -> Response:
    if hasattr(exc, "message_dict") and exc.message_dict:
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    if getattr(exc, "messages", None):
        messages = [str(message) for message in exc.messages if str(message).strip()]
        if len(messages) == 1:
            return Response({"detail": messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        if messages:
            return Response(
                {"non_field_errors": messages},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminOverrideAssociadoViewSet(GenericViewSet):
    queryset = Associado.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        return Associado.objects.prefetch_related(
            "contratos__ciclos__parcelas",
            "documentos",
            "admin_override_events__changes",
        ).select_related("esteira_item", "agente_responsavel")

    @extend_schema(
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_associado_editor",
    )
    @action(detail=True, methods=["get"], url_path="editor")
    def editor(self, request, pk=None):
        associado = self.get_object()
        payload = AdminOverrideService.build_associado_editor_payload(associado)
        serializer = AdminOverrideEditorPayloadSerializer(payload, context=self.get_serializer_context())
        return Response(serializer.data)

    @extend_schema(
        responses=AdminOverrideEventReadSerializer(many=True),
        operation_id="admin_override_associado_history",
    )
    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        associado = self.get_object()
        payload = AdminOverrideService.build_associado_history_payload(
            associado,
            request=request,
        )
        serializer = AdminOverrideEventReadSerializer(
            payload,
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @extend_schema(
        request=AssociadoCoreOverrideWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_associado_core",
    )
    @action(detail=True, methods=["post"], url_path="core")
    def core(self, request, pk=None):
        associado = self.get_object()
        serializer = AssociadoCoreOverrideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AdminOverrideService.apply_associado_core_override(
                associado=associado,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)

    @extend_schema(
        request=EsteiraOverrideWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_associado_esteira",
    )
    @action(detail=True, methods=["post"], url_path="esteira/status")
    def esteira_status(self, request, pk=None):
        associado = self.get_object()
        serializer = EsteiraOverrideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AdminOverrideService.apply_esteira_override(
                associado=associado,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)

    @extend_schema(
        request=AdminOverrideSaveAllWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_associado_save_all",
    )
    @action(detail=True, methods=["post"], url_path="save-all")
    def save_all(self, request, pk=None):
        associado = self.get_object()
        serializer = AdminOverrideSaveAllWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = AdminOverrideService.apply_save_all(
                associado=associado,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)

    @extend_schema(
        request=RenewalStageTransitionWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_associado_renewal_transition",
    )
    @action(detail=True, methods=["post"], url_path="renewal-stage")
    def renewal_stage(self, request, pk=None):
        associado = self.get_object()
        serializer = RenewalStageTransitionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = AdminOverrideService.apply_safe_renewal_stage_transition(
                associado=associado,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)


class AdminOverrideContratoViewSet(GenericViewSet):
    queryset = Contrato.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        return Contrato.objects.select_related("associado", "agente").prefetch_related(
            "ciclos__parcelas",
            "comprovantes",
        )

    @extend_schema(
        request=ContratoCoreOverrideWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_contrato_core",
    )
    @action(detail=True, methods=["post"], url_path="core")
    def core(self, request, pk=None):
        contrato = self.get_object()
        serializer = ContratoCoreOverrideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AdminOverrideService.apply_contract_core_override(
                contrato=contrato,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(contrato.associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)

    @extend_schema(
        request=CycleLayoutOverrideWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_contrato_cycles_layout",
    )
    @action(detail=True, methods=["post"], url_path="cycles/layout")
    def cycles_layout(self, request, pk=None):
        contrato = self.get_object()
        serializer = CycleLayoutOverrideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AdminOverrideService.apply_cycle_layout_override(
                contrato=contrato,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(contrato.associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)


class AdminOverrideRefinanciamentoViewSet(GenericViewSet):
    queryset = Refinanciamento.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        return Refinanciamento.objects.select_related("associado", "contrato_origem")

    @extend_schema(
        request=RefinanciamentoOverrideWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_refinanciamento_core",
    )
    @action(detail=True, methods=["post"], url_path="core")
    def core(self, request, pk=None):
        refinanciamento = self.get_object()
        serializer = RefinanciamentoOverrideWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            AdminOverrideService.apply_refinanciamento_override(
                refinanciamento=refinanciamento,
                payload=serializer.validated_data,
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(refinanciamento.associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)


class AdminOverrideDocumentoViewSet(GenericViewSet):
    queryset = Documento.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Documento.all_objects.select_related("associado")

    @extend_schema(
        request=DocumentoVersionWriteSerializer,
        responses=DocumentoSerializer,
        operation_id="admin_override_documento_versionar",
    )
    @action(detail=True, methods=["post"], url_path="versionar")
    def versionar(self, request, pk=None):
        documento = self.get_object()
        serializer = DocumentoVersionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            novo = AdminOverrideService.versionar_documento(
                documento=documento,
                payload=serializer.validated_data,
                user=request.user,
                request=request,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        return Response(DocumentoSerializer(novo, context=self.get_serializer_context()).data)


class AdminOverrideComprovanteViewSet(GenericViewSet):
    queryset = Comprovante.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return Comprovante.all_objects.select_related(
            "contrato__associado",
            "refinanciamento__associado",
            "refinanciamento__contrato_origem",
        )

    @extend_schema(
        request=ComprovanteCreateWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_comprovante_create",
    )
    def create(self, request, *args, **kwargs):
        serializer = ComprovanteCreateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        arquivos = request.FILES.getlist("arquivos")
        if not arquivos:
            return Response(
                {"arquivos": ["Envie ao menos um comprovante."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ciclo = get_object_or_404(
            Ciclo.objects.select_related("contrato__associado", "contrato__agente"),
            pk=serializer.validated_data["ciclo_id"],
        )
        try:
            AdminOverrideService.criar_comprovantes_ciclo(
                ciclo=ciclo,
                payload={**serializer.validated_data, "arquivos": arquivos},
                user=request.user,
                request=request,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(ciclo.contrato.associado)
        return Response(AdminOverrideEditorPayloadSerializer(payload).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        request=ComprovanteVersionWriteSerializer,
        responses=AdminOverrideEditorPayloadSerializer,
        operation_id="admin_override_comprovante_versionar",
    )
    @action(detail=True, methods=["post"], url_path="versionar")
    def versionar(self, request, pk=None):
        comprovante = self.get_object()
        serializer = ComprovanteVersionWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            novo = AdminOverrideService.versionar_comprovante(
                comprovante=comprovante,
                payload=serializer.validated_data,
                user=request.user,
                request=request,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_editor_payload(
            novo.contrato.associado if novo.contrato_id else novo.refinanciamento.associado,
        )
        return Response(AdminOverrideEditorPayloadSerializer(payload).data)


class AdminOverrideEventViewSet(GenericViewSet):
    queryset = AdminOverrideEvent.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]

    def get_queryset(self):
        return AdminOverrideEvent.objects.select_related(
            "associado",
            "contrato",
            "refinanciamento",
            "documento",
            "comprovante",
        )

    @extend_schema(
        request=AdminOverrideReverterWriteSerializer,
        responses=AdminOverrideEventReadSerializer,
        operation_id="admin_override_event_reverter",
    )
    @action(detail=True, methods=["post"], url_path="reverter")
    def reverter(self, request, pk=None):
        event = self.get_object()
        serializer = AdminOverrideReverterWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reverted = AdminOverrideService.revert_event(
                event=event,
                motivo=serializer.validated_data["motivo_reversao"],
                user=request.user,
            )
        except AdminOverrideConflict as exc:
            return _conflict_response(exc)
        except DjangoValidationError as exc:
            return _validation_error_response(exc)
        payload = AdminOverrideService.build_associado_history_payload(
            reverted.associado,
            request=request,
        )
        target = next((item for item in payload if item["id"] == reverted.id), None)
        if target is None:
            target = get_object_or_404(AdminOverrideEvent, pk=reverted.id)
            serialized = AdminOverrideEventReadSerializer(target, context=self.get_serializer_context())
            return Response(serialized.data)
        return Response(
            AdminOverrideEventReadSerializer(target, context=self.get_serializer_context()).data
        )
