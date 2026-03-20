from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.associados.mobile_legacy import (
    build_bootstrap_payload,
    build_me_payload,
    resolve_mobile_associado,
)

from .mobile_legacy_auth import (
    LegacyMobileTokenAuthentication,
    authenticate_legacy_mobile_login,
    build_password_reset_request,
    consume_password_reset_token,
    ensure_user_role,
    ensure_self_service_roles,
    issue_mobile_access_token,
    revoke_mobile_access_token,
)
from .models import User
from .serializers import PasswordResetRequestSerializer
from .views import LoginRateThrottle


class LegacyLoginSerializer(serializers.Serializer):
    login = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class LegacyRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    password_confirmation = serializers.CharField(trim_whitespace=False, write_only=True)
    terms = serializers.BooleanField(required=False, default=False)
    terms_version = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        password_serializer = PasswordResetRequestSerializer(
            data={
                "password": attrs["password"],
                "password_confirm": attrs["password_confirmation"],
            },
            context={},
        )
        password_serializer.is_valid(raise_exception=True)
        attrs["password"] = password_serializer.validated_data["password"]
        return attrs


class LegacyForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()


class LegacyResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    token = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    password_confirmation = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        password_serializer = PasswordResetRequestSerializer(
            data={
                "password": attrs["password"],
                "password_confirm": attrs["password_confirmation"],
            },
            context={},
        )
        password_serializer.is_valid(raise_exception=True)
        attrs["password"] = password_serializer.validated_data["password"]
        return attrs


def _split_name(full_name: str) -> tuple[str, str]:
    normalized = " ".join((full_name or "").split()).strip()
    if not normalized:
        return "Associado", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name[:150], last_name[:150]


def _roles_for_response(user: User, *, include_associado_alias: bool) -> list[str]:
    if include_associado_alias:
        return ensure_self_service_roles(user)

    ensure_user_role(user, "ASSOCIADODOIS")
    return list(
        user.user_roles.filter(deleted_at__isnull=True)
        .order_by("role_id")
        .values_list("role__codigo", flat=True)
    )


class LegacyMobileAuthenticatedAPIView(APIView):
    authentication_classes = [LegacyMobileTokenAuthentication]
    permission_classes = [permissions.IsAuthenticated]


class LegacyLoginView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LegacyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, associado = authenticate_legacy_mobile_login(
            login=serializer.validated_data["login"],
            password=serializer.validated_data["password"],
            request=request,
        )
        token = issue_mobile_access_token(user, request=request)
        payload = build_bootstrap_payload(associado, request=request)
        roles = _roles_for_response(user, include_associado_alias=associado is not None)

        return Response(
            {
                "ok": True,
                "token": token.key,
                "token_type": "Bearer",
                "user": {
                    "id": user.id,
                    "name": user.full_name or user.email,
                    "email": user.email,
                },
                "roles": roles,
                **payload,
            },
            status=status.HTTP_200_OK,
        )


class LegacyLogoutView(LegacyMobileAuthenticatedAPIView):
    def post(self, request):
        legacy_token = getattr(request, "legacy_mobile_token", None)
        if legacy_token is not None:
            revoke_mobile_access_token(legacy_token)
        return Response({"ok": True}, status=status.HTTP_200_OK)


class LegacyHomeView(LegacyMobileAuthenticatedAPIView):
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            {"ok": True, **build_bootstrap_payload(associado, request=request)},
            status=status.HTTP_200_OK,
        )


class LegacyMeView(LegacyMobileAuthenticatedAPIView):
    def get(self, request):
        associado = resolve_mobile_associado(request.user)
        return Response(
            build_me_payload(request.user, associado, request=request),
            status=status.HTTP_200_OK,
        )


class LegacyRegisterView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = LegacyRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        if User.all_objects.filter(email__iexact=email).exists():
            return Response(
                {
                    "ok": False,
                    "message": "Esse e-mail já possui cadastro em nosso sistema.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not serializer.validated_data["terms"]:
            return Response(
                {
                    "ok": False,
                    "message": "É necessário aceitar os termos para criar a conta.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_name, last_name = _split_name(serializer.validated_data["name"])
        user = User.objects.create_user(
            email=email,
            password=serializer.validated_data["password"],
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            must_set_password=False,
        )
        ensure_user_role(user, "ASSOCIADODOIS")

        token = issue_mobile_access_token(user, request=request, name="legacy-mobile-register")
        return Response(
            {
                "ok": True,
                "message": "Conta criada com sucesso.",
                "token": token.key,
                "token_type": "Bearer",
                "user": {
                    "id": user.id,
                    "name": user.full_name or user.email,
                    "email": user.email,
                },
                "roles": _roles_for_response(user, include_associado_alias=False),
            },
            status=status.HTTP_201_CREATED,
        )


class LegacyCheckEmailView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        email = (request.query_params.get("email") or "").strip().lower()
        if not email:
            return Response(
                {
                    "ok": False,
                    "message": "Informe um e-mail válido.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        sources: list[str] = []
        if User.all_objects.filter(email__iexact=email).exists():
            sources.append("users")

        from apps.associados.models import Associado  # noqa: PLC0415

        if Associado.objects.filter(email__iexact=email).exists():
            sources.append("agente_cadastros")

        return Response(
            {
                "ok": True,
                "email": email,
                "exists": bool(sources),
                "sources": sources,
            },
            status=status.HTTP_200_OK,
        )


class LegacyForgotPasswordView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LegacyForgotPasswordSerializer(data=request.data)
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


class LegacyResetPasswordView(APIView):
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = LegacyResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            reset_request = consume_password_reset_token(
                email=serializer.validated_data["email"],
                token=serializer.validated_data["token"],
            )
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
