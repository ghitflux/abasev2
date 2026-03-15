from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounts.legacy_agent_repair import LegacyAssociadoAgentRepairService


class Command(BaseCommand):
    help = (
        "Reconstrói o agente responsável real dos associados/contratos "
        "a partir das tabelas legadas users/roles/role_user/agente_cadastros."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Calcula o reparo sem persistir alterações.",
        )

    def handle(self, *args, **options):
        required_tables = {"users", "roles", "role_user", "agente_cadastros"}
        existing_tables = set(connection.introspection.table_names())
        missing_tables = sorted(required_tables - existing_tables)
        if missing_tables:
            raise CommandError(
                "Tabelas legadas ausentes para reconstrução: "
                + ", ".join(missing_tables)
            )

        legacy_agents = self._fetch_legacy_agents()
        legacy_cadastros = self._fetch_legacy_cadastros()
        if not legacy_agents:
            raise CommandError("Nenhum agente legado encontrado em users/role_user.")
        if not legacy_cadastros:
            raise CommandError("Nenhum cadastro legado encontrado em agente_cadastros.")

        service = LegacyAssociadoAgentRepairService()
        result = service.repair(
            legacy_agents=legacy_agents,
            legacy_cadastros=legacy_cadastros,
            dry_run=bool(options["dry_run"]),
        )

        mode = "DRY-RUN" if options["dry_run"] else "APLICADO"
        self.stdout.write(f"[{mode}] agentes sincronizados: criados={result.agent_users_created}, atualizados={result.agent_users_updated}, roles_adicionadas={result.agent_roles_added}")
        self.stdout.write(
            f"[{mode}] associados: matched={result.matched_associados}, "
            f"atualizados={result.associados_updated}, "
            f"sem_fonte_legada={result.associados_without_legacy_source}, "
            f"snapshot_sem_agente={result.associados_with_unresolved_agent}"
        )
        self.stdout.write(f"[{mode}] contratos atualizados: {result.contratos_updated}")

        if result.unresolved_agent_snapshots:
            self.stdout.write("[INFO] snapshots legados sem usuário AGENTE resolvido:")
            for snapshot, total in result.unresolved_agent_snapshots.most_common(20):
                self.stdout.write(f"  - {snapshot}: {total}")

    def _fetch_legacy_agents(self) -> list[dict[str, object]]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    u.id AS legacy_user_id,
                    u.email,
                    u.name,
                    u.password,
                    u.must_set_password,
                    u.profile_photo_path
                FROM users u
                INNER JOIN role_user ru ON ru.user_id = u.id
                INNER JOIN roles r ON r.id = ru.role_id
                WHERE LOWER(r.name) = 'agente'
                ORDER BY u.id ASC
                """
            )
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def _fetch_legacy_cadastros(self) -> list[dict[str, object]]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cpf_cnpj, agente_responsavel, agente_filial, created_at
                FROM agente_cadastros
                ORDER BY created_at ASC, id ASC
                """
            )
            rows = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
