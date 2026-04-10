from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.contratos.incomplete_cycle_one_repair import repair_incomplete_cycle_one


class Command(BaseCommand):
    help = "Corrige contratos com ciclo 1 concluído/renovado sem 3 parcelas de ciclo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica as correções no banco. Sem esta flag executa apenas dry-run.",
        )
        parser.add_argument(
            "--report-json",
            type=str,
            help="Salva o relatório JSON no caminho informado.",
        )

    def handle(self, *args, **options):
        payload = repair_incomplete_cycle_one(apply=bool(options["apply"]))
        report_path = options.get("report_json")
        if report_path:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        self.stdout.write(json.dumps(payload, ensure_ascii=False, default=str))
