from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.sessions.models import Session
from django.core.files.storage import default_storage
from django.db import connection

from apps.accounts.models import MobileAccessToken, PasswordResetRequest, Role, User, UserRole
from apps.importacao.models import ArquivoRetorno


RETURN_MONTHS: tuple[date, ...] = (
    date(2025, 10, 1),
    date(2025, 11, 1),
    date(2025, 12, 1),
    date(2026, 1, 1),
    date(2026, 2, 1),
)
RETURN_STAGE_MANIFEST = "return_files_manifest.json"

PRESERVED_TABLES = {
    "accounts_mobileaccesstoken",
    "accounts_passwordresetrequest",
    "accounts_role",
    "accounts_user",
    "accounts_userrole",
    "auth_group",
    "auth_permission",
    "django_content_type",
    "django_session",
}
PRESERVED_AUTO_TABLES = {
    "accounts_user_groups",
    "accounts_user_user_permissions",
    "auth_group_permissions",
}
PRESERVED_ALL_TABLES = PRESERVED_TABLES | PRESERVED_AUTO_TABLES
COUNT_FLEX_TABLES = {
    "accounts_role",
    "accounts_user",
    "accounts_userrole",
}
COUNT_STRICT_TABLES = PRESERVED_ALL_TABLES - COUNT_FLEX_TABLES


@dataclass(frozen=True)
class StagedReturnFile:
    competencia: date
    source_id: int
    source_name: str
    source_storage_path: str
    staged_path: str

    def as_dict(self) -> dict[str, str | int]:
        return {
            "competencia": self.competencia.isoformat(),
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_storage_path": self.source_storage_path,
            "staged_path": self.staged_path,
        }


def default_restore_report_path(prefix: str) -> Path:
    timestamp = date.today().strftime("%Y%m%d")
    workspace_root = Path("/workspace")
    if workspace_root.exists():
        return workspace_root / "backups" / f"{prefix}_{timestamp}.json"
    return Path(settings.BASE_DIR) / "media" / "relatorios" / f"{prefix}_{timestamp}.json"


def managed_table_names() -> list[str]:
    return sorted(
        {
            model._meta.db_table
            for model in apps.get_models()
            if model._meta.managed and not model._meta.proxy
        }
    )


def tables_to_truncate() -> list[str]:
    return [
        table_name
        for table_name in managed_table_names()
        if table_name not in PRESERVED_TABLES
    ]


def capture_preserved_auth_counts() -> dict[str, int]:
    table_counts = {
        "accounts_user": User.all_objects.count(),
        "accounts_role": Role.all_objects.count(),
        "accounts_userrole": UserRole.all_objects.count(),
        "accounts_mobileaccesstoken": MobileAccessToken.all_objects.count(),
        "accounts_passwordresetrequest": PasswordResetRequest.all_objects.count(),
        "auth_group": Group.objects.count(),
        "auth_permission": Permission.objects.count(),
        "django_session": Session.objects.count(),
    }
    with connection.cursor() as cursor:
        for table_name in sorted(PRESERVED_AUTO_TABLES):
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {connection.ops.quote_name(table_name)}")
            except Exception:
                table_counts[table_name] = -1
                continue
            row = cursor.fetchone()
            table_counts[table_name] = int(row[0]) if row else 0
    return table_counts


