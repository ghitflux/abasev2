"""
Management command to create Django User accounts for existing Associado records
and link them via the Associado.user OneToOneField.

The CPF is used to derive the user's email: {cpf_digits}@app.abase.local
This internal email is never exposed to the associate; login is done via CPF.

Usage:
    python manage.py create_associado_users
    python manage.py create_associado_users --dry-run
    python manage.py create_associado_users --cpf 12345678900
    python manage.py create_associado_users --overwrite

Options:
    --dry-run    Show what would be done without making any changes
    --cpf        Process only a specific CPF (digits only)
    --overwrite  Re-link associados that already have a user (skipped by default)
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User, UserRole
from apps.associados.models import Associado


def _only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _cpf_email(cpf: str) -> str:
    """Generate the internal email for a CPF-based login."""
    return f"{_only_digits(cpf)}@app.abase.local"


def _split_name(nome: str) -> tuple[str, str]:
    """Split full name into first and last."""
    parts = (nome or "").strip().split()
    if not parts:
        return ("", "")
    first = parts[0]
    last = " ".join(parts[1:]) if len(parts) > 1 else ""
    return first, last


class Command(BaseCommand):
    help = "Create Django User accounts for existing Associado records (mobile login)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without persisting any changes.",
        )
        parser.add_argument(
            "--cpf",
            type=str,
            help="Process only the associado with this CPF (digits only).",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Re-process associados that already have a linked user.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        target_cpf: str | None = _only_digits(options.get("cpf") or "")
        overwrite: bool = options["overwrite"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — nenhuma alteração será salva.\n"))

        # Fetch ASSOCIADO role
        try:
            role_associado = Role.objects.get(codigo="ASSOCIADO")
        except Role.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(
                    "Role 'ASSOCIADO' não encontrada. "
                    "Execute primeiro: python manage.py shell → Role.objects.create(codigo='ASSOCIADO', nome='Associado')"
                )
            )
            return

        # Build queryset
        qs = Associado.objects.select_related("user").order_by("id")
        if target_cpf:
            qs = qs.filter(cpf_cnpj=target_cpf)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"Nenhum associado com CPF {target_cpf}."))
                return

        if not overwrite:
            qs = qs.filter(user__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhum associado para processar."))
            return

        self.stdout.write(f"Associados a processar: {total}\n")

        created = 0
        skipped = 0
        errors = 0

        for associado in qs.iterator():
            cpf = _only_digits(associado.cpf_cnpj or "")
            if not cpf:
                self.stdout.write(
                    self.style.WARNING(f"  SKIP  id={associado.id} — CPF vazio")
                )
                skipped += 1
                continue

            email = _cpf_email(cpf)
            first_name, last_name = _split_name(associado.nome_completo or "")

            if dry_run:
                self.stdout.write(
                    f"  [DRY]  id={associado.id} cpf={cpf} → email={email} nome='{associado.nome_completo}'"
                )
                created += 1
                continue

            try:
                with transaction.atomic():
                    # Create or retrieve the User
                    user, user_created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            "first_name": first_name,
                            "last_name": last_name,
                            "is_active": True,
                            "must_set_password": False,
                        },
                    )

                    if user_created:
                        # Default password = CPF digits; associate must change via app later
                        user.set_password(cpf)
                        user.save(update_fields=["password"])

                    # Assign ASSOCIADO role if not already assigned
                    UserRole.objects.get_or_create(
                        user=user,
                        role=role_associado,
                        defaults={"assigned_at": timezone.now()},
                    )

                    # Link Associado → User
                    if associado.user_id != user.pk:
                        associado.user = user
                        associado.save(update_fields=["user", "updated_at"])

                action = "CRIADO" if user_created else "VINCULADO"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {action}  id={associado.id} cpf={cpf} → {email}"
                    )
                )
                created += 1

            except Exception as exc:
                self.stderr.write(
                    self.style.ERROR(
                        f"  ERRO   id={associado.id} cpf={cpf}: {exc}"
                    )
                )
                errors += 1

        self.stdout.write("")
        self.stdout.write(f"Processados : {created}")
        self.stdout.write(f"Ignorados   : {skipped}")
        self.stdout.write(f"Erros       : {errors}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN finalizado — nada foi salvo."))
        else:
            self.stdout.write(self.style.SUCCESS("\nConcluído."))
