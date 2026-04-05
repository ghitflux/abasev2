from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.legacy_restore_runtime import select_restore_uploaded_by
from apps.importacao.maristela_cycle_membership import (
    MaristelaCycleMembershipRepairRunner,
)


class Command(BaseCommand):
    help = (
        "Saneia março/2026 e novembro/2025 na materialização dos ciclos após o rebuild."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--march-ref", default="2026-03")
        parser.add_argument("--november-ref", default="2025-11")
        parser.add_argument(
            "--sheet-file",
            default="anexos_legado/Conciliacao/planilha_manual_maristela.xlsx",
        )
        parser.add_argument("--cpf")
        parser.add_argument("--associado-id", type=int)
        parser.add_argument("--contrato-id", type=int)
        parser.add_argument("--report-json")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        execute = bool(options["execute"])
        if dry_run == execute:
            raise CommandError("Informe exatamente um modo: `--dry-run` ou `--execute`.")

        actor = None
        if execute:
            try:
                actor = select_restore_uploaded_by()
            except RuntimeError:
                actor = None

        runner = MaristelaCycleMembershipRepairRunner(
            execute=execute,
            march_ref=options["march_ref"],
            november_ref=options["november_ref"],
            sheet_file=options["sheet_file"],
            actor=actor,
            cpf=options.get("cpf"),
            associado_id=options.get("associado_id"),
            contrato_id=options.get("contrato_id"),
        )
        payload = runner.run()

        if report_json := options.get("report_json"):
            target = Path(report_json).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Relatório: {target}")

        summary = payload["summary"]
        self.summary = summary
        self.stdout.write(f"modo: {summary['mode']}")
        self.stdout.write(f"associados_auditados: {summary['associados_auditados']}")
        self.stdout.write(f"repairable: {summary['repairable']}")
        self.stdout.write(f"repaired: {summary['repaired']}")
        self.stdout.write(f"manual_review: {summary['manual_review']}")
