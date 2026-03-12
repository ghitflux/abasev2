from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.management.seed_utils import ensure_access_users


class Command(BaseCommand):
    help = "Garante roles base e um usuario de desenvolvimento para cada nivel de acesso."

    @transaction.atomic
    def handle(self, *args, **options):
        specs = ensure_access_users()
        self.stdout.write(self.style.SUCCESS("Usuarios base de desenvolvimento garantidos:"))
        for role_code, spec in specs.items():
            self.stdout.write(f"- {role_code}: {spec.email}")
