from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    primary_role = serializers.CharField(read_only=True)
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
        return list(obj.roles.values_list("codigo", flat=True))


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request=request,
            username=attrs["email"],
            password=attrs["password"],
        )
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
