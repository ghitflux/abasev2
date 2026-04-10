from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.refinanciamento.treasury_value_repair import (
    repair_treasury_refinanciamento_values,
)


class Command(BaseCommand):
    help = (
        "Corrige valor liberado e repasse do agente em refinanciamentos exibidos "
        "na tesouraria, reaproveitando os valores do contrato operacional."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção no banco. Sem a flag roda em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            default="",
            help="Caminho opcional para salvar o relatório em JSON.",
        )

    def handle(self, *args, **options):
        payload = repair_treasury_refinanciamento_values(
            apply=bool(options["apply"])
        )
        report_json = str(options.get("report_json") or "").strip()
        if report_json:
            path = Path(report_json)
        else:
            suffix = "apply" if options["apply"] else "dry_run"
            path = (
                Path(settings.BASE_DIR)
                / "media"
                / "relatorios"
                / f"repair_tesouraria_refinanciamento_valores_{suffix}.json"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS(json.dumps(payload, ensure_ascii=False)))
        self.stdout.write(f"Relatório salvo em {path}")
