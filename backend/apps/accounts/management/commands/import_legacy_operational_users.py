from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.backends import LEGACY_ROLE_CODE_MAP, ROLE_METADATA
from apps.accounts.hashers import encode_legacy_bcrypt_hash, is_legacy_bcrypt_hash
from apps.accounts.legacy_agent_repair import LegacyAssociadoAgentRepairService
from apps.accounts.management.commands.import_legacy_data import (
    _int,
    _str,
    _ts,
    extract_table_data,
)
from apps.accounts.models import Role, User


DEFAULT_SQL_FILE = Path("/tmp/abasedb1203.sql")
OPERATIONAL_ROLE_NAMES = {"admin", "agente", "analista", "coordenador", "tesoureiro"}


def _split_name(full_name: str) -> tuple[str, str]:
    normalized = " ".join(full_name.split()).strip()
    if not normalized:
        return "Usuario", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name[:150], last_name[:150]


class Command(BaseCommand):
    help = (
        "Importa apenas os usuários operacionais legados (admin/agente/analista/"
        "coordenador/tesoureiro) e realinha o agente responsável dos associados."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(DEFAULT_SQL_FILE),
            help="Caminho para o dump SQL legado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa sem persistir alterações.",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"]).expanduser()
        if not file_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {file_path}")

        sql_text = file_path.read_text(encoding="utf-8", errors="replace")
        roles_rows = extract_table_data(sql_text, "roles")
        users_rows = extract_table_data(sql_text, "users")
        role_user_rows = extract_table_data(sql_text, "role_user")
        cadastro_rows = extract_table_data(sql_text, "agente_cadastros")

        if not roles_rows or not users_rows or not role_user_rows:
            raise CommandError("Dump legado sem dados suficientes de roles/users/role_user.")

        legacy_role_names = {
            _int(row.get("id")): _str(row.get("name")).strip().lower()
            for row in roles_rows
            if _int(row.get("id")) is not None
        }
        legacy_users = {
            _int(row.get("id")): row
            for row in users_rows
            if _int(row.get("id")) is not None and _str(row.get("email"))
        }

        selected_user_roles: dict[int, set[str]] = defaultdict(set)
        for row in role_user_rows:
            legacy_user_id = _int(row.get("user_id"))
            legacy_role_id = _int(row.get("role_id"))
            if legacy_user_id is None or legacy_role_id is None:
                continue

            legacy_role_name = legacy_role_names.get(legacy_role_id, "")
            if legacy_role_name not in OPERATIONAL_ROLE_NAMES:
                continue

            role_code = LEGACY_ROLE_CODE_MAP.get(legacy_role_name)
            if role_code:
                selected_user_roles[legacy_user_id].add(role_code)

        if not selected_user_roles:
            raise CommandError("Nenhum usuário operacional encontrado no dump legado.")

        summary = {
            "usuarios_operacionais": len(selected_user_roles),
            "users_created": 0,
            "users_updated": 0,
            "roles_created": 0,
            "agent_users_created": 0,
            "agent_users_updated": 0,
            "agent_roles_added": 0,
            "matched_associados": 0,
            "associados_updated": 0,
            "contratos_updated": 0,
            "associados_without_legacy_source": 0,
            "associados_with_unresolved_agent": 0,
        }

        context = transaction.atomic()
        with context:
            roles_by_code = self._ensure_roles(summary)
            user_map, legacy_agent_rows = self._sync_operational_users(
                selected_user_roles=selected_user_roles,
                legacy_users=legacy_users,
                roles_by_code=roles_by_code,
                summary=summary,
            )

            service = LegacyAssociadoAgentRepairService()
            repair_result = service.repair(
                legacy_agents=legacy_agent_rows,
                legacy_cadastros=[
                    {
                        "id": _int(row.get("id")),
                        "cpf_cnpj": _str(row.get("cpf_cnpj")),
                        "agente_responsavel": _str(row.get("agente_responsavel")),
                        "agente_filial": _str(row.get("agente_filial")),
                        "created_at": _str(row.get("created_at")),
                    }
                    for row in cadastro_rows
                ],
                dry_run=bool(options["dry_run"]),
            )

            summary["agent_users_created"] = repair_result.agent_users_created
            summary["agent_users_updated"] = repair_result.agent_users_updated
            summary["agent_roles_added"] = repair_result.agent_roles_added
            summary["matched_associados"] = repair_result.matched_associados
            summary["associados_updated"] = repair_result.associados_updated
            summary["contratos_updated"] = repair_result.contratos_updated
            summary["associados_without_legacy_source"] = (
                repair_result.associados_without_legacy_source
            )
            summary["associados_with_unresolved_agent"] = (
                repair_result.associados_with_unresolved_agent
            )

            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if options["dry_run"] else "APLICADO"
        self.stdout.write(
            f"[{mode}] usuarios_operacionais={len(selected_user_roles)} "
            f"users_created={summary['users_created']} "
            f"users_updated={summary['users_updated']} "
            f"roles_created={summary['roles_created']}"
        )
        self.stdout.write(
            f"[{mode}] associados matched={summary['matched_associados']} "
            f"associados_updated={summary['associados_updated']} "
            f"contratos_updated={summary['contratos_updated']} "
            f"sem_fonte_legada={summary['associados_without_legacy_source']} "
            f"snapshot_sem_agente={summary['associados_with_unresolved_agent']}"
        )
        self.summary = summary

    def _ensure_roles(self, summary: dict[str, int]) -> dict[str, Role]:
        roles_by_code: dict[str, Role] = {}
        for code in LEGACY_ROLE_CODE_MAP.values():
            metadata = ROLE_METADATA[code]
            role, created = Role.all_objects.get_or_create(
                codigo=code,
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
            roles_by_code[code] = role
            summary["roles_created"] += int(created)
        return roles_by_code

    def _sync_operational_users(
        self,
        *,
        selected_user_roles: dict[int, set[str]],
        legacy_users: dict[int, dict],
        roles_by_code: dict[str, Role],
        summary: dict[str, int],
    ) -> tuple[dict[int, int], list[dict[str, object]]]:
        user_map: dict[int, int] = {}
        legacy_agent_rows: list[dict[str, object]] = []

        for legacy_user_id, role_codes in sorted(selected_user_roles.items()):
            legacy_row = legacy_users.get(legacy_user_id)
            if not legacy_row:
                continue

            email = _str(legacy_row.get("email"))
            if not email:
                continue

            first_name, last_name = _split_name(_str(legacy_row.get("name")))
            raw_password = _str(legacy_row.get("password"))
            imported_password = (
                encode_legacy_bcrypt_hash(raw_password)
                if is_legacy_bcrypt_hash(raw_password)
                else make_password(None)
            )

            user, created = User.all_objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "password": imported_password,
                    "must_set_password": bool(_int(legacy_row.get("must_set_password"))),
                    "profile_photo_path": _str(legacy_row.get("profile_photo_path")),
                    "is_active": True,
                    "is_staff": "ADMIN" in role_codes,
                    "is_superuser": "ADMIN" in role_codes,
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

            must_set_password = bool(_int(legacy_row.get("must_set_password")))
            if user.must_set_password != must_set_password:
                user.must_set_password = must_set_password
                update_fields.append("must_set_password")

            profile_photo_path = _str(legacy_row.get("profile_photo_path"))
            if user.profile_photo_path != profile_photo_path:
                user.profile_photo_path = profile_photo_path
                update_fields.append("profile_photo_path")

            if not user.is_active:
                user.is_active = True
                update_fields.append("is_active")
            if user.is_staff != ("ADMIN" in role_codes):
                user.is_staff = "ADMIN" in role_codes
                update_fields.append("is_staff")
            if user.is_superuser != ("ADMIN" in role_codes):
                user.is_superuser = "ADMIN" in role_codes
                update_fields.append("is_superuser")
            if user.deleted_at is not None:
                user.deleted_at = None
                update_fields.append("deleted_at")

            should_update_password = (
                isinstance(imported_password, str)
                and imported_password != user.password
                and (
                    not user.has_usable_password()
                    or user.password.startswith("legacy_bcrypt$")
                    or is_legacy_bcrypt_hash(user.password)
                )
            )
            if should_update_password:
                user.password = imported_password
                update_fields.append("password")

            if update_fields:
                user.save(update_fields=[*update_fields, "updated_at"])
                if not created:
                    summary["users_updated"] += 1

            user.roles.set([roles_by_code[code] for code in sorted(role_codes)])

            legacy_created_at = _ts(legacy_row.get("created_at"))
            legacy_updated_at = _ts(legacy_row.get("updated_at"))
            updates = {}
            if legacy_created_at:
                updates["created_at"] = legacy_created_at
            if legacy_updated_at:
                updates["updated_at"] = legacy_updated_at
            elif legacy_created_at:
                updates["updated_at"] = legacy_created_at
            if updates:
                User.all_objects.filter(pk=user.pk).update(**updates)

            user_map[legacy_user_id] = user.pk
            summary["users_created"] += int(created)

            if "AGENTE" in role_codes:
                legacy_agent_rows.append(
                    {
                        "legacy_user_id": legacy_user_id,
                        "email": email,
                        "name": _str(legacy_row.get("name")),
                        "password": raw_password,
                        "must_set_password": bool(_int(legacy_row.get("must_set_password"))),
                        "profile_photo_path": _str(legacy_row.get("profile_photo_path")),
                    }
                )

        return user_map, legacy_agent_rows
