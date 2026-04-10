from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.small_value_return_renewal_repair import (
    repair_small_value_return_renewal_block,
)


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


class Command(BaseCommand):
    help = (
        "Impede que contratos 30/50 importados do arquivo retorno permaneçam em "
        "apto_a_renovar e reconstrói seus ciclos/refinanciamentos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a reconstrução no banco. Sem a flag, roda em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        payload = repair_small_value_return_renewal_block(
            apply=bool(options.get("apply"))
        )
        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("repair_small_value_return_renewal_block")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Correção concluída em modo {payload['mode']} para "
                f"{payload['candidate_contract_total']} contrato(s) 30/50 importado(s)."
            )
        )
        self.stdout.write(f"Relatório: {target}")
