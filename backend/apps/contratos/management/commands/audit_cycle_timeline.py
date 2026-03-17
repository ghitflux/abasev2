from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.contratos.cycle_audit import (
    build_cycle_timeline_audit,
    write_cycle_timeline_audit_csv,
    write_cycle_timeline_audit_json,
)


class Command(BaseCommand):
    help = "Audita a timeline de ciclos e renovações com base em tesouraria e refinanciamento."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--json",
            dest="json_path",
            help="Arquivo JSON de saída.",
        )
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Arquivo CSV de saída.",
        )

    def handle(self, *args, **options):
        report = build_cycle_timeline_audit(cpf=options.get("cpf"))
        summary = report["summary"]
        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Auditados "
                    f"{summary['total_associados']} associado(s); "
                    f"{summary['associados_com_achados']} com achados."
                )
            )
        )
        for classification, count in sorted(summary["classifications"].items()):
            self.stdout.write(f"- {classification}: {count}")

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        json_path = options.get("json_path") or (
            Path("backend/media/relatorios/legacy_import")
            / f"audit_cycle_timeline_{timestamp}.json"
        )
        json_target = write_cycle_timeline_audit_json(report, json_path)
        self.stdout.write(f"JSON: {json_target}")

        csv_path = options.get("csv_path")
        if csv_path:
            csv_target = write_cycle_timeline_audit_csv(report, csv_path)
            self.stdout.write(f"CSV: {csv_target}")
