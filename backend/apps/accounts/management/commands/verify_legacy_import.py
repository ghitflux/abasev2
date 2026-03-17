from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.legacy_import_audit import (
    SUCCESS_STATUS,
    build_legacy_verification_report,
    default_legacy_report_path,
    save_legacy_report,
)


class Command(BaseCommand):
    help = (
        "Verifica a importação do dump legado contra o schema canônico e gera "
        "um relatório JSON auditável."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Caminho para o dump SQL legado.",
        )
        parser.add_argument(
            "--report-file",
            help="Caminho opcional para salvar o relatório JSON.",
        )
        parser.add_argument(
            "--no-fail",
            action="store_true",
            help="Não retorna erro mesmo se houver divergências.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        report_path = (
            Path(options["report_file"]).expanduser()
            if options.get("report_file")
            else default_legacy_report_path("verify_legacy_import")
        )
        report = build_legacy_verification_report(dump_path)
        report["report_file"] = str(report_path)
        save_legacy_report(report, report_path)

        self.stdout.write(f"status={report['status']}")
        self.stdout.write(f"report_file={report_path}")
        self.stdout.write(json.dumps(report["summary"], ensure_ascii=False, indent=2))

        if report["mismatches"]:
            self.stdout.write("mismatches:")
            for mismatch in report["mismatches"]:
                self.stdout.write(f"  - {mismatch}")

        if report["status"] != SUCCESS_STATUS and not options["no_fail"]:
            raise CommandError(
                f"Verificação falhou. Consulte o relatório em {report_path}"
            )

        self.report = report
