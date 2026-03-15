from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.hashers import encode_legacy_bcrypt_hash, is_legacy_bcrypt_hash
from apps.accounts.models import Role, User, UserRole
from apps.associados.models import Associado
from apps.contratos.models import Contrato


def _clean_document(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _split_name(full_name: str | None) -> tuple[str, str]:
    normalized = " ".join((full_name or "").split()).strip()
    if not normalized:
        return "Usuario", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name[:150], last_name[:150]


def _normalize_lookup_value(raw: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", raw or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_only).strip().casefold()


def _lookup_aliases(raw: str | None) -> list[str]:
    normalized = _normalize_lookup_value(raw)
    if not normalized:
        return []

    aliases = [normalized]
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if compact and compact != normalized:
        aliases.append(compact)

    if "@" in normalized:
        local_part = normalized.split("@", 1)[0].strip()
        if local_part and local_part not in aliases:
            aliases.append(local_part)
        compact_local = re.sub(r"[^a-z0-9]+", "", local_part)
        if compact_local and compact_local not in aliases:
            aliases.append(compact_local)

    return aliases


def _first_lookup_token(raw: str | None) -> str:
    normalized = _normalize_lookup_value(raw)
    if not normalized:
        return ""
    return normalized.split(" ", 1)[0]


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


@dataclass
class LegacyAgentRepairResult:
    agent_users_created: int = 0
    agent_users_updated: int = 0
    agent_roles_added: int = 0
    matched_associados: int = 0
    associados_updated: int = 0
    contratos_updated: int = 0
    associados_without_legacy_source: int = 0
    associados_with_unresolved_agent: int = 0
    unresolved_agent_snapshots: Counter[str] = field(default_factory=Counter)


class LegacyAssociadoAgentRepairService:
    def __init__(self) -> None:
        self._agent_lookup: dict[str, int | None] = {}
        self._agent_first_token_lookup: dict[str, int | None] = {}

    def repair(
        self,
        *,
        legacy_agents: Iterable[dict[str, Any]],
        legacy_cadastros: Iterable[dict[str, Any]],
        dry_run: bool = False,
    ) -> LegacyAgentRepairResult:
        result = LegacyAgentRepairResult()
        legacy_agents = list(legacy_agents)
        legacy_cadastros = list(legacy_cadastros)

        with transaction.atomic():
            agent_role = self._ensure_agent_role()
            user_map = self._sync_agent_users(legacy_agents, agent_role, result)
            self._build_agent_lookup(user_map, legacy_agents)
            source_by_cpf = self._build_source_rows(legacy_cadastros)

            for associado in Associado.objects.all().order_by("id"):
                source_row = source_by_cpf.get(associado.cpf_cnpj)
                if source_row is None:
                    result.associados_without_legacy_source += 1
                    continue

                result.matched_associados += 1
                agente_pk = self._resolve_agent_user_id(
                    source_row.get("agente_responsavel"),
                    source_row.get("agente_filial"),
                )
                if not agente_pk:
                    snapshot_key = (
                        source_row.get("agente_responsavel")
                        or source_row.get("agente_filial")
                        or "<vazio>"
                    )
                    result.associados_with_unresolved_agent += 1
                    result.unresolved_agent_snapshots[str(snapshot_key)] += 1
                    continue

                update_fields: list[str] = []
                if associado.agente_responsavel_id != agente_pk:
                    associado.agente_responsavel_id = agente_pk
                    update_fields.append("agente_responsavel")

                agente_filial = (
                    str(source_row.get("agente_filial") or "").strip()
                    or str(source_row.get("agente_responsavel") or "").strip()
                )
                if agente_filial and associado.agente_filial != agente_filial[:160]:
                    associado.agente_filial = agente_filial[:160]
                    update_fields.append("agente_filial")

                if update_fields:
                    result.associados_updated += 1
                    if not dry_run:
                        associado.save(update_fields=[*update_fields, "updated_at"])

                contratos_qs = Contrato.objects.filter(associado_id=associado.pk).exclude(
                    agente_id=agente_pk
                )
                contratos_count = contratos_qs.count()
                if contratos_count:
                    result.contratos_updated += contratos_count
                    if not dry_run:
                        contratos_qs.update(agente_id=agente_pk)

            if dry_run:
                transaction.set_rollback(True)

        return result

    def _ensure_agent_role(self) -> Role:
        role, _ = Role.all_objects.get_or_create(
            codigo="AGENTE",
            defaults={
                "nome": "Agente",
                "descricao": "Agente comercial",
                "deleted_at": None,
            },
        )

        update_fields: list[str] = []
        if role.nome != "Agente":
            role.nome = "Agente"
            update_fields.append("nome")
        if role.deleted_at is not None:
            role.deleted_at = None
            update_fields.append("deleted_at")
        if update_fields:
            role.save(update_fields=[*update_fields, "updated_at"])

        return role

    def _sync_agent_users(
        self,
        legacy_agents: Iterable[dict[str, Any]],
        agent_role: Role,
        result: LegacyAgentRepairResult,
    ) -> dict[int, int]:
        user_map: dict[int, int] = {}

        for row in legacy_agents:
            legacy_user_id = int(row["legacy_user_id"])
            email = str(row.get("email") or "").strip()
            if not email:
                continue

            first_name, last_name = _split_name(str(row.get("name") or ""))
            raw_password = str(row.get("password") or "")
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
                    "must_set_password": bool(row.get("must_set_password")),
                    "profile_photo_path": str(row.get("profile_photo_path") or ""),
                    "is_active": True,
                    "is_staff": False,
                    "is_superuser": False,
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

            must_set_password = bool(row.get("must_set_password"))
            if user.must_set_password != must_set_password:
                user.must_set_password = must_set_password
                update_fields.append("must_set_password")

            profile_photo_path = str(row.get("profile_photo_path") or "")
            if user.profile_photo_path != profile_photo_path:
                user.profile_photo_path = profile_photo_path
                update_fields.append("profile_photo_path")

            if not user.is_active:
                user.is_active = True
                update_fields.append("is_active")
            if user.deleted_at is not None:
                user.deleted_at = None
                update_fields.append("deleted_at")

            should_update_password = (
                imported_password != user.password
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
                if created:
                    result.agent_users_created += 1
                else:
                    result.agent_users_updated += 1
            elif created:
                result.agent_users_created += 1

            assignment, assignment_created = UserRole.all_objects.get_or_create(
                user=user,
                role=agent_role,
                defaults={"deleted_at": None},
            )
            if assignment_created:
                result.agent_roles_added += 1
            elif assignment.deleted_at is not None:
                assignment.deleted_at = None
                assignment.save(update_fields=["deleted_at", "updated_at"])
                result.agent_roles_added += 1

            user_map[legacy_user_id] = user.pk

        return user_map

    def _build_agent_lookup(
        self,
        user_map: dict[int, int],
        legacy_agents: Iterable[dict[str, Any]],
    ) -> None:
        self._agent_lookup = {}
        self._agent_first_token_lookup = {}

        for row in legacy_agents:
            user_pk = user_map.get(int(row["legacy_user_id"]))
            if not user_pk:
                continue
            self._register_agent_aliases(
                user_pk,
                row.get("name"),
                row.get("email"),
            )

        for user in User.objects.filter(roles__codigo="AGENTE").distinct():
            self._register_agent_aliases(user.pk, user.full_name, user.email)

    def _register_agent_aliases(self, user_pk: int, *values: Any) -> None:
        for value in values:
            raw_value = str(value or "")
            for alias in _lookup_aliases(raw_value):
                self._register_lookup_alias(self._agent_lookup, alias, user_pk)

            first_token = _first_lookup_token(raw_value)
            if first_token:
                self._register_lookup_alias(
                    self._agent_first_token_lookup,
                    first_token,
                    user_pk,
                )

    @staticmethod
    def _register_lookup_alias(
        lookup: dict[str, int | None],
        alias: str,
        user_pk: int,
    ) -> None:
        existing = lookup.get(alias)
        if existing is None and alias not in lookup:
            lookup[alias] = user_pk
            return
        if existing != user_pk:
            lookup[alias] = None

    def _resolve_agent_user_id(self, *snapshots: Any) -> int | None:
        for snapshot in snapshots:
            for alias in _lookup_aliases(str(snapshot or "")):
                user_pk = self._agent_lookup.get(alias)
                if user_pk:
                    return user_pk

        for snapshot in snapshots:
            first_token = _first_lookup_token(str(snapshot or ""))
            if not first_token:
                continue
            user_pk = self._agent_first_token_lookup.get(first_token)
            if user_pk:
                return user_pk

        return None

    def _build_source_rows(
        self,
        legacy_cadastros: Iterable[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        source_by_cpf: dict[str, dict[str, Any]] = {}

        for row in legacy_cadastros:
            cpf_cnpj = _clean_document(str(row.get("cpf_cnpj") or ""))
            if not cpf_cnpj:
                continue

            current = source_by_cpf.get(cpf_cnpj)
            if current is None or self._is_earlier_row(row, current):
                source_by_cpf[cpf_cnpj] = {
                    "id": row.get("id"),
                    "cpf_cnpj": cpf_cnpj,
                    "agente_responsavel": str(row.get("agente_responsavel") or "").strip(),
                    "agente_filial": str(row.get("agente_filial") or "").strip(),
                    "created_at": row.get("created_at"),
                }

        return source_by_cpf

    def _is_earlier_row(
        self,
        candidate: dict[str, Any],
        current: dict[str, Any],
    ) -> bool:
        candidate_created_at = _coerce_datetime(candidate.get("created_at"))
        current_created_at = _coerce_datetime(current.get("created_at"))
        if candidate_created_at and current_created_at:
            if candidate_created_at != current_created_at:
                return candidate_created_at < current_created_at
        elif candidate_created_at and not current_created_at:
            return True
        elif not candidate_created_at and current_created_at:
            return False

        candidate_id = int(candidate.get("id") or 0)
        current_id = int(current.get("id") or 0)
        if candidate_id and current_id:
            return candidate_id < current_id
        return False
