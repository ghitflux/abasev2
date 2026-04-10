from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.november_2025_outside_cycle_repair import (
    repair_november_2025_outside_cycles,
)


class Command(BaseCommand):
    help = (
        "Saneia novembro/2025 para permanecer sempre fora dos ciclos, "
        "limpando conciliações manuais inválidas e rebuildando os contratos afetados."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--report-json")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        apply = bool(options["apply"])
        if dry_run == apply:
            raise CommandError("Informe exatamente um modo: `--dry-run` ou `--apply`.")

        payload = repair_november_2025_outside_cycles(apply=apply)

        if report_json := options.get("report_json"):
            target = Path(report_json).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Relatório: {target}")

        for key, value in payload.items():
            self.stdout.write(f"{key}: {value}")
