"""
Views mobile self-service — /api/v1/app/

Os endpoints v1 preservam os contratos funcionais usados pelo app mobile novo,
mas executam tudo pelo namespace unificado da API principal.
"""
from __future__ import annotations

import json

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView


class AppStatusView(APIView):
    """
    GET /api/v1/app/status/
    Endpoint público (sem autenticação) que retorna se o app está em manutenção.
    Controlado pela variável de ambiente APP_MAINTENANCE_MODE=true no servidor.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        maintenance = getattr(settings, "APP_MAINTENANCE_MODE", False)
        message = getattr(
            settings,
            "APP_MAINTENANCE_MESSAGE",
            "O aplicativo está temporariamente indisponível para manutenção. Tente novamente em breve.",
        )
        return Response({"maintenance": maintenance, "message": message})

from apps.accounts.permissions import IsAssociadoOrAdmin
from apps.accounts.serializers import get_user_role_codes
from apps.accounts.mobile_maintenance import MobileMaintenanceMixin
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.models import Contrato
from apps.esteira.models import DocIssue, DocReupload

from .mobile_legacy import (
    build_antecipacao_payload,
    build_auxilio2_payload,
    build_bootstrap_payload,
    build_issues_payload,
    build_mensalidades_payload,
    build_status_payload,
    create_auxilio2_charge,
    resolve_mobile_associado,
)
from .mobile_legacy_views import (
    DOCUMENT_UPLOAD_FIELDS,
    _merged_payload,
    _resolve_or_create_associado,
    _upsert_documento,
)
from .models import Associado
from .serializers import DocumentoCreateSerializer


class _AppDocumentoUploadResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.CharField()
    status = serializers.CharField()
    observacao = serializers.CharField()


def _build_app_me_payload(request) -> dict[str, object]:
    associado = resolve_mobile_associado(request.user)
    bootstrap = build_bootstrap_payload(associado, request=request)
    status_payload = build_status_payload(associado, request=request)
    issues_payload = build_issues_payload(associado)

    return {
        "ok": True,
        "user": {
            "id": request.user.id,
            "name": request.user.full_name or request.user.email,
            "email": request.user.email,
        },
        "roles": get_user_role_codes(request.user),
        **bootstrap,
        "issues": issues_payload.get("issues", []),
        "pendencias": issues_payload.get("issues", []),
        "exists": status_payload.get("exists", False),
        "status": status_payload.get("status"),
        "basic_complete": status_payload.get("basic_complete", False),
        "complete": status_payload.get("complete", False),
        "permissions": status_payload.get("permissions", {}),
        "auxilios": status_payload.get("auxilios", {}),
        "termos": status_payload.get("termos", {}),
    }


class AppMeView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(_build_app_me_payload(request), status=status.HTTP_200_OK)


class AppMensalidadesView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_mensalidades_payload(
                associado,
                ref_from=request.query_params.get("ref_from"),
                ref_to=request.query_params.get("ref_to"),
            ),
            status=status.HTTP_200_OK,
        )


class AppAntecipacaoView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_antecipacao_payload(associado),
            status=status.HTTP_200_OK,
        )


class AppPendenciasView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(build_issues_payload(associado), status=status.HTTP_200_OK)


class AppDocumentosView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=DocumentoCreateSerializer,
        responses={201: _AppDocumentoUploadResponseSerializer},
    )
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de enviar documentos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DocumentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(associado=associado)
        return Response(
            {
                "id": doc.id,
                "tipo": doc.tipo,
                "status": doc.status,
                "observacao": doc.observacao,
            },
            status=status.HTTP_201_CREATED,
        )


class AppCadastroView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_status_payload(associado, request=request),
            status=status.HTTP_200_OK,
        )

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        payload = _merged_payload(request.data)
        associado = _resolve_or_create_associado(request.user, payload)

        for field_name, document_type in DOCUMENT_UPLOAD_FIELDS.items():
            upload = request.FILES.get(field_name)
            if upload is None:
                continue
            _upsert_documento(
                associado=associado,
                tipo=document_type,
                upload=upload,
                observacao="Documento enviado no fluxo mobile.",
            )

        return Response(
            {
                "ok": True,
                "message": "Cadastro atualizado com sucesso.",
                "cadastro": build_status_payload(associado, request=request).get("cadastro"),
            },
            status=status.HTTP_200_OK,
        )


class AppCadastroCheckCpfView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        cpf = "".join(ch for ch in (request.query_params.get("cpf") or "") if ch.isdigit())
        if not cpf:
            return Response({"exists": False}, status=status.HTTP_200_OK)

        associado = resolve_mobile_associado(request.user)
        duplicate = Associado.all_objects.filter(cpf_cnpj=cpf).exclude(
            pk=associado.pk if associado else None
        ).first()
        return Response(
            {
                "exists": duplicate is not None,
                "data": None
                if duplicate is None
                else {
                    "full_name": duplicate.nome_completo,
                },
            },
            status=status.HTTP_200_OK,
        )


class AppPendenciasReuploadsView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=OpenApiTypes.OBJECT, responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de reenviar documentos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        issue_id = request.data.get("associadodois_doc_issue_id") or request.data.get("issue_id")
        issue = None
        if issue_id:
            issue = DocIssue.objects.filter(pk=issue_id, associado=associado).first()
            if issue is None:
                return Response(
                    {"ok": False, "message": "Pendência documental não encontrada."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        saved_count = 0
        notes = str(request.data.get("notes") or request.data.get("observacao") or "")
        extras_raw = request.data.get("extras")
        try:
            extras = json.loads(extras_raw) if extras_raw else None
        except json.JSONDecodeError:
            extras = None

        uploads_snapshot = list(issue.agent_uploads_json or []) if issue else []

        for field_name, document_type in DOCUMENT_UPLOAD_FIELDS.items():
            upload = request.FILES.get(field_name)
            if upload is None:
                continue

            documento = _upsert_documento(
                associado=associado,
                tipo=document_type,
                upload=upload,
                observacao=notes or "Reenvio de documento pelo aplicativo.",
            )
            saved_count += 1

            if issue is not None:
                uploaded_at = timezone.now()
                DocReupload.objects.create(
                    doc_issue=issue,
                    associado=associado,
                    uploaded_by=request.user,
                    cpf_cnpj=associado.cpf_cnpj,
                    contrato_codigo=associado.contrato_codigo_contrato or "",
                    file_original_name=upload.name,
                    file_stored_name=documento.arquivo.name.split("/")[-1],
                    file_relative_path=documento.arquivo.name,
                    file_mime=getattr(upload, "content_type", "") or "",
                    file_size_bytes=getattr(upload, "size", None),
                    status=DocReupload.Status.RECEBIDO,
                    uploaded_at=uploaded_at,
                    notes=notes,
                    extras=extras,
                )
                uploads_snapshot.append(
                    {
                        "field": field_name,
                        "file_relative_path": documento.arquivo.name,
                        "uploaded_at": uploaded_at.isoformat(),
                        "notes": notes,
                    }
                )

        if saved_count == 0:
            return Response(
                {"ok": False, "message": "Nenhum arquivo foi enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if issue is not None:
            issue.agent_uploads_json = uploads_snapshot
            issue.save(update_fields=["agent_uploads_json", "updated_at"])

        return Response(
            {
                "ok": True,
                "message": "Arquivos recebidos com sucesso.",
                "saved_count": saved_count,
            },
            status=status.HTTP_200_OK,
        )


class AppTermosAceiteView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="AppTermosAceiteResponse",
                fields={
                    "ok": serializers.BooleanField(),
                    "aceite_termos": serializers.BooleanField(),
                },
            )
        }
    )
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de aceitar os termos."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        associado.aceite_termos = True
        associado.save(update_fields=["aceite_termos", "updated_at"])
        contrato = resolve_operational_contract_for_associado(associado)
        if contrato is not None:
            contrato.termos_web = True
            contrato.save(update_fields=["termos_web", "updated_at"])

        return Response({"ok": True, "aceite_termos": True}, status=status.HTTP_200_OK)


class AppContatoView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(
        responses={
            200: inline_serializer(
                name="AppContatoResponse",
                fields={
                    "ok": serializers.BooleanField(),
                    "contato_status": serializers.CharField(),
                },
            )
        }
    )
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        if associado is None:
            return Response(
                {"ok": False, "message": "Cadastre seus dados antes de solicitar contato."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        associado.contato_status = "solicitado"
        associado.contato_updated_at = timezone.now()
        associado.save(update_fields=["contato_status", "contato_updated_at", "updated_at"])
        contrato = resolve_operational_contract_for_associado(associado)
        if contrato is not None:
            contrato.contato_web = True
            contrato.save(update_fields=["contato_web", "updated_at"])

        return Response(
            {"ok": True, "contato_status": associado.contato_status},
            status=status.HTTP_200_OK,
        )


class AppAuxilio2StatusView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_auxilio2_payload(request.user, associado=associado),
            status=status.HTTP_200_OK,
        )


class AppAuxilio2ResumoView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_auxilio2_payload(request.user, associado=associado),
            status=status.HTTP_200_OK,
        )


class AppAuxilio2ChargeView(MobileMaintenanceMixin, APIView):
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request):
        associado = resolve_mobile_associado(request.user)
        charge = create_auxilio2_charge(request.user, associado=associado)
        payload = build_auxilio2_payload(request.user, associado=associado)
        return Response(
            {
                "ok": True,
                **payload,
                "filiacaoId": charge.id,
            },
            status=status.HTTP_200_OK,
        )
