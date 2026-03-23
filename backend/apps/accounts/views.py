from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.pagination import StandardResultsSetPagination

from .models import Role, User
from .permissions import IsCoordenadorOrAdmin
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserAccessUpdateSerializer,
    AdminUserListSerializer,
    AdminUsersMetaSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetRequestSerializer,
    PasswordResetResultSerializer,
    RefreshSerializer,
    UserSerializer,
    get_manageable_role_codes,
    is_manageable_user_for_manager,
)


class LoginRateThrottle(AnonRateThrottle):
    rate = "10/min"


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(request=LoginSerializer, responses={200: LoginSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(serializer.save(), status=status.HTTP_200_OK)


class RefreshView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(request=RefreshSerializer, responses={200: RefreshSerializer})
    def post(self, request):
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
