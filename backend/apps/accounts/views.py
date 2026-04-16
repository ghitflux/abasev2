import logging

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.pagination import StandardResultsSetPagination

from .mobile_legacy_auth import build_password_reset_request, consume_password_reset_token
from .models import PasswordResetRequest, Role, User
from .permissions import IsCoordenadorOrAdmin
from .services import AgentPortfolioRedistributionService, ComissaoService
from .serializers import (
    AgentManualPasswordResetSerializer,
    AgentRedistributionPreviewSerializer,
    AdminUserCreateSerializer,
    AdminUserAccessUpdateSerializer,
    AdminUserListSerializer,
    AdminUsersMetaSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetResultSerializer,
    PublicPasswordResetResponseSerializer,
    ConfiguracaoComissaoAgenteResetSerializer,
    ConfiguracaoComissaoAgentesWriteSerializer,
    ConfiguracaoComissaoGlobalWriteSerializer,
    ConfiguracaoComissaoPayloadSerializer,
    RefreshSerializer,
    SelfServiceForgotPasswordSerializer,
    SelfServiceRegisterSerializer,
    SelfServiceResetPasswordSerializer,
    UserSerializer,
    get_manageable_role_codes,
    is_manageable_user_for_manager,
)

logger = logging.getLogger(__name__)


class LoginRateThrottle(AnonRateThrottle):
    rate = "10/min"


class AgentManualPasswordResetRateThrottle(AnonRateThrottle):
    rate = "3/hour"


def _maintenance_response():
    """Retorna 503 com mensagem de manutenção se APP_MAINTENANCE_MODE estiver ativo."""
    if getattr(settings, "APP_MAINTENANCE_MODE", False):
        message = getattr(
            settings,
            "APP_MAINTENANCE_MESSAGE",
            "O aplicativo está temporariamente indisponível para manutenção. Tente novamente em breve.",
        )
        return Response({"detail": message}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return None


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(request=LoginSerializer, responses={200: LoginSerializer})
    def post(self, request):
        if (resp := _maintenance_response()) is not None:
            return resp
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RefreshSerializer, responses={200: RefreshSerializer})
    def post(self, request):
        if (resp := _maintenance_response()) is not None:
            return resp
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    @extend_schema(request=LogoutSerializer, responses={205: None})
    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh and "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS:
            token = RefreshToken(refresh)
            token.blacklist()
        return Response(status=status.HTTP_205_RESET_CONTENT)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=SelfServiceRegisterSerializer, responses={201: SelfServiceRegisterSerializer})
    def post(self, request):
        serializer = SelfServiceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_201_CREATED)


class ForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=SelfServiceForgotPasswordSerializer,
        responses={200: PasswordResetResultSerializer},
    )
    def post(self, request):
        serializer = SelfServiceForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = User.all_objects.filter(
            email__iexact=serializer.validated_data["email"].strip().lower(),
            deleted_at__isnull=True,
        ).first()
        if user is not None and user.is_active:
            build_password_reset_request(user=user, request=request)

        return Response(
            {
                "ok": True,
                "message": "Se o e-mail existir, um código de redefinição foi enviado.",
            },
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=SelfServiceResetPasswordSerializer,
        responses={200: PasswordResetResultSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = SelfServiceResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            email = (serializer.validated_data.get("email") or "").strip().lower()
            if email:
                reset_request = consume_password_reset_token(
                    email=email,
                    token=serializer.validated_data["token"],
                )
            else:
                reset_request = (
                    PasswordResetRequest.objects.select_related("user")
                    .filter(
                        token=serializer.validated_data["token"],
                        used_at__isnull=True,
                        deleted_at__isnull=True,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if reset_request is None or not reset_request.is_active:
                    raise AuthenticationFailed("Token de redefinição inválido ou expirado.")
                reset_request.used_at = timezone.now()
                reset_request.save(update_fields=["used_at", "updated_at"])
        except AuthenticationFailed as exc:
            return Response(
                {
                    "ok": False,
                    "message": str(exc.detail),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = reset_request.user
        try:
            validate_password(serializer.validated_data["password"], user=user)
        except DjangoValidationError as exc:
            return Response(
                {
                    "ok": False,
                    "message": " ".join(exc.messages),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["password"])
        user.must_set_password = False
        user.save(update_fields=["password", "must_set_password", "updated_at"])

        return Response(
            {
                "ok": True,
                "message": "Senha atualizada com sucesso.",
            },
            status=status.HTTP_200_OK,
        )


def _resolve_request_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AgentManualPasswordResetView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AgentManualPasswordResetRateThrottle]

    @extend_schema(
        request=AgentManualPasswordResetSerializer,
        responses={200: PublicPasswordResetResponseSerializer},
    )
    @transaction.atomic
    def post(self, request):
        serializer = AgentManualPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = (
            User.objects.filter(
                email__iexact=email,
                deleted_at__isnull=True,
                is_active=True,
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo="AGENTE",
            )
            .distinct()
            .first()
        )

        if user is not None:
            user.set_password(serializer.validated_data["password"])
            user.must_set_password = False
            user.save(update_fields=["password", "must_set_password", "updated_at"])

        logger.info(
            "agent_manual_password_reset email=%s eligible=%s user_id=%s ip=%s user_agent=%s at=%s",
            email,
            bool(user),
            user.id if user else None,
            _resolve_request_ip(request),
            request.META.get("HTTP_USER_AGENT", "")[:255],
            timezone.now().isoformat(),
        )

        return Response(
            PublicPasswordResetResponseSerializer(
                {
                    "ok": True,
                    "message": "Se o e-mail for elegível, a senha foi atualizada.",
                }
            ).data,
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)


def _parse_bool_query_param(value: str | None) -> bool | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "sim"}:
        return True
    if normalized in {"0", "false", "f", "no", "nao", "não"}:
        return False
    return None


class AdminUserViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.none()
    serializer_class = AdminUserListSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["first_name", "last_name", "email", "date_joined", "last_login"]
    ordering = ["first_name", "last_name", "email"]
    http_method_names = ["get", "patch", "head", "options", "post"]

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        if self.action in {"update", "partial_update"}:
            return AdminUserAccessUpdateSerializer
        return AdminUserListSerializer

    def get_base_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return (
            User.objects.prefetch_related("user_roles__role")
            .exclude(
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo__iexact="ASSOCIADO",
            )
            .distinct()
        )

    def _filter_manager_scope(self, queryset):
        user = self.request.user
        if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
            return queryset.none()
        if user.has_role("ADMIN"):
            return queryset
        return queryset.exclude(
            user_roles__deleted_at__isnull=True,
            user_roles__role__codigo__in=["ADMIN", "COORDENADOR"],
        )

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()

        user = self.request.user
        if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
            return User.objects.none()

        queryset = self.get_base_queryset()
        if self.action == "list":
            queryset = self._filter_manager_scope(queryset)

        role_code = self.request.query_params.get("role")
        if role_code:
            queryset = queryset.filter(
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo__iexact=role_code.strip(),
            )

        is_active = _parse_bool_query_param(self.request.query_params.get("is_active"))
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)

        return queryset

    def get_object(self):
        instance = super().get_object()
        if not is_manageable_user_for_manager(self.request.user, instance):
            raise PermissionDenied("Você não pode gerenciar este usuário.")
        return instance

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data["meta"] = self._build_meta()
        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        refreshed = self.get_base_queryset().get(pk=instance.pk)
        output = AdminUserListSerializer(
            refreshed,
            context=self.get_serializer_context(),
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        refreshed = self.get_base_queryset().get(pk=instance.pk)
        output = AdminUserListSerializer(
            refreshed,
            context=self.get_serializer_context(),
        )
        return Response(output.data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: AgentRedistributionPreviewSerializer})
    @action(detail=True, methods=["get"], url_path="redistribuicao-agente")
    def redistribuicao_agente(self, request, pk=None):
        user = self.get_object()
        payload = AgentPortfolioRedistributionService.build_preview(source_user=user)
        return Response(
            AgentRedistributionPreviewSerializer(
                payload,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: PasswordResetResultSerializer},
    )
    @action(detail=True, methods=["post"], url_path="resetar-senha")
    def resetar_senha(self, request, pk=None):
        user = self.get_object()
        serializer = PasswordResetRequestSerializer(
            data=request.data,
            context={"target_user": user},
        )
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["password"])
        user.must_set_password = False
        user.save(update_fields=["password", "must_set_password", "updated_at"])

        return Response(
            PasswordResetResultSerializer(
                {
                    "detail": "Senha atualizada com sucesso.",
                    "must_set_password": False,
                }
            ).data,
            status=status.HTTP_200_OK,
        )

    def _build_meta(self):
        user = self.request.user
        if not getattr(user, "is_authenticated", False) or not hasattr(user, "has_role"):
            return AdminUsersMetaSerializer(
                {
                    "total": 0,
                    "ativos": 0,
                    "admins": 0,
                    "troca_senha_pendente": 0,
                    "available_roles": Role.objects.none(),
                }
            ).data

        queryset = self._filter_manager_scope(self.get_base_queryset())
        available_roles = Role.objects.filter(
            codigo__in=get_manageable_role_codes(self.request.user)
        ).order_by("nome")

        data = {
            "total": queryset.count(),
            "ativos": queryset.filter(is_active=True).count(),
            "admins": queryset.filter(
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo="ADMIN",
            )
            .distinct()
            .count(),
            "troca_senha_pendente": queryset.filter(must_set_password=True).count(),
            "available_roles": available_roles,
        }
        return AdminUsersMetaSerializer(data).data


class ConfiguracaoComissaoViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    serializer_class = ConfiguracaoComissaoPayloadSerializer

    @extend_schema(responses={200: ConfiguracaoComissaoPayloadSerializer})
    def list(self, request):
        payload = ComissaoService.build_settings_payload()
        return Response(
            ConfiguracaoComissaoPayloadSerializer(
                payload,
                context={"request": request},
            ).data
        )

    @extend_schema(
        request=ConfiguracaoComissaoGlobalWriteSerializer,
        responses={200: ConfiguracaoComissaoPayloadSerializer},
    )
    @action(detail=False, methods=["post"], url_path="global")
    @transaction.atomic
    def aplicar_global(self, request):
        serializer = ConfiguracaoComissaoGlobalWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = ComissaoService.aplicar_percentual_global(
            percentual=serializer.validated_data["percentual"],
            motivo=serializer.validated_data.get("motivo", ""),
            user=request.user,
        )
        return Response(
            ConfiguracaoComissaoPayloadSerializer(
                payload,
                context={"request": request},
            ).data
        )

    @extend_schema(
        request=ConfiguracaoComissaoAgentesWriteSerializer,
        responses={200: ConfiguracaoComissaoPayloadSerializer},
    )
    @action(detail=False, methods=["post"], url_path="agentes")
    @transaction.atomic
    def aplicar_agentes(self, request):
        serializer = ConfiguracaoComissaoAgentesWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = ComissaoService.aplicar_percentual_agentes(
            agente_ids=serializer.validated_data["agentes"],
            percentual=serializer.validated_data["percentual"],
            motivo=serializer.validated_data.get("motivo", ""),
            user=request.user,
        )
        return Response(
            ConfiguracaoComissaoPayloadSerializer(
                payload,
                context={"request": request},
            ).data
        )

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ],
        request=ConfiguracaoComissaoAgenteResetSerializer,
        responses={200: ConfiguracaoComissaoPayloadSerializer},
    )
    @action(detail=True, methods=["post"], url_path="remover-override")
    @transaction.atomic
    def remover_override(self, request, pk=None):
        serializer = ConfiguracaoComissaoAgenteResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = ComissaoService.remover_override_agente(
            agente_id=int(pk),
            motivo=serializer.validated_data.get("motivo", ""),
            user=request.user,
        )
        return Response(
            ConfiguracaoComissaoPayloadSerializer(
                payload,
                context={"request": request},
            ).data
        )
