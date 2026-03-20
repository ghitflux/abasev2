from __future__ import annotations

import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from apps.associados.models import Associado

from .models import MobileAccessToken, PasswordResetRequest, Role, User, UserRole

MOBILE_TOKEN_LIFETIME = timedelta(days=3650)
PASSWORD_RESET_LIFETIME = timedelta(hours=24)

ROLE_METADATA = {
    "ASSOCIADO": (
        "Associado",
        "Autoatendimento do associado.",
    ),
    "ASSOCIADODOIS": (
        "Associado 2",
        "Compatibilidade legada do aplicativo mobile.",
    ),
}


def only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def looks_like_email(value: str | None) -> bool:
    return bool(re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", (value or "").strip()))


def split_name(full_name: str) -> tuple[str, str]:
    normalized = " ".join((full_name or "").split()).strip()
    if not normalized:
        return "Associado", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name[:150], last_name[:150]


def _ensure_role(code: str) -> Role:
    nome, descricao = ROLE_METADATA.get(code, (code.title(), ""))
    role, _ = Role.all_objects.get_or_create(
        codigo=code,
        defaults={
            "nome": nome,
            "descricao": descricao,
            "deleted_at": None,
        },
    )
    update_fields: list[str] = []
    if role.deleted_at is not None:
        role.deleted_at = None
        update_fields.append("deleted_at")
    if role.nome != nome:
        role.nome = nome
        update_fields.append("nome")
    if role.descricao != descricao:
        role.descricao = descricao
        update_fields.append("descricao")
    if update_fields:
        role.save(update_fields=[*update_fields, "updated_at"])
    return role


def ensure_user_role(user: User, code: str) -> Role:
    role = _ensure_role(code)
    link = UserRole.all_objects.filter(user=user, role=role).first()
    if link is None:
        UserRole.objects.create(user=user, role=role)
        return role
    if link.deleted_at is not None:
        link.deleted_at = None
        link.assigned_at = timezone.now()
        link.save(update_fields=["deleted_at", "assigned_at", "updated_at"])
    return role


def ensure_self_service_roles(user: User, *, include_legacy_alias: bool = True) -> list[str]:
    ensure_user_role(user, "ASSOCIADODOIS")
    if include_legacy_alias:
        ensure_user_role(user, "ASSOCIADO")

    role_codes = list(
        UserRole.objects.filter(user=user, deleted_at__isnull=True)
        .order_by("role_id")
        .values_list("role__codigo", flat=True)
    )

    if "ASSOCIADODOIS" not in role_codes:
        role_codes.append("ASSOCIADODOIS")
    if include_legacy_alias and "ASSOCIADO" not in role_codes:
        role_codes.append("ASSOCIADO")
    return role_codes


def resolve_associado_for_user(user: User) -> Associado | None:
    try:
        return user.associado
    except Associado.DoesNotExist:
        return Associado.objects.filter(email__iexact=user.email).first()


@transaction.atomic
def ensure_associado_user(associado: Associado) -> User:
    if associado.user_id:
        user = associado.user
    else:
        email = (associado.email or "").strip().lower()
        user = None
        if email:
            user = User.all_objects.filter(email__iexact=email).first()

        if user is None:
            generated_email = email or f"{associado.cpf_cnpj}@app.abase.local"
            if User.all_objects.filter(email__iexact=generated_email).exists():
                generated_email = f"{associado.cpf_cnpj}.{associado.pk}@app.abase.local"
            first_name, last_name = split_name(associado.nome_completo)
            raw_password = associado.matricula_display or associado.cpf_cnpj or secrets.token_hex(8)
            user = User.objects.create_user(
                email=generated_email,
                password=raw_password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                must_set_password=False,
            )

        associado.user = user
        associado.save(update_fields=["user", "updated_at"])

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])

    ensure_self_service_roles(user)
    return user


def _matches_associado_matricula(associado: Associado, raw_password: str) -> bool:
    password_digits = only_digits(raw_password)
    if not password_digits:
        return False

    candidates = {
        only_digits(associado.matricula_orgao),
        only_digits(associado.matricula),
        only_digits(associado.matricula_display),
    }
    candidates.discard("")
    return password_digits in candidates