def _snapshot_queryset(values: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return [dict(row) for row in values]


def capture_preserved_auth_snapshot() -> dict[str, object]:
    return {
        "counts": capture_preserved_auth_counts(),
        "users": _snapshot_queryset(
            User.all_objects.order_by("id").values("id", "email", "password")
        ),
        "roles": _snapshot_queryset(
            Role.all_objects.order_by("id").values("id", "codigo")
        ),
        "user_roles": _snapshot_queryset(
            UserRole.all_objects.order_by("id").values("id", "user_id", "role_id")
        ),
        "mobile_access_tokens": _snapshot_queryset(
            MobileAccessToken.all_objects.order_by("id").values("id", "user_id", "key")
        ),
        "password_reset_requests": _snapshot_queryset(
            PasswordResetRequest.all_objects.order_by("id").values("id", "user_id", "token")
        ),
    }


def validate_preserved_auth_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    pre_counts = dict(snapshot["counts"])
    post_counts = capture_preserved_auth_counts()
    count_delta = {
        table_name: post_counts.get(table_name, 0) - pre_counts.get(table_name, 0)
        for table_name in sorted(PRESERVED_ALL_TABLES)
    }

    for table_name in sorted(COUNT_STRICT_TABLES):
        if post_counts.get(table_name, 0) != pre_counts.get(table_name, 0):
            errors.append(
                f"Tabela preservada {table_name} mudou de {pre_counts.get(table_name, 0)} "
                f"para {post_counts.get(table_name, 0)}."
            )

    for table_name in sorted(COUNT_FLEX_TABLES):
        if post_counts.get(table_name, 0) < pre_counts.get(table_name, 0):
            errors.append(
                f"Tabela preservada {table_name} reduziu de {pre_counts.get(table_name, 0)} "
                f"para {post_counts.get(table_name, 0)}."
            )

    pre_users = {row["id"]: row for row in snapshot["users"]}
    current_users = {
        row["id"]: row
        for row in User.all_objects.filter(id__in=pre_users).values("id", "email", "password")
    }
    for user_id, row in sorted(pre_users.items()):
        current = current_users.get(user_id)
        if current is None:
            errors.append(f"Usuário preservado ausente id={user_id} email={row['email']}.")
            continue
        if current["email"] != row["email"]:
            errors.append(
                f"Usuário preservado id={user_id} mudou email de {row['email']} "
                f"para {current['email']}."
            )
        if current["password"] != row["password"]:
            errors.append(
                f"Usuário preservado id={user_id} email={row['email']} teve o hash alterado."
            )

    for key, model, fields, label in (
        ("roles", Role, ("id", "codigo"), "role"),
        ("user_roles", UserRole, ("id", "user_id", "role_id"), "user_role"),
        (
            "mobile_access_tokens",
            MobileAccessToken,
            ("id", "user_id", "key"),
            "mobile_access_token",
        ),
        (
            "password_reset_requests",
            PasswordResetRequest,
            ("id", "user_id", "token"),
            "password_reset_request",
        ),
    ):
        expected_rows = {
            row["id"]: row
            for row in snapshot[key]
        }
        current_rows = {
            row["id"]: row
            for row in model.all_objects.filter(id__in=expected_rows).values(*fields)
        }
        for row_id, expected in sorted(expected_rows.items()):
            current = current_rows.get(row_id)
            if current is None:
                errors.append(f"Registro preservado ausente {label} id={row_id}.")
                continue
            if any(current[field] != expected[field] for field in fields):
                errors.append(
                    f"Registro preservado alterado {label} id={row_id}: "
                    f"esperado={expected} atual={current}."
                )

    return {
        "ok": not errors,
        "pre_counts": pre_counts,
        "post_counts": post_counts,
        "count_delta": count_delta,
        "errors": errors,
    }


def select_restore_uploaded_by() -> User:
    preferred = (
        User.objects.filter(email__iexact="admin@abase.local", is_active=True)
        .order_by("id")
        .first()
    )
    if preferred is not None:
        return preferred

    for role_code in ("ADMIN", "COORDENADOR"):
        user = (
            User.objects.filter(is_active=True, roles__codigo=role_code)
            .distinct()
            .order_by("id")
            .first()
        )
        if user is not None:
            return user

    raise RuntimeError(
        "Nenhum usuário ativo elegível para uploaded_by foi encontrado."
    )


def stage_return_files(stage_dir: str | Path) -> dict[str, object]:
    target_dir = Path(stage_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)

    staged_rows: list[StagedReturnFile] = []
    for competencia in RETURN_MONTHS:
        arquivo = (
            ArquivoRetorno.objects.filter(competencia=competencia)
            .order_by("-created_at", "-id")
            .first()
        )
        if arquivo is None:
            raise RuntimeError(
                f"Nenhum ArquivoRetorno encontrado para a competência {competencia.isoformat()}."
            )
        if not arquivo.arquivo_url:
            raise RuntimeError(
                f"ArquivoRetorno id={arquivo.id} sem arquivo_url para a competência "
                f"{competencia.isoformat()}."
            )
        if not default_storage.exists(arquivo.arquivo_url):
            raise RuntimeError(
                f"Arquivo físico ausente no storage atual: {arquivo.arquivo_url}"
            )

        staged_name = (
            f"{competencia.isoformat()}__{arquivo.id}__{Path(arquivo.arquivo_nome).name}"
        )
        destination = target_dir / staged_name
        with default_storage.open(arquivo.arquivo_url, "rb") as source, destination.open(
            "wb"
        ) as output:
            shutil.copyfileobj(source, output)

        staged_rows.append(
            StagedReturnFile(
                competencia=competencia,
                source_id=arquivo.id,
                source_name=arquivo.arquivo_nome,
                source_storage_path=arquivo.arquivo_url,
                staged_path=staged_name,
            )
        )

    manifest = {
        "stage_dir": str(target_dir.resolve()),
        "files": [row.as_dict() for row in staged_rows],
    }
    manifest_path = target_dir / RETURN_STAGE_MANIFEST
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "stage_dir": str(target_dir.resolve()),
        "manifest_path": str(manifest_path.resolve()),
        "files": [row.as_dict() for row in staged_rows],
    }


def load_staged_return_manifest(stage_dir: str | Path) -> dict[str, object]:
    manifest_path = Path(stage_dir).expanduser() / RETURN_STAGE_MANIFEST
    if not manifest_path.exists():
        raise RuntimeError(f"Manifesto de staging não encontrado: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))
