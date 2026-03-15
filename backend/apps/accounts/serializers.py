import re

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, User, UserRole


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def get_user_role_codes(user: User) -> list[str]:
    prefetched_user_roles = getattr(user, "_prefetched_objects_cache", {}).get("user_roles")
    if prefetched_user_roles is not None:
        active_links = [link for link in prefetched_user_roles if link.deleted_at is None]
        return [
            link.role.codigo
            for link in sorted(active_links, key=lambda user_role: user_role.role_id)
        ]

    return list(
        UserRole.objects.filter(user=user, deleted_at__isnull=True)
        .order_by("role_id")
        .values_list("role__codigo", flat=True)
    )


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    primary_role = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "primary_role",
            "roles",
        ]

    def get_roles(self, obj: User) -> list[str]:
        return get_user_role_codes(obj)

    def get_primary_role(self, obj: User) -> str | None:
        roles = get_user_role_codes(obj)
        return roles[0] if roles else None


class AvailableRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["codigo", "nome"]


class AdminUserListSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    primary_role = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    is_current_user = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "primary_role",
            "roles",
            "is_active",
            "must_set_password",
            "date_joined",
            "last_login",
            "is_current_user",
        ]

    def get_roles(self, obj: User) -> list[str]:
        return get_user_role_codes(obj)

    def get_primary_role(self, obj: User) -> str | None:
        roles = get_user_role_codes(obj)
        return roles[0] if roles else None

    def get_is_current_user(self, obj: User) -> bool:
        request = self.context.get("request")
        return bool(request and request.user and request.user.pk == obj.pk)


class AdminUsersMetaSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    ativos = serializers.IntegerField()
    admins = serializers.IntegerField()
    troca_senha_pendente = serializers.IntegerField()
    available_roles = AvailableRoleSerializer(many=True)


class AdminUserAccessUpdateSerializer(serializers.Serializer):
    roles = serializers.ListField(
        child=serializers.CharField(max_length=30),
        required=False,
        allow_empty=False,
    )
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        instance: User = self.instance
        request = self.context["request"]

        role_codes = attrs.get("roles")
        if role_codes is None:
            roles = [
                user_role.role
                for user_role in instance.user_roles.filter(deleted_at__isnull=True)
                .select_related("role")
                .order_by("role_id")
            ]
        else:
            normalized_codes = sorted(
                {
                    code.strip().upper()
                    for code in role_codes
                    if isinstance(code, str) and code.strip()
                }
            )
            if not normalized_codes:
                raise serializers.ValidationError(
                    {"roles": "Selecione ao menos um perfil de acesso."}
                )

            roles = list(
                Role.objects.filter(codigo__in=normalized_codes)
                .exclude(codigo__iexact="ASSOCIADO")
                .order_by("id")
            )
            found_codes = {role.codigo for role in roles}
            missing_codes = [code for code in normalized_codes if code not in found_codes]
            if missing_codes:
                raise serializers.ValidationError(
                    {
                        "roles": (
                            "Perfis inválidos: " + ", ".join(sorted(missing_codes)) + "."
                        )
                    }
                )

        next_is_active = attrs.get("is_active", instance.is_active)
        next_role_codes = {role.codigo for role in roles}

        if instance.pk == request.user.pk and not next_is_active:
            raise serializers.ValidationError(
                {"is_active": "Você não pode desativar o próprio usuário em sessão."}
            )

        if (
            instance.pk == request.user.pk
            and request.user.has_role("ADMIN")
            and "ADMIN" not in next_role_codes
        ):
            raise serializers.ValidationError(
                {"roles": "Seu usuário precisa manter o perfil ADMIN."}
            )

        attrs["roles"] = roles
        attrs["is_active"] = next_is_active
        return attrs

    def update(self, instance: User, validated_data):
        roles: list[Role] = validated_data["roles"]
        role_codes = {role.codigo for role in roles}
        next_is_active = validated_data["is_active"]
        next_role_ids = {role.id for role in roles}

        instance.is_active = next_is_active
        instance.is_staff = instance.is_superuser or "ADMIN" in role_codes
        instance.save(update_fields=["is_active", "is_staff", "updated_at"])

        existing_links = {
            user_role.role_id: user_role
            for user_role in UserRole.all_objects.filter(user=instance)
        }

        for role in roles:
            link = existing_links.get(role.id)
            if link is None:
                UserRole.objects.create(user=instance, role=role)
                continue

            if link.deleted_at is not None:
                link.deleted_at = None
                link.assigned_at = timezone.now()
                link.save(update_fields=["deleted_at", "assigned_at", "updated_at"])

        for role_id, link in existing_links.items():
            if role_id not in next_role_ids and link.deleted_at is None:
                link.hard_delete()

        return instance


class PasswordResetResultSerializer(serializers.Serializer):
    detail = serializers.CharField()
    must_set_password = serializers.BooleanField()


class PasswordResetRequestSerializer(serializers.Serializer):
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    password_confirm = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate(self, attrs):
        password = attrs["password"]
        password_confirm = attrs["password_confirm"]

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "A confirmação da senha não confere."}
            )

        try:
            validate_password(password, user=self.context.get("target_user"))
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})

        return attrs


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False, allow_blank=True)
    cpf = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        email = (attrs.get("email") or "").strip()
        cpf = _only_digits(attrs.get("cpf") or "")
        password = attrs["password"]

        if not email and not cpf:
            raise serializers.ValidationError("Informe email ou CPF.")

        if cpf and not email:
            # Login via CPF: resolve o e-mail do usuário vinculado ao associado
            from apps.associados.models import Associado  # noqa: PLC0415

            try:
                associado = Associado.objects.select_related("user").get(cpf_cnpj=cpf)
            except Associado.DoesNotExist:
                raise serializers.ValidationError("Credenciais inválidas.")

            if not associado.user:
                raise serializers.ValidationError("Usuário não vinculado a este CPF.")

            email = associado.user.email

        user = authenticate(request=request, username=email, password=password)
        if not user:
            raise serializers.ValidationError("Credenciais inválidas.")
        if not user.is_active:
            raise serializers.ValidationError("Usuário inativo.")
        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        user = validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        }


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        serializer = TokenRefreshSerializer(data=attrs)
        try:
            serializer.is_valid(raise_exception=True)
        except (InvalidToken, TokenError):
            raise serializers.ValidationError("Refresh token invalido ou expirado.")
        return serializer.validated_data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True)
