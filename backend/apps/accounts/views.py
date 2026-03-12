from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    UserSerializer,
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
