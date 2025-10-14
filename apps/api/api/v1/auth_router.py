from ninja import Router
from ninja.errors import HttpError
from core.auth import AuthenticationManager
from core.auth.security import (
    track_failed_login,
    reset_failed_login,
    is_locked_out,
    get_lockout_time_remaining,
)
from core.models.event_log import EventLog
from .schemas import AuthOut, UserOut

router = Router(tags=["auth"])
manager = AuthenticationManager()


@router.post("/oidc/callback", response=AuthOut)
async def oidc_callback(request, code: str, code_verifier: str = ""):
    """Callback OIDC após autenticação no provider"""
    try:
        data = await manager.authenticate_user(
            "oidc", {"code": code, "metadata": {"code_verifier": code_verifier}}
        )

        # Registrar evento de login bem-sucedido
        user_id = data.get("user", {}).get("id")
        if user_id:
            await EventLog.objects.acreate(
                entity_type="user",
                entity_id=str(user_id),
                event_type="LOGIN_SUCCESS",
                payload={"method": "oidc"},
                actor_id=str(user_id),
            )

        return data

    except Exception as e:
        # Registrar falha de login
        await EventLog.objects.acreate(
            entity_type="auth",
            entity_id="oidc",
            event_type="LOGIN_FAILED",
            payload={"error": str(e), "method": "oidc"},
        )
        raise


@router.post("/login/local")
async def login_local(request, username: str, password: str):
    """Login com credenciais locais (com proteção de lockout)"""
    # Verifica se conta está bloqueada
    if is_locked_out(username):
        remaining = get_lockout_time_remaining(username)
        raise HttpError(
            403,
            {
                "error": "account_locked",
                "retry_after": remaining,
                "message": f"Conta bloqueada. Tente novamente em {remaining // 60} minutos.",
            },
        )

    try:
        # Autentica usuário (implementar lógica de verificação de senha)
        from django.contrib.auth import authenticate

        user = authenticate(request, username=username, password=password)

        if not user:
            # Registra tentativa falha
            failed_count = track_failed_login(username)

            # Log de tentativa falha
            await EventLog.objects.acreate(
                entity_type="user",
                entity_id=username,
                event_type="LOGIN_FAILED",
                payload={"method": "local", "failed_count": failed_count},
            )

            # Verifica se atingiu limite
            if failed_count >= 5:
                raise HttpError(
                    403,
                    {
                        "error": "account_locked",
                        "message": "Muitas tentativas falhas. Conta bloqueada temporariamente.",
                    },
                )

            raise HttpError(401, {"error": "invalid_credentials", "attempts_remaining": 5 - failed_count})

        # Login bem-sucedido - reseta contador
        reset_failed_login(username)

        # Gera tokens JWT
        data = await manager.authenticate_user(
            "jwt", {"metadata": {"user_id": str(user.id)}}
        )

        # Log de sucesso
        await EventLog.objects.acreate(
            entity_type="user",
            entity_id=str(user.id),
            event_type="LOGIN_SUCCESS",
            payload={"method": "local"},
            actor_id=str(user.id),
        )

        return data

    except HttpError:
        raise
    except Exception as e:
        await EventLog.objects.acreate(
            entity_type="auth",
            entity_id="local",
            event_type="LOGIN_ERROR",
            payload={"error": str(e)},
        )
        raise HttpError(500, "authentication_error")


@router.post("/refresh")
async def refresh(request, refresh_token: str):
    """Renova access token usando refresh token"""
    try:
        data = await manager.refresh_access_token(refresh_token)

        # Log de refresh
        claims = await manager.contexts["jwt"].validate_token(refresh_token)
        if claims[0]:
            user_id = claims[1].get("user_id")
            await EventLog.objects.acreate(
                entity_type="user",
                entity_id=str(user_id),
                event_type="TOKEN_REFRESHED",
                payload={},
                actor_id=str(user_id),
            )

        return data

    except Exception as e:
        await EventLog.objects.acreate(
            entity_type="auth",
            entity_id="refresh",
            event_type="TOKEN_REFRESH_FAILED",
            payload={"error": str(e)},
        )
        raise HttpError(401, "invalid_refresh_token")


@router.post("/logout")
async def logout(request, token: str, user_id: str, global_logout: bool = False):
    """Logout: invalida tokens"""
    try:
        await manager.logout_user(user_id, token, global_logout)

        # Log de logout
        await EventLog.objects.acreate(
            entity_type="user",
            entity_id=str(user_id),
            event_type="LOGOUT",
            payload={"global": global_logout},
            actor_id=str(user_id),
        )

        return {"ok": True}

    except Exception as e:
        raise HttpError(500, "logout_error")


@router.get("/me", response=UserOut)
async def me(request):
    """Retorna dados do usuário autenticado"""
    # Extrai token
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HttpError(401, "missing_token")

    token = auth_header.split(" ", 1)[1]

    # Valida token
    claims = await manager.validate_request(token)

    return {
        "id": claims.get("user_id"),
        "email": claims.get("email", ""),
        "name": "",
        "perfil": claims.get("perfil", "AGENTE"),
    }


@router.post("/validate")
async def validate(request):
    """Valida se token é válido"""
    return {"ok": True}
