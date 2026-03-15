"""
Management command to import data from the legacy MySQL dump (abase.sql).

Usage:
    python manage.py import_legacy_data --file /path/to/abase.sql
    python manage.py import_legacy_data --file /path/to/abase.sql --tables users roles
    python manage.py import_legacy_data --file /path/to/abase.sql --dry-run

Import order (respects FK dependencies):
  1. roles
  2. users
  3. role_user
  4. agente_margens
  5. agente_cadastros  (→ Associado + Endereco + DadosBancarios + Contrato)
  6. agente_cadastro_assumptions
  7. agente_doc_issues
  8. agente_doc_reuploads
  9. agente_margem_historicos
 10. agente_margem_snapshots
 11. despesas
 12. pagamentos_mensalidades
 13. tesouraria_confirmacoes
 14. tesouraria_pagamentos
 15. refinanciamentos
 16. refinanciamento_assumptions
 17. refinanciamento_ajustes_valor
 18. refinanciamento_comprovantes
 19. refinanciamento_itens
 20. refinanciamento_solicitacoes
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.backends import LEGACY_ROLE_CODE_MAP, ROLE_METADATA
from apps.accounts.hashers import encode_legacy_bcrypt_hash, is_legacy_bcrypt_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(value: str | None) -> datetime | None:
    """Parse MySQL timestamp string to aware datetime."""
    if not value or value == "NULL":
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value.strip("'"), fmt)
            return timezone.make_aware(dt)
        except ValueError:
            continue
    return None


def _date(value: str | None) -> date | None:
    if not value or value == "NULL":
        return None
    try:
        return datetime.strptime(value.strip("'"), "%Y-%m-%d").date()
    except ValueError:
        return None


def _dec(value: str | None) -> Decimal | None:
    if not value or value == "NULL":
        return None
    try:
        return Decimal(value.strip("'"))
    except InvalidOperation:
        return None


def _int(value: str | None) -> int | None:
    if not value or value == "NULL":
        return None
    try:
        return int(value.strip("'"))
    except ValueError:
        return None


def _str(value: str | None) -> str:
    if not value or value == "NULL":
        return ""
    return value.strip("'").replace("\\'", "'").replace("\\\\", "\\")


def _str_or_none(value: str | None) -> str | None:
    if not value or value == "NULL":
        return None
    return value.strip("'").replace("\\'", "'").replace("\\\\", "\\")


def _bool(value: str | None) -> bool:
    if not value or value == "NULL":
        return False
    return value.strip("'") in ("1", "true", "True")


def _json(value: str | None) -> Any:
    if not value or value == "NULL":
        return None
    import json
    raw = value.strip("'")
    candidates = [
        raw,
        raw.replace("\\'", "'").replace("\\\\", "\\"),
        raw.replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\/", "/")
        .replace("\\\\", "\\"),
    ]

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except Exception:
            continue

    try:
        return json.loads(bytes(raw, "utf-8").decode("unicode_escape"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# SQL parser
# ---------------------------------------------------------------------------

def extract_table_data(sql_text: str, table_name: str) -> list[dict]:
    """
    Extract all rows from INSERT statements for the given table name.
    Returns a list of dicts {column: raw_value_string}.
    """
    # Find INSERT INTO `table_name` (`col1`, ...) VALUES ...;
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(table_name) + r"`\s*"
        r"\(([^)]+)\)\s*VALUES\s*([\s\S]+?);",
        re.IGNORECASE,
    )
    rows = []
    for match in pattern.finditer(sql_text):
        cols_raw = match.group(1)
        values_raw = match.group(2)

        # Parse column names (strip backticks)
        cols = [c.strip().strip("`") for c in cols_raw.split(",")]

        for row_raw in _split_row_tuples(values_raw):
            raw_vals = _split_values(row_raw)
            if len(raw_vals) == len(cols):
                rows.append(dict(zip(cols, raw_vals)))
    return rows


def _split_row_tuples(values_str: str) -> list[str]:
    rows = []
    current = ""
    depth = 0
    in_quote = False
    previous = ""

    for c in values_str:
        if c == "'" and previous != "\\":
            in_quote = not in_quote

        if not in_quote and c == "(":
            depth += 1
            if depth == 1:
                previous = c
                continue

        if not in_quote and c == ")":
            depth -= 1
            if depth == 0:
                rows.append(current)
                current = ""
                previous = c
                continue

        if depth >= 1:
            current += c

        previous = c

    return rows


def _split_values(values_str: str) -> list[str]:
    """
    Split a comma-separated values string respecting quoted strings.
    e.g.: "1, 'hello', NULL, 'it\\'s fine', 2"
    """
    result = []
    current = ""
    in_quote = False
    i = 0
    while i < len(values_str):
        c = values_str[i]
        if c == "'" and not in_quote:
            in_quote = True
            current += c
        elif c == "'" and in_quote:
            # Check for escaped quote
            if i > 0 and values_str[i - 1] == "\\":
                current += c
            else:
                in_quote = False
                current += c
        elif c == "," and not in_quote:
            result.append(current.strip())
            current = ""
        else:
            current += c
        i += 1
    if current.strip():
        result.append(current.strip())
    return result


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

ALL_TABLES = [
    "roles",
    "users",
    "role_user",
    "agente_margens",
    "agente_cadastros",
    "agente_cadastro_assumptions",
    "agente_doc_issues",
    "agente_doc_reuploads",
    "agente_margem_historicos",
    "agente_margem_snapshots",
    "despesas",
    "pagamentos_mensalidades",
    "tesouraria_confirmacoes",
    "tesouraria_pagamentos",
    "refinanciamentos",
    "refinanciamento_assumptions",
    "refinanciamento_ajustes_valor",
    "refinanciamento_comprovantes",
    "refinanciamento_itens",
    "refinanciamento_solicitacoes",
]

_LOOKUP_MISSING = object()


class Command(BaseCommand):
    help = "Import legacy MySQL data from abase.sql dump"

    def _ensure_runtime_state(self):
        if not hasattr(self, "_user_map"):
            self._user_map: dict[int, int] = {}
        if not hasattr(self, "_role_map"):
            self._role_map: dict[int, int] = {}
        if not hasattr(self, "_cad_map"):
            self._cad_map: dict[int, int] = {}
        if not hasattr(self, "_refi_map"):
            self._refi_map: dict[int, int] = {}
        if not hasattr(self, "_pag_map"):
            self._pag_map: dict[int, int] = {}
        if not hasattr(self, "_tes_pag_map"):
            self._tes_pag_map: dict[int, int] = {}
        if not hasattr(self, "_doc_issue_map"):
            self._doc_issue_map: dict[int, int] = {}
        if not hasattr(self, "_esteira_map"):
            self._esteira_map: dict[int, int] = {}
        if not hasattr(self, "_legacy_user_rows"):
            self._legacy_user_rows: dict[int, dict[str, str]] = {}
        if not hasattr(self, "_agent_lookup"):
            self._agent_lookup: dict[str, int | None] = {}
        if not hasattr(self, "_agent_first_token_lookup"):
            self._agent_first_token_lookup: dict[str, int | None] = {}
        if not hasattr(self, "_agent_lookup_built"):
            self._agent_lookup_built = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Path to the abase.sql dump file",
        )
        parser.add_argument(
            "--tables",
            nargs="*",
            choices=ALL_TABLES,
            default=ALL_TABLES,
            help="Which tables to import (default: all)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and count rows without writing to the database",
        )

    def handle(self, *args, **options):
        self._ensure_runtime_state()
        sql_path = Path(options["file"])
        if not sql_path.exists():
            raise CommandError(f"File not found: {sql_path}")

        self.stdout.write(f"Reading {sql_path} …")
        sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(sql_text):,} characters"))

        tables_to_import = options["tables"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no data will be written"))

        # ID mapping dicts: legacy_id → Django object pk
        self._user_map: dict[int, int] = {}       # legacy user.id → User.pk
        self._role_map: dict[int, int] = {}       # legacy role.id → Role.pk
        self._cad_map: dict[int, int] = {}        # legacy agente_cadastro.id → Associado.pk
        self._refi_map: dict[int, int] = {}       # legacy refinanciamento.id → Refinanciamento.pk
        self._pag_map: dict[int, int] = {}        # legacy pagamento_mensalidade.id → PagamentoMensalidade.pk
        self._tes_pag_map: dict[int, int] = {}    # legacy tesouraria_pagamento.id → Pagamento.pk
        self._doc_issue_map: dict[int, int] = {}  # legacy agente_doc_issue.id → DocIssue.pk
        self._esteira_map: dict[int, int] = {}    # legacy cad_id → EsteiraItem.pk (from assumptions)
        self._legacy_user_rows: dict[int, dict[str, str]] = {}
        self._agent_lookup: dict[str, int | None] = {}
        self._agent_first_token_lookup: dict[str, int | None] = {}
        self._agent_lookup_built = False

        dispatch = {
            "roles": self._import_roles,
            "users": self._import_users,
            "role_user": self._import_role_user,
            "agente_margens": self._import_agente_margens,
            "agente_cadastros": self._import_agente_cadastros,
            "agente_cadastro_assumptions": self._import_cad_assumptions,
            "agente_doc_issues": self._import_doc_issues,
            "agente_doc_reuploads": self._import_doc_reuploads,
            "agente_margem_historicos": self._import_margem_historicos,
            "agente_margem_snapshots": self._import_margem_snapshots,
            "despesas": self._import_despesas,
            "pagamentos_mensalidades": self._import_pagamentos_mensalidades,
            "tesouraria_confirmacoes": self._import_tesouraria_confirmacoes,
            "tesouraria_pagamentos": self._import_tesouraria_pagamentos,
            "refinanciamentos": self._import_refinanciamentos,
            "refinanciamento_assumptions": self._import_refi_assumptions,
            "refinanciamento_ajustes_valor": self._import_ajustes_valor,
            "refinanciamento_comprovantes": self._import_refi_comprovantes,
            "refinanciamento_itens": self._import_refi_itens,
            "refinanciamento_solicitacoes": self._import_refi_solicitacoes,
        }

        # Always import in dependency order
        for table in ALL_TABLES:
            if table not in tables_to_import:
                continue
            fn = dispatch[table]
            rows = extract_table_data(sql_text, table)
            self.stdout.write(f"  {table}: {len(rows)} rows found")
            if not dry_run and rows:
                fn(rows)

        self.stdout.write(self.style.SUCCESS("Import complete."))

    # ------------------------------------------------------------------
    # Importers
    # ------------------------------------------------------------------

    def _import_roles(self, rows):
        self._ensure_runtime_state()
        from apps.accounts.models import Role
        created = 0
        for r in rows:
            name = _str(r.get("name"))
            legacy_role_id = _int(r.get("id"))
            codigo = _map_legacy_role_code(name)
            if legacy_role_id is None or not codigo:
                continue

            metadata = ROLE_METADATA.get(codigo, {"nome": name[:100], "descricao": ""})
            obj, new = Role.all_objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nome": metadata["nome"],
                    "descricao": metadata["descricao"],
                    "deleted_at": None,
                },
            )
            update_fields: list[str] = []
            if obj.nome != metadata["nome"]:
                obj.nome = metadata["nome"]
                update_fields.append("nome")
            if obj.descricao != metadata["descricao"]:
                obj.descricao = metadata["descricao"]
                update_fields.append("descricao")
            if obj.deleted_at is not None:
                obj.deleted_at = None
                update_fields.append("deleted_at")
            if update_fields:
                obj.save(update_fields=[*update_fields, "updated_at"])

            self._role_map[legacy_role_id] = obj.pk
            if new:
                created += 1
        self.stdout.write(f"    roles: {created} created")

    def _import_users(self, rows):
        self._ensure_runtime_state()
        from apps.accounts.models import User
        created = 0
        updated = 0
        for r in rows:
            legacy_user_id = _int(r.get("id"))
            name = _str(r.get("name"))
            parts = name.split(" ", 1)
            first = parts[0][:150]
            last = parts[1][:150] if len(parts) > 1 else ""
            email = _str(r.get("email"))
            if not email:
                continue
            raw_password = _str(r.get("password"))
            imported_password = (
                encode_legacy_bcrypt_hash(raw_password)
                if is_legacy_bcrypt_hash(raw_password)
                else make_password(None)
            )
            obj, new = User.all_objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "password": imported_password,
                    "must_set_password": _bool(r.get("must_set_password")),
                    "profile_photo_path": _str(r.get("profile_photo_path")),
                    "is_active": True,
                    "deleted_at": None,
                },
            )
            fields_to_update: list[str] = []
            if obj.first_name != first:
                obj.first_name = first
                fields_to_update.append("first_name")
            if obj.last_name != last:
                obj.last_name = last
                fields_to_update.append("last_name")

            must_set_password = _bool(r.get("must_set_password"))
            if obj.must_set_password != must_set_password:
                obj.must_set_password = must_set_password
                fields_to_update.append("must_set_password")

            profile_photo_path = _str(r.get("profile_photo_path"))
            if obj.profile_photo_path != profile_photo_path:
                obj.profile_photo_path = profile_photo_path
                fields_to_update.append("profile_photo_path")

            if not obj.is_active:
                obj.is_active = True
                fields_to_update.append("is_active")

            if obj.deleted_at is not None:
                obj.deleted_at = None
                fields_to_update.append("deleted_at")

            should_update_password = (
                imported_password != obj.password
                and (
                    not obj.has_usable_password()
                    or obj.password.startswith("legacy_bcrypt$")
                    or is_legacy_bcrypt_hash(obj.password)
                )
            )
            if should_update_password:
                obj.password = imported_password
                fields_to_update.append("password")

            if fields_to_update:
                obj.save(update_fields=[*fields_to_update, "updated_at"])
                if not new:
                    updated += 1
            if legacy_user_id is not None:
                self._user_map[legacy_user_id] = obj.pk
                self._legacy_user_rows[legacy_user_id] = {"name": name, "email": email}
            if new:
                created += 1

        self._agent_lookup_built = False
        self.stdout.write(f"    users: {created} created, {updated} updated")

    def _import_role_user(self, rows):
        self._ensure_runtime_state()
        from apps.accounts.models import User, Role, UserRole
        created = 0
        assignments: dict[int, set[int]] = defaultdict(set)
        for r in rows:
            user_pk = self._user_map.get(_int(r.get("user_id")))
            role_pk = self._role_map.get(_int(r.get("role_id")))
            if not user_pk or not role_pk:
                continue
            assignments[user_pk].add(role_pk)

        for user_pk, role_pks in assignments.items():
            user = User.all_objects.get(pk=user_pk)
            current_role_pks = set(
                UserRole.objects.filter(user_id=user_pk).values_list("role_id", flat=True)
            )
            roles = list(Role.objects.filter(pk__in=role_pks).order_by("id"))
            if current_role_pks != role_pks:
                user.roles.set(roles)
                created += max(len(role_pks - current_role_pks), 0)

            role_codes = {role.codigo for role in roles}
            is_admin = "ADMIN" in role_codes
            update_fields: list[str] = []
            if user.is_staff != is_admin:
                user.is_staff = is_admin
                update_fields.append("is_staff")
            if user.is_superuser != is_admin:
                user.is_superuser = is_admin
                update_fields.append("is_superuser")
            if update_fields:
                user.save(update_fields=[*update_fields, "updated_at"])

        self._agent_lookup_built = False
        self.stdout.write(f"    role_user: {created} created")

    def _import_agente_margens(self, rows):
        from apps.accounts.models import AgenteMargemConfig
        created = 0
        for r in rows:
            agente_pk = self._user_map.get(_int(r.get("agente_user_id")))
            if not agente_pk:
                continue
            updated_by_pk = self._user_map.get(_int(r.get("updated_by_user_id")))
            AgenteMargemConfig.objects.create(
                agente_id=agente_pk,
                percentual=_dec(r.get("percentual")) or Decimal("10"),
                vigente_desde=_ts(r.get("vigente_desde")) or timezone.now(),
                vigente_ate=_ts(r.get("vigente_ate")),
                updated_by_id=updated_by_pk,
                motivo=_str(r.get("motivo")),
            )
            created += 1
        self.stdout.write(f"    agente_margens: {created} created")

    def _import_agente_cadastros(self, rows):
        self._ensure_runtime_state()
        from apps.associados.models import Associado, Endereco, DadosBancarios, ContatoHistorico
        from apps.contratos.models import Contrato

        created = 0
        errors = 0
        self._build_agent_lookup()

        for r in rows:
            try:
                with transaction.atomic():
                    cpf_cnpj = re.sub(r"\D", "", _str(r.get("cpf_cnpj")))
                    full_name = _str(r.get("full_name"))

                    # Resolve agente FK using imported users and legacy aliases.
                    agente_pk = self._resolve_agent_user_id(
                        _str(r.get("agente_responsavel")),
                        _str(r.get("agente_filial")),
                    )

                    assoc, new = Associado.objects.get_or_create(
                        cpf_cnpj=cpf_cnpj,
                        defaults={
                            "nome_completo": full_name[:255],
                            "rg": _str(r.get("rg"))[:30],
                            "orgao_expedidor": _str(r.get("orgao_expedidor"))[:80],
                            "email": _str(r.get("email"))[:254],
                            "telefone": _str(r.get("cellphone"))[:30],
                            "data_nascimento": _date(r.get("birth_date")),
                            "profissao": _str(r.get("profession"))[:120],
                            "estado_civil": _map_estado_civil(_str(r.get("marital_status"))),
                            "orgao_publico": _str(r.get("orgao_publico"))[:160],
                            "matricula_orgao": _str(r.get("matricula_servidor_publico"))[:60],
                            "agente_responsavel_id": agente_pk,
                            "agente_filial": _str(r.get("agente_filial"))[:160],
                            "auxilio_taxa": _dec(r.get("auxilio_taxa")) or Decimal("10"),
                            "auxilio_status": _str(r.get("auxilio_status"))[:80],
                            "observacao": _str(r.get("observacoes")),
                            "status": Associado.Status.CADASTRADO,
                        },
                    )
                    self._cad_map[int(r["id"])] = assoc.pk

                    if new:
                        created += 1
                        # Endereco
                        if _str(r.get("cep")):
                            Endereco.objects.get_or_create(
                                associado=assoc,
                                defaults={
                                    "cep": _str(r.get("cep"))[:12],
                                    "logradouro": _str(r.get("address"))[:255],
                                    "numero": _str(r.get("address_number"))[:60],
                                    "complemento": _str(r.get("complement"))[:120],
                                    "bairro": _str(r.get("neighborhood"))[:120],
                                    "cidade": _str(r.get("city"))[:120],
                                    "uf": _str(r.get("uf"))[:2],
                                },
                            )
                        # DadosBancarios
                        if _str(r.get("bank_name")) or _str(r.get("bank_agency")):
                            DadosBancarios.objects.get_or_create(
                                associado=assoc,
                                defaults={
                                    "banco": _str(r.get("bank_name"))[:100],
                                    "agencia": _str(r.get("bank_agency"))[:20],
                                    "conta": _str(r.get("bank_account"))[:30],
                                    "tipo_conta": (_str(r.get("account_type")) or "corrente")[:20],
                                    "chave_pix": _str(r.get("pix_key"))[:120],
                                },
                            )
                        # ContatoHistorico
                        ContatoHistorico.objects.get_or_create(
                            associado=assoc,
                            defaults={
                                "celular": _str(r.get("cellphone"))[:20],
                                "email": _str(r.get("email"))[:254],
                                "orgao_publico": _str(r.get("orgao_publico"))[:150],
                                "situacao_servidor": _str(r.get("situacao_servidor"))[:80],
                                "matricula_servidor": _str(r.get("matricula_servidor_publico"))[:50],
                            },
                        )

                    codigo = _str(r.get("contrato_codigo_contrato"))
                    if codigo:
                        status_raw = _str(r.get("contrato_status_contrato"))
                        Contrato.objects.get_or_create(
                            codigo=codigo,
                            defaults={
                                "associado": assoc,
                                "agente_id": agente_pk,
                                "valor_bruto": _dec(r.get("calc_valor_bruto")) or Decimal("0"),
                                "valor_liquido": _dec(r.get("calc_liquido_cc")) or Decimal("0"),
                                "valor_mensalidade": _dec(r.get("contrato_mensalidade")) or Decimal("0"),
                                "prazo_meses": _int(r.get("contrato_prazo_meses")) or 3,
                                "taxa_antecipacao": _dec(r.get("contrato_taxa_antecipacao")) or Decimal("0"),
                                "margem_disponivel": _dec(r.get("contrato_margem_disponivel")) or Decimal("0"),
                                "valor_total_antecipacao": _dec(r.get("contrato_valor_antecipacao")) or Decimal("0"),
                                "doacao_associado": _dec(r.get("contrato_doacao_associado")) or Decimal("0"),
                                "status": _map_contrato_status(status_raw),
                                "data_aprovacao": _date(r.get("contrato_data_aprovacao")),
                                "data_primeira_mensalidade": _date(r.get("contrato_data_envio_primeira")),
                                "mes_averbacao": _date(r.get("contrato_mes_averbacao")),
                                "auxilio_liberado_em": _date(r.get("auxilio_data_envio")),
                            },
                        )
            except Exception as exc:
                errors += 1
                self.stderr.write(f"    skip cad id={r.get('id')}: {exc}")

        self.stdout.write(f"    agente_cadastros: {created} created, {errors} errors")

    def _build_agent_lookup(self):
        from apps.accounts.models import User

        if self._agent_lookup_built:
            return

        self._agent_lookup = {}
        self._agent_first_token_lookup = {}
        candidates = User.objects.filter(
            roles__codigo__in=("AGENTE", "ADMIN")
        ).distinct()

        for user in candidates:
            self._register_agent_aliases(user.pk, user.full_name, user.email)

        for legacy_user_id, legacy_row in self._legacy_user_rows.items():
            user_pk = self._user_map.get(legacy_user_id)
            if not user_pk:
                continue
            self._register_agent_aliases(
                user_pk,
                legacy_row.get("name", ""),
                legacy_row.get("email", ""),
            )

        self._agent_lookup_built = True

    def _register_agent_aliases(self, user_pk: int, *values: str):
        for value in values:
            for alias in _lookup_aliases(value):
                self._register_lookup_alias(self._agent_lookup, alias, user_pk)

            first_token = _first_lookup_token(value)
            if first_token:
                self._register_lookup_alias(
                    self._agent_first_token_lookup,
                    first_token,
                    user_pk,
                )

    def _register_lookup_alias(
        self,
        lookup: dict[str, int | None],
        alias: str,
        user_pk: int,
    ):
        existing = lookup.get(alias, _LOOKUP_MISSING)
        if existing is _LOOKUP_MISSING:
            lookup[alias] = user_pk
            return
        if existing != user_pk:
            lookup[alias] = None

    def _resolve_agent_user_id(self, *snapshots: str) -> int | None:
        for snapshot in snapshots:
            for alias in _lookup_aliases(snapshot):
                user_pk = self._agent_lookup.get(alias, _LOOKUP_MISSING)
                if user_pk not in (_LOOKUP_MISSING, None):
                    return user_pk

        for snapshot in snapshots:
            first_token = _first_lookup_token(snapshot)
            if not first_token:
                continue
            user_pk = self._agent_first_token_lookup.get(first_token, _LOOKUP_MISSING)
            if user_pk not in (_LOOKUP_MISSING, None):
                return user_pk

        return None

    def _import_cad_assumptions(self, rows):
        from apps.esteira.models import EsteiraItem

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            if not cad_pk:
                continue
            analista_pk = self._user_map.get(_int(r.get("analista_id")))
            status_raw = _str(r.get("status"))
            situacao = (
                EsteiraItem.Situacao.EM_ANDAMENTO
                if status_raw == "assumido"
                else EsteiraItem.Situacao.AGUARDANDO
            )
            obj, new = EsteiraItem.objects.get_or_create(
                associado_id=cad_pk,
                defaults={
                    "etapa_atual": EsteiraItem.Etapa.ANALISE,
                    "status": situacao,
                    "analista_responsavel_id": analista_pk,
                    "assumido_em": _ts(r.get("assumido_em")),
                    "heartbeat_at": _ts(r.get("heartbeat_at")),
                },
            )
            self._esteira_map[_int(r.get("agente_cadastro_id"))] = obj.pk
            if new:
                created += 1
        self.stdout.write(f"    agente_cadastro_assumptions: {created} created")

    def _import_doc_issues(self, rows):
        from apps.esteira.models import DocIssue

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            analista_pk = self._user_map.get(_int(r.get("analista_id")))
            if not cad_pk or not analista_pk:
                continue
            status_raw = _str(r.get("status"))
            obj = DocIssue.objects.create(
                associado_id=cad_pk,
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                contrato_codigo=_str(r.get("contrato_codigo_contrato")),
                analista_id=analista_pk,
                status=status_raw if status_raw in ("incomplete", "resolved") else "incomplete",
                mensagem=_str(r.get("mensagem")),
                documents_snapshot_json=_json(r.get("documents_snapshot_json")),
                agent_uploads_json=_json(r.get("agent_uploads_json")),
            )
            self._doc_issue_map[int(r["id"])] = obj.pk
            created += 1
        self.stdout.write(f"    agente_doc_issues: {created} created")

    def _import_doc_reuploads(self, rows):
        from apps.esteira.models import DocReupload

        created = 0
        for r in rows:
            issue_pk = self._doc_issue_map.get(_int(r.get("agente_doc_issue_id")))
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            if not issue_pk or not cad_pk:
                continue
            uploaded_by_pk = self._user_map.get(_int(r.get("uploaded_by_user_id")))
            status_raw = _str(r.get("status"))
            DocReupload.objects.create(
                doc_issue_id=issue_pk,
                associado_id=cad_pk,
                uploaded_by_id=uploaded_by_pk,
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                contrato_codigo=_str(r.get("contrato_codigo_contrato")),
                file_original_name=_str(r.get("file_original_name")),
                file_stored_name=_str(r.get("file_stored_name")),
                file_relative_path=_str(r.get("file_relative_path")),
                file_mime=_str(r.get("file_mime")),
                file_size_bytes=_int(r.get("file_size_bytes")),
                status=status_raw if status_raw in ("received", "accepted", "rejected") else "received",
                uploaded_at=_ts(r.get("uploaded_at")),
                notes=_str(r.get("notes")),
                extras=_json(r.get("extras")),
            )
            created += 1
        self.stdout.write(f"    agente_doc_reuploads: {created} created")

    def _import_margem_historicos(self, rows):
        from apps.accounts.models import AgenteMargemHistorico

        created = 0
        for r in rows:
            agente_pk = self._user_map.get(_int(r.get("agente_user_id")))
            if not agente_pk:
                continue
            changed_by_pk = self._user_map.get(_int(r.get("changed_by_user_id")))
            AgenteMargemHistorico.objects.create(
                agente_id=agente_pk,
                percentual_anterior=_dec(r.get("percentual_anterior")),
                percentual_novo=_dec(r.get("percentual_novo")),
                changed_by_id=changed_by_pk,
                motivo=_str(r.get("motivo")),
                meta=_json(r.get("meta")),
            )
            created += 1
        self.stdout.write(f"    agente_margem_historicos: {created} created")

    def _import_margem_snapshots(self, rows):
        from apps.accounts.models import AgenteMargemSnapshot

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            agente_pk = self._user_map.get(_int(r.get("agente_user_id")))
            if not cad_pk or not agente_pk:
                continue
            changed_by_pk = self._user_map.get(_int(r.get("changed_by_user_id")))
            AgenteMargemSnapshot.objects.create(
                cadastro_id=cad_pk,
                agente_id=agente_pk,
                percentual_anterior=_dec(r.get("percentual_anterior")),
                percentual_novo=_dec(r.get("percentual_novo")),
                mensalidade=_dec(r.get("mensalidade")),
                margem_disponivel=_dec(r.get("margem_disponivel")),
                auxilio_valor_anterior=_dec(r.get("auxilio_valor_anterior")),
                auxilio_valor_novo=_dec(r.get("auxilio_valor_novo")),
                changed_by_id=changed_by_pk,
                motivo=_str(r.get("motivo")),
            )
            created += 1
        self.stdout.write(f"    agente_margem_snapshots: {created} created")

    def _import_despesas(self, rows):
        from apps.financeiro.models import Despesa

        created = 0
        for r in rows:
            user_pk = self._user_map.get(_int(r.get("user_id")))
            status_raw = _str(r.get("status"))
            tipo_raw = _str(r.get("tipo"))
            rec_raw = _str(r.get("recorrencia"))
            Despesa.objects.create(
                user_id=user_pk,
                categoria=_str(r.get("categoria")),
                descricao=_str(r.get("descricao")),
                valor=_dec(r.get("valor")) or Decimal("0"),
                data_despesa=_date(r.get("data_despesa")) or date.today(),
                data_pagamento=_date(r.get("data_pagamento")),
                status=status_raw if status_raw in ("pendente", "pago") else "pendente",
                tipo=tipo_raw if tipo_raw in ("fixa", "variavel") else "",
                recorrencia=rec_raw if rec_raw in ("nenhuma", "mensal", "trimestral", "anual") else "nenhuma",
                recorrencia_ativa=_bool(r.get("recorrencia_ativa")),
                observacoes=_str(r.get("observacoes")),
                comprovantes_json=_json(r.get("comprovantes_json")),
            )
            created += 1
        self.stdout.write(f"    despesas: {created} created")

    def _import_pagamentos_mensalidades(self, rows):
        from apps.importacao.models import PagamentoMensalidade

        created = 0
        for r in rows:
            created_by_pk = self._user_map.get(_int(r.get("created_by_user_id")))
            assoc_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            manual_by_pk = self._user_map.get(_int(r.get("manual_by_user_id")))
            manual_status = _str(r.get("manual_status"))
            obj = PagamentoMensalidade.objects.create(
                created_by_id=created_by_pk,
                import_uuid=_str(r.get("import_uuid")),
                referencia_month=_date(r.get("referencia_month")) or date.today(),
                status_code=_str(r.get("status_code")),
                matricula=_str(r.get("matricula")),
                orgao_pagto=_str(r.get("orgao_pagto")),
                nome_relatorio=_str(r.get("nome_relatorio")),
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                associado_id=assoc_pk,
                valor=_dec(r.get("valor")),
                esperado_manual=_dec(r.get("esperado_manual")),
                recebido_manual=_dec(r.get("recebido_manual")),
                manual_status=manual_status if manual_status in ("pendente", "pago", "cancelado") else None,
                agente_refi_solicitado=_bool(r.get("agente_refi_solicitado")),
                manual_paid_at=_ts(r.get("manual_paid_at")),
                manual_forma_pagamento=_str(r.get("manual_forma_pagamento")),
                manual_comprovante_path=_str(r.get("manual_comprovante_path")),
                manual_by_id=manual_by_pk,
                source_file_path=_str(r.get("source_file_path")),
            )
            self._pag_map[int(r["id"])] = obj.pk
            created += 1
        self.stdout.write(f"    pagamentos_mensalidades: {created} created")

    def _import_tesouraria_confirmacoes(self, rows):
        from apps.tesouraria.models import Confirmacao
        from apps.contratos.models import Contrato

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("cad_id")))
            if not cad_pk:
                continue
            # Find the contrato for this associado
            contrato = Contrato.objects.filter(associado_id=cad_pk).first()
            if not contrato:
                continue
            link = _str(r.get("link_chamada"))
            # Ligação
            if _bool(r.get("ligacao_recebida")):
                Confirmacao.objects.get_or_create(
                    contrato=contrato,
                    tipo=Confirmacao.Tipo.LIGACAO,
                    defaults={
                        "competencia": date.today(),
                        "status": Confirmacao.Status.CONFIRMADO,
                        "data_confirmacao": _ts(r.get("ligacao_recebida_at")),
                        "link_chamada": link,
                    },
                )
                created += 1
            # Averbação
            if _bool(r.get("averbacao_confirmada")):
                Confirmacao.objects.get_or_create(
                    contrato=contrato,
                    tipo=Confirmacao.Tipo.AVERBACAO,
                    defaults={
                        "competencia": date.today(),
                        "status": Confirmacao.Status.CONFIRMADO,
                        "data_confirmacao": _ts(r.get("averbacao_confirmada_at")),
                        "link_chamada": link,
                    },
                )
                created += 1
        self.stdout.write(f"    tesouraria_confirmacoes: {created} created")

    def _import_tesouraria_pagamentos(self, rows):
        from apps.tesouraria.models import Pagamento

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            if not cad_pk:
                continue
            created_by_pk = self._user_map.get(_int(r.get("created_by_user_id")))
            status_raw = _str(r.get("status"))
            obj = Pagamento.objects.create(
                cadastro_id=cad_pk,
                created_by_id=created_by_pk,
                contrato_codigo=_str(r.get("contrato_codigo_contrato")),
                contrato_valor_antecipacao=_dec(r.get("contrato_valor_antecipacao")),
                contrato_margem_disponivel=_dec(r.get("contrato_margem_disponivel")),
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                full_name=_str(r.get("full_name")),
                agente_responsavel=_str(r.get("agente_responsavel")),
                status=status_raw if status_raw in ("pendente", "pago", "cancelado") else "pago",
                valor_pago=_dec(r.get("valor_pago")),
                paid_at=_ts(r.get("paid_at")),
                forma_pagamento=_str(r.get("forma_pagamento")),
                comprovante_path=_str(r.get("comprovante_path")),
                comprovante_associado_path=_str(r.get("comprovante_associado_path")),
                comprovante_agente_path=_str(r.get("comprovante_agente_path")),
                notes=_str(r.get("notes")),
            )
            self._tes_pag_map[int(r["id"])] = obj.pk
            created += 1
        self.stdout.write(f"    tesouraria_pagamentos: {created} created")

    def _import_refinanciamentos(self, rows):
        from apps.refinanciamento.models import Refinanciamento
        from apps.associados.models import Associado

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            cpf_cnpj = re.sub(r"\D", "", _str(r.get("cpf_cnpj")))
            if not cad_pk and cpf_cnpj:
                assoc = Associado.objects.filter(cpf_cnpj=cpf_cnpj).first()
                cad_pk = assoc.pk if assoc else None
            if not cad_pk:
                continue
            created_by_pk = self._user_map.get(_int(r.get("created_by_user_id")))
            status_raw = _str(r.get("status"))
            obj = Refinanciamento.objects.create(
                associado_id=cad_pk,
                solicitado_por_id=created_by_pk,
                competencia_solicitada=_date(r.get("ref1")) or date.today(),
                status=_map_refi_status(status_raw),
                mode=_str(r.get("mode")) or "manual",
                cycle_key=_str(r.get("cycle_key")),
                ref1=_date(r.get("ref1")),
                ref2=_date(r.get("ref2")),
                ref3=_date(r.get("ref3")),
                cpf_cnpj_snapshot=cpf_cnpj,
                nome_snapshot=_str(r.get("nome_snapshot")),
                agente_snapshot=_str(r.get("agente_snapshot")),
                filial_snapshot=_str(r.get("filial_snapshot")),
                contrato_codigo_origem=_str(r.get("contrato_codigo_origem")),
                contrato_codigo_novo=_str(r.get("contrato_codigo_novo")),
                executado_em=_ts(r.get("executed_at")),
            )
            self._refi_map[int(r["id"])] = obj.pk
            created += 1
        self.stdout.write(f"    refinanciamentos: {created} created")

    def _import_refi_assumptions(self, rows):
        from apps.refinanciamento.models import Assumption

        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("agente_cadastro_id")))
            if not cad_pk:
                continue
            sol_pk = self._user_map.get(_int(r.get("solicitado_por_user_id")))
            analista_pk = self._user_map.get(_int(r.get("analista_id")))
            status_raw = _str(r.get("status"))
            Assumption.objects.create(
                cadastro_id=cad_pk,
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                request_key=_str(r.get("request_key")),
                refs_json=_json(r.get("refs_json")),
                solicitado_por_id=sol_pk,
                analista_id=analista_pk,
                status=status_raw if status_raw in ("liberado", "assumido", "finalizado") else "liberado",
                solicitado_em=_ts(r.get("solicitado_em")),
                liberado_em=_ts(r.get("liberado_em")),
                assumido_em=_ts(r.get("assumido_em")),
                finalizado_em=_ts(r.get("finalizado_em")),
                heartbeat_at=_ts(r.get("heartbeat_at")),
            )
            created += 1
        self.stdout.write(f"    refinanciamento_assumptions: {created} created")

    def _import_ajustes_valor(self, rows):
        from apps.refinanciamento.models import AjusteValor

        created = 0
        for r in rows:
            refi_pk = self._refi_map.get(_int(r.get("refinanciamento_id")))
            if not refi_pk:
                continue
            created_by_pk = self._user_map.get(_int(r.get("created_by_user_id")))
            AjusteValor.objects.create(
                refinanciamento_id=refi_pk,
                cpf_cnpj=_str(r.get("cpf_cnpj")),
                origem=_str(r.get("origem")),
                fonte_base=_str(r.get("fonte_base")),
                valor_base=_dec(r.get("valor_base")),
                valor_antigo=_dec(r.get("valor_antigo")),
                valor_novo=_dec(r.get("valor_novo")) or Decimal("0"),
                tp_margem=_dec(r.get("tp_margem")),
                ac_margem=_dec(r.get("ac_margem")),
                a2_margem=_dec(r.get("a2_margem")),
                created_by_id=created_by_pk,
                ip=_str(r.get("ip")),
                user_agent=_str(r.get("user_agent")),
                motivo=_str(r.get("motivo")),
                meta=_json(r.get("meta")),
            )
            created += 1
        self.stdout.write(f"    refinanciamento_ajustes_valor: {created} created")

    def _import_refi_comprovantes(self, rows):
        from apps.refinanciamento.models import Comprovante

        created = 0
        for r in rows:
            refi_pk = self._refi_map.get(_int(r.get("refinanciamento_id")))
            if not refi_pk:
                continue
            uploaded_by_pk = self._user_map.get(_int(r.get("uploaded_by_user_id")))
            kind = _str(r.get("kind"))
            # Map kind to tipo choices
            tipo = "outro"
            if "pix" in kind.lower():
                tipo = "pix"
            elif "contrato" in kind.lower():
                tipo = "contrato"
            Comprovante.objects.create(
                refinanciamento_id=refi_pk,
                tipo=tipo,
                arquivo=_str(r.get("path")),
                nome_original=_str(r.get("original_name")),
                agente_snapshot=_str(r.get("agente_snapshot")),
                filial_snapshot=_str(r.get("filial_snapshot")),
                enviado_por_id=uploaded_by_pk,
            )
            created += 1
        self.stdout.write(f"    refinanciamento_comprovantes: {created} created")

    def _import_refi_itens(self, rows):
        from apps.refinanciamento.models import Item

        created = 0
        for r in rows:
            refi_pk = self._refi_map.get(_int(r.get("refinanciamento_id")))
            if not refi_pk:
                continue
            pag_pk = self._pag_map.get(_int(r.get("pagamento_mensalidade_id")))
            tes_pk = self._tes_pag_map.get(_int(r.get("tesouraria_pagamento_id")))
            Item.objects.create(
                refinanciamento_id=refi_pk,
                pagamento_mensalidade_id=pag_pk,
                tesouraria_pagamento_id=tes_pk,
                referencia_month=_date(r.get("referencia_month")) or date.today(),
                status_code=_str(r.get("status_code")),
                valor=_dec(r.get("valor")),
                import_uuid=_str(r.get("import_uuid")),
                source_file_path=_str(r.get("source_file_path")),
            )
            created += 1
        self.stdout.write(f"    refinanciamento_itens: {created} created")

    def _import_refi_solicitacoes(self, rows):
        """
        refinanciamento_solicitacoes → atualiza campos no Refinanciamento existente
        ou cria novo se não há correspondência por cycle_key.
        """
        from apps.refinanciamento.models import Refinanciamento
        from apps.associados.models import Associado

        updated = 0
        created = 0
        for r in rows:
            cad_pk = self._cad_map.get(_int(r.get("cadastro_id")))
            cpf_cnpj = re.sub(r"\D", "", _str(r.get("cpf_cnpj")))
            if not cad_pk and cpf_cnpj:
                assoc = Associado.objects.filter(cpf_cnpj=cpf_cnpj).first()
                cad_pk = assoc.pk if assoc else None
            if not cad_pk:
                continue

            refi_legacy_id = _int(r.get("refinanciamento_id"))
            refi_pk = self._refi_map.get(refi_legacy_id) if refi_legacy_id else None
            reviewed_by_pk = self._user_map.get(_int(r.get("reviewed_by_user_id")))
            created_by_pk = self._user_map.get(_int(r.get("created_by_user_id")))
            status_raw = _str(r.get("status"))

            if refi_pk:
                # Update existing refinanciamento with solicitacao data
                Refinanciamento.objects.filter(pk=refi_pk).update(
                    cycle_key=_str(r.get("cycle_key")),
                    parcelas_ok=_int(r.get("parcelas_ok")) or 0,
                    parcelas_json=_json(r.get("parcelas_json")),
                    analista_note=_str(r.get("analista_note")),
                    coordenador_note=_str(r.get("coordenador_note")),
                    reviewed_by_id=reviewed_by_pk,
                    reviewed_at=_ts(r.get("reviewed_at")),
                    termo_antecipacao_path=_str(r.get("termo_antecipacao_path")),
                    termo_antecipacao_original_name=_str(r.get("termo_antecipacao_original_name")),
                    termo_antecipacao_mime=_str(r.get("termo_antecipacao_mime")),
                    termo_antecipacao_size_bytes=_int(r.get("termo_antecipacao_size_bytes")),
                    termo_antecipacao_uploaded_at=_ts(r.get("termo_antecipacao_uploaded_at")),
                )
                updated += 1
            else:
                # Create new from solicitacao
                obj = Refinanciamento.objects.create(
                    associado_id=cad_pk,
                    solicitado_por_id=created_by_pk,
                    competencia_solicitada=_date(r.get("ref1")) or date.today(),
                    status=_map_refi_status(status_raw),
                    cycle_key=_str(r.get("cycle_key")),
                    ref1=_date(r.get("ref1")),
                    ref2=_date(r.get("ref2")),
                    ref3=_date(r.get("ref3")),
                    cpf_cnpj_snapshot=cpf_cnpj,
                    nome_snapshot=_str(r.get("nome_snapshot")),
                    agente_snapshot=_str(r.get("agente_snapshot")),
                    filial_snapshot=_str(r.get("filial_snapshot")),
                    parcelas_ok=_int(r.get("parcelas_ok")) or 0,
                    parcelas_json=_json(r.get("parcelas_json")),
                    analista_note=_str(r.get("analista_note")),
                    coordenador_note=_str(r.get("coordenador_note")),
                    reviewed_by_id=reviewed_by_pk,
                    reviewed_at=_ts(r.get("reviewed_at")),
                    termo_antecipacao_path=_str(r.get("termo_antecipacao_path")),
                    termo_antecipacao_original_name=_str(r.get("termo_antecipacao_original_name")),
                    termo_antecipacao_mime=_str(r.get("termo_antecipacao_mime")),
                    termo_antecipacao_size_bytes=_int(r.get("termo_antecipacao_size_bytes")),
                    termo_antecipacao_uploaded_at=_ts(r.get("termo_antecipacao_uploaded_at")),
                )
                created += 1
        self.stdout.write(
            f"    refinanciamento_solicitacoes: {created} created, {updated} updated"
        )


# ---------------------------------------------------------------------------
# Value mappers
# ---------------------------------------------------------------------------

def _normalize_lookup_value(raw: str) -> str:
    normalized = unicodedata.normalize("NFKD", raw or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    collapsed = re.sub(r"\s+", " ", ascii_only).strip().casefold()
    return collapsed


def _lookup_aliases(raw: str) -> list[str]:
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


def _first_lookup_token(raw: str) -> str:
    normalized = _normalize_lookup_value(raw)
    if not normalized:
        return ""
    return normalized.split(" ", 1)[0]


def _map_legacy_role_code(raw: str) -> str | None:
    normalized = _normalize_lookup_value(raw)
    return LEGACY_ROLE_CODE_MAP.get(normalized)


def _map_estado_civil(raw: str) -> str:
    mapping = {
        "casado": "casado",
        "casado(a)": "casado",
        "solteiro": "solteiro",
        "solteiro(a)": "solteiro",
        "divorciado": "divorciado",
        "divorciado(a)": "divorciado",
        "viúvo": "viuvo",
        "viuvo": "viuvo",
        "viúvo(a)": "viuvo",
        "viuvo(a)": "viuvo",
        "união estável": "uniao_estavel",
    }
    return mapping.get(raw.lower(), "")


def _map_contrato_status(raw: str) -> str:
    mapping = {
        "concluído": "ativo",
        "concluido": "ativo",
        "ativo": "ativo",
        "pendente": "em_analise",
        "cancelado": "cancelado",
        "encerrado": "encerrado",
    }
    return mapping.get(raw.lower(), "em_analise")


def _map_refi_status(raw: str) -> str:
    mapping = {
        "done": "concluido",
        "pending": "pendente_apto",
        "in_progress": "em_analise",
        "suspended": "bloqueado",
        "approved": "aprovado",
        "rejected": "rejeitado",
        "cancelled": "revertido",
    }
    return mapping.get(raw.lower(), "pendente_apto")
