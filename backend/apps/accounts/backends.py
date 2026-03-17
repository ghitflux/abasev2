from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import DatabaseError, connection, transaction

from apps.accounts.hashers import (
    LegacyLaravelBcryptPasswordHasher,
    encode_legacy_bcrypt_hash,
    is_legacy_bcrypt_hash,
)
from apps.accounts.management.seed_utils import DEFAULT_ROLES
from apps.accounts.models import Role

LEGACY_ROLE_CODE_MAP = {
    "admin": "ADMIN",
    "agente": "AGENTE",
    "analista": "ANALISTA",
    "associado": "ASSOCIADO",
    "associadodois": "ASSOCIADODOIS",
    "coordenador": "COORDENADOR",
    "tesoureiro": "TESOUREIRO",
    "user": "USER",
}

ROLE_METADATA = {
    codigo: {"nome": nome, "descricao": descricao}
    for codigo, nome, descricao in DEFAULT_ROLES
}


class LegacyLaravelUserBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        email = kwargs.get(user_model.USERNAME_FIELD) or kwargs.get("email") or username
        if not email or password is None:
            return None

        legacy_user = _fetch_legacy_user(email)
        if legacy_user is None:
            return None

        imported_password = _normalize_legacy_password(legacy_user["password"])
        if not imported_password:
            return None

        hasher = LegacyLaravelBcryptPasswordHasher()
        try:
            if not hasher.verify(password, imported_password):
                return None
        except ValueError:
            return None

        return _sync_legacy_user(legacy_user, imported_password)

    def get_user(self, user_id):
        return get_user_model().objects.filter(pk=user_id).first()


def _fetch_legacy_user(email: str) -> dict[str, object] | None:
    try:
        if "users" not in connection.introspection.table_names():
            return None
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, password, must_set_password, profile_photo_path
                FROM users
                WHERE LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                [email],
            )
            row = cursor.fetchone()
    except DatabaseError:
        return None

    if row is None:
        return None

    return {
        "id": row[0],
        "name": row[1] or "",
        "email": row[2],
        "password": row[3] or "",
        "must_set_password": bool(row[4]),
        "profile_photo_path": row[5] or "",
    }


def _fetch_legacy_role_codes(legacy_user_id: int) -> list[str]:
    try:
        existing_tables = set(connection.introspection.table_names())
        if "roles" not in existing_tables or "role_user" not in existing_tables:
            return []

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.name
                FROM role_user ru
                INNER JOIN roles r ON r.id = ru.role_id
                WHERE ru.user_id = %s
                ORDER BY ru.id ASC
                """,
                [legacy_user_id],
            )
            rows = cursor.fetchall()
    except DatabaseError:
        return []

    mapped_codes: list[str] = []
    seen_codes: set[str] = set()

    for (legacy_name,) in rows:
        normalized_name = str(legacy_name or "").strip().lower()
        codigo = LEGACY_ROLE_CODE_MAP.get(normalized_name)
        if codigo and codigo not in seen_codes:
            mapped_codes.append(codigo)
            seen_codes.add(codigo)

    return mapped_codes


def _normalize_legacy_password(value: str) -> str | None:
    if not is_legacy_bcrypt_hash(value):
        return None
    return encode_legacy_bcrypt_hash(value)


def _split_name(full_name: str) -> tuple[str, str]:
    normalized = " ".join(full_name.split()).strip()
    if not normalized:
        return "Usuario", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name[:150], last_name[:150]


def _ensure_roles(role_codes: list[str]) -> list[Role]:
    ensured_roles: list[Role] = []

    for codigo in role_codes:
        metadata = ROLE_METADATA.get(codigo, {"nome": codigo.title(), "descricao": ""})
        role, _ = Role.all_objects.get_or_create(
            codigo=codigo,
            defaults={
                "nome": metadata["nome"],
                "descricao": metadata["descricao"],
                "deleted_at": None,
            },
        )

        update_fields: list[str] = []
        if role.nome != metadata["nome"]:
            role.nome = metadata["nome"]
            update_fields.append("nome")
        if role.descricao != metadata["descricao"]:
            role.descricao = metadata["descricao"]
            update_fields.append("descricao")
        if role.deleted_at is not None:
            role.deleted_at = None
            update_fields.append("deleted_at")
        if update_fields:
            role.save(update_fields=[*update_fields, "updated_at"])

        ensured_roles.append(role)

    return ensured_roles


def _sync_legacy_user(legacy_user: dict[str, object], imported_password: str):
    user_model = get_user_model()
    first_name, last_name = _split_name(str(legacy_user["name"]))
    role_codes = _fetch_legacy_role_codes(int(legacy_user["id"]))
    roles = _ensure_roles(role_codes)
    is_admin = "ADMIN" in role_codes

    with transaction.atomic():
        user, _ = user_model.all_objects.get_or_create(
            email=str(legacy_user["email"]),
            defaults={
                "first_name": first_name,
                "last_name": last_name,
                "password": imported_password,
                "must_set_password": bool(legacy_user["must_set_password"]),
                "profile_photo_path": str(legacy_user["profile_photo_path"]),
                "is_active": True,
                "is_staff": is_admin,
                "is_superuser": is_admin,
                "deleted_at": None,
            },
        )

        update_fields: list[str] = []
        if user.first_name != first_name:
            user.first_name = first_name
            update_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            update_fields.append("last_name")
        if user.password != imported_password:
            user.password = imported_password
            update_fields.append("password")
        if user.must_set_password != bool(legacy_user["must_set_password"]):
            user.must_set_password = bool(legacy_user["must_set_password"])
            update_fields.append("must_set_password")
        if user.profile_photo_path != str(legacy_user["profile_photo_path"]):
            user.profile_photo_path = str(legacy_user["profile_photo_path"])
            update_fields.append("profile_photo_path")
        if not user.is_active:
            user.is_active = True
            update_fields.append("is_active")
        if user.is_staff != is_admin:
            user.is_staff = is_admin
            update_fields.append("is_staff")
        if user.is_superuser != is_admin:
            user.is_superuser = is_admin
            update_fields.append("is_superuser")
        if user.deleted_at is not None:
            user.deleted_at = None
            update_fields.append("deleted_at")
        if update_fields:
            user.save(update_fields=[*update_fields, "updated_at"])

        if roles:
            current_codes = set(user.roles.values_list("codigo", flat=True))
            next_codes = {role.codigo for role in roles}
            if current_codes != next_codes:
                user.roles.set(roles)

    return user
