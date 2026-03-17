from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.duplicate_billing import repair_duplicate_billing_months


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
    help = "Repara competências duplicadas, mescla contratos operacionais duplicados e reconstrói a linha canônica."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica o reparo. Sem esta flag, roda em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        payload = repair_duplicate_billing_months(
            cpf_cnpj=options.get("cpf"),
            execute=bool(options["execute"]),
        )
        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("repair_duplicate_billing_months")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        summary = payload["summary"]
        mode = summary["mode"]
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Reparo concluído em modo {mode}: "
                    f"{summary['groups']} grupo(s), "
                    f"{summary['merged_contracts']} contrato(s) mesclado(s), "
                    f"{summary['remaining_duplicate_keys']} competência(s) duplicada(s) restante(s)."
                )
            )
        )
        self.stdout.write(f"Relatório: {target}")
