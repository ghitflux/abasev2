from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.small_value_agent_repair import (
    assign_default_agent_to_small_value_associados,
)


class Command(BaseCommand):
    help = (
        "Atribui o agente padrão ABASE aos associados de 30/50 reais "
        "que ainda não possuem agente responsável."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a atualização no banco. Sem esta flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        report = assign_default_agent_to_small_value_associados(
            apply=bool(options["apply"])
        )
        if report["default_agent_id"] is None:
            raise CommandError("Agente padrão ABASE não encontrado.")

        self.stdout.write(f"modo: {report['mode']}")
        self.stdout.write(f"default_agent_id: {report['default_agent_id']}")
        self.stdout.write(f"default_agent_email: {report['default_agent_email']}")
        self.stdout.write(f"associado_total: {report['associado_total']}")

        for associado_id, cpf in zip(report["associado_ids"], report["cpfs"], strict=False):
            self.stdout.write(f"{associado_id}: {cpf}")
