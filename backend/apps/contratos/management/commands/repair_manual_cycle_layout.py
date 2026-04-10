from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.contratos.manual_cycle_layout_repair import repair_manual_cycle_layouts


class Command(BaseCommand):
    help = (
        "Normaliza contratos com layout manual, removendo do ciclo parcelas "
        "não descontadas/quitadas fora do ciclo e religando documentos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--contrato-id", type=int)
        parser.add_argument("--cpf")

    def handle(self, *args, **options):
        report = repair_manual_cycle_layouts(
            apply=bool(options["apply"]),
            contrato_id=options.get("contrato_id"),
            cpf=options.get("cpf"),
        )
        self.stdout.write(f"mode: {'apply' if options['apply'] else 'dry-run'}")
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")
