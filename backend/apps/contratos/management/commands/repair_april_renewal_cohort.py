from __future__ import annotations

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.contratos.april_renewal_cohort_repair import (
    run_april_renewal_cohort_repair,
    write_april_repair_report,
)


class Command(BaseCommand):
    help = (
        "Corrige o lote oficial da renovação parcial de abril, "
        "reconstrói contratos quebrados do recorte e resincroniza aptos a renovar."
    )

    def add_arguments(self, parser):
        parser.add_argument("--csv-path", required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--report-json")
        parser.add_argument(
            "--floor-reference",
            default="2025-10",
            help="Competência mínima no formato YYYY-MM. Padrão: 2025-10.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"CSV não encontrado: {csv_path}")

        try:
            year_str, month_str = str(options["floor_reference"]).split("-", 1)
            floor_reference = date(int(year_str), int(month_str), 1)
        except (TypeError, ValueError) as exc:
            raise CommandError("floor-reference inválido. Use YYYY-MM.") from exc

        payload = run_april_renewal_cohort_repair(
            csv_path=csv_path,
            execute=bool(options["apply"]),
            floor_reference=floor_reference,
        )
        target = write_april_repair_report(payload, options.get("report_json"))

        self.stdout.write(f"mode: {payload['mode']}")
        for key, value in payload["summary"].items():
            self.stdout.write(f"{key}: {value}")
        self.stdout.write(f"report: {target}")
