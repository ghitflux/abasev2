from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounts.legacy_restore_runtime import PRESERVED_ALL_TABLES, tables_to_truncate


class Command(BaseCommand):
    help = (
        "Limpa todas as tabelas gerenciadas de domínio preservando autenticação, "
        "papéis e metadados necessários de auth."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe as tabelas que seriam truncadas sem aplicar alterações.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Executa a limpeza definitivamente.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        execute = bool(options["execute"])
        if dry_run == execute:
            raise CommandError("Informe exatamente um modo: use `--dry-run` ou `--execute`.")

        existing_tables = set(connection.introspection.table_names())
        target_tables = [
            table_name for table_name in tables_to_truncate() if table_name in existing_tables
        ]
        preserved_tables = sorted(table_name for table_name in PRESERVED_ALL_TABLES if table_name in existing_tables)

        counts: dict[str, int] = {}
        with connection.cursor() as cursor:
            for table_name in target_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {connection.ops.quote_name(table_name)}")
                row = cursor.fetchone()
                counts[table_name] = int(row[0]) if row else 0

        mode = "DRY-RUN" if dry_run else "EXECUTE"
        self.stdout.write(f"[{mode}] Tabelas preservadas: {', '.join(preserved_tables)}")
        self.stdout.write(f"[{mode}] Tabelas a truncar: {', '.join(target_tables)}")
        for table_name in target_tables:
            self.stdout.write(f"[{mode}] {table_name}: {counts[table_name]} registros")

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Nenhuma alteração foi aplicada."))
            return

        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            try:
                for table_name in target_tables:
                    cursor.execute(f"TRUNCATE TABLE {connection.ops.quote_name(table_name)}")
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

        self.stdout.write(
            self.style.SUCCESS(
                f"[EXECUTE] Limpeza concluída. {len(target_tables)} tabelas truncadas."
            )
        )