def authenticate_legacy_mobile_login(*, login: str, password: str, request=None) -> tuple[User, Associado | None]:
    login = (login or "").strip()
    password = password or ""
    if not login or not password:
        raise AuthenticationFailed("Informe os dados de acesso.")

    user: User | None = None
    associado: Associado | None = None

    if looks_like_email(login):
        user = authenticate(request=request, username=login, password=password)
        if user is None:
            raise AuthenticationFailed("Credenciais inválidas.")
        associado = resolve_associado_for_user(user)
        if associado is not None and not associado.user_id:
            associado.user = user
            associado.save(update_fields=["user", "updated_at"])
    else:
        cpf = only_digits(login)
        associado = (
            Associado.objects.select_related("user")
            .filter(cpf_cnpj=cpf)
            .first()
        )
        if associado is None:
            raise AuthenticationFailed("Credenciais inválidas.")

        if _matches_associado_matricula(associado, password):
            user = ensure_associado_user(associado)
        elif associado.user_id:
            user = authenticate(request=request, username=associado.user.email, password=password)
            if user is None:
                raise AuthenticationFailed("Credenciais inválidas.")
        else:
            raise AuthenticationFailed("Credenciais inválidas.")

    if user is None:
        raise AuthenticationFailed("Credenciais inválidas.")
    if not user.is_active:
        raise AuthenticationFailed("Usuário inativo.")

    if associado is not None:
        ensure_self_service_roles(user)

    return user, associado


@transaction.atomic
def issue_mobile_access_token(user: User, *, request=None, name: str = "legacy-mobile") -> MobileAccessToken:
    now = timezone.now()
    MobileAccessToken.objects.filter(
        user=user,
        scope=MobileAccessToken.Scope.LEGACY_APP,
        revoked_at__isnull=True,
    ).update(revoked_at=now, updated_at=now)

    raw_key = secrets.token_hex(32)
    return MobileAccessToken.objects.create(
        user=user,
        key=raw_key,
        token_prefix=raw_key[:12],
        name=name,
        scope=MobileAccessToken.Scope.LEGACY_APP,
        expires_at=now + MOBILE_TOKEN_LIFETIME,
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        ip_address=(request.META.get("REMOTE_ADDR") if request else None),
    )


def revoke_mobile_access_token(token: MobileAccessToken) -> None:
    if token.revoked_at is not None:
        return
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at", "updated_at"])


def build_password_reset_request(*, user: User, request=None) -> PasswordResetRequest:
    now = timezone.now()
    PasswordResetRequest.objects.filter(
        user=user,
        used_at__isnull=True,
        deleted_at__isnull=True,
    ).update(deleted_at=now, updated_at=now)

    reset_request = PasswordResetRequest.objects.create(
        user=user,
        email=user.email,
        token=secrets.token_urlsafe(32),
        expires_at=now + PASSWORD_RESET_LIFETIME,
        requested_from_ip=(request.META.get("REMOTE_ADDR") if request else None),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
    )

    send_mail(
        subject="ABASE - redefinição de senha",
        message=(
            "Use o código abaixo para redefinir sua senha no aplicativo ABASE:\n\n"
            f"{reset_request.token}\n\n"
            "Se você não solicitou a redefinição, ignore este e-mail."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@abase.local"),
        recipient_list=[user.email],
        fail_silently=True,
    )
    return reset_request


def consume_password_reset_token(*, email: str, token: str) -> PasswordResetRequest:
    normalized_email = (email or "").strip().lower()
    reset_request = (
        PasswordResetRequest.objects.select_related("user")
        .filter(
            email__iexact=normalized_email,
            token=token,
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
    return reset_request


class LegacyMobileTokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate_header(self, request):
        return self.keyword

    def authenticate(self, request):
        raw_header = get_authorization_header(request).decode("utf-8")
        token_key = ""

        if raw_header:
            parts = raw_header.split()
            if len(parts) == 2 and parts[0].lower() == self.keyword.lower():
                token_key = parts[1].strip()

        if not token_key:
            token_key = (request.query_params.get("token") or "").strip()
        if not token_key:
            return None

        token = (
            MobileAccessToken.objects.select_related("user")
            .filter(key=token_key, deleted_at__isnull=True)
            .first()
        )
        if token is None or not token.is_active:
            raise AuthenticationFailed("Token mobile inválido ou expirado.")
        if not token.user.is_active:
            raise AuthenticationFailed("Usuário inativo.")

        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at", "updated_at"])
        request.legacy_mobile_token = token
        return token.user, token
