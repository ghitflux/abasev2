from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.legacy_restore_runtime import select_restore_uploaded_by
from apps.importacao.maristela_reconciliation import (
    MaristelaReconciliationRunner,
    _default_report_dir,
    write_maristela_reports,
)


class Command(BaseCommand):
    help = (
        "Concilia os associados com base na planilha manual da Maristela, "
        "corrigindo parcelas, pagamentos mensais e status global."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Caminho da planilha XLSX com a conciliação manual.",
        )
        parser.add_argument(
            "--report-dir",
            help="Diretório opcional para gravar os relatórios JSON/CSV.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analisa divergências sem persistir alterações.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica as correções definitivamente.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        execute = bool(options["execute"])
        if dry_run == execute:
            raise CommandError("Informe exatamente um modo: use `--dry-run` ou `--execute`.")

        file_path = Path(options["file"]).expanduser()
        if not file_path.exists():
            raise CommandError(f"Planilha não encontrada: {file_path}")

        report_dir = Path(options["report_dir"]).expanduser() if options.get("report_dir") else _default_report_dir()
        actor = select_restore_uploaded_by() if execute else None

        runner = MaristelaReconciliationRunner(
            file_path=file_path,
            execute=execute,
            actor=actor,
        )
        payload = runner.run()
        written_paths = write_maristela_reports(payload, report_dir)

        summary = payload["summary"]
        self.summary = {
            "mode": summary["mode"],
            "file": summary["file"],
            "report_dir": str(report_dir),
            "rows_loaded": summary["rows_loaded"],
            "matched_associados": summary["matched_associados"],
            "planilha_sem_match": summary["planilha_sem_match"],
            "excecoes_conciliacao": summary["excecoes_conciliacao"],
            "correcoes_planejadas": summary["correcoes_planejadas"],
            "affected_contracts": summary["affected_contracts"],
            "post_process": summary.get("post_process") or {},
        }

        self.stdout.write(f"modo: {summary['mode']}")
        self.stdout.write(f"planilha: {file_path.resolve()}")
        self.stdout.write(f"report_dir: {report_dir.resolve()}")
        self.stdout.write(f"rows_loaded: {summary['rows_loaded']}")
        self.stdout.write(f"matched_associados: {summary['matched_associados']}")
        self.stdout.write(f"planilha_sem_match: {summary['planilha_sem_match']}")
        self.stdout.write(f"excecoes_conciliacao: {summary['excecoes_conciliacao']}")
        self.stdout.write(f"correcoes_planejadas: {summary['correcoes_planejadas']}")
        self.stdout.write(f"affected_contracts: {summary['affected_contracts']}")
        if summary.get("post_process"):
            self.stdout.write(f"post_process: {summary['post_process']}")
        for name, path in sorted(written_paths.items()):
            self.stdout.write(f"{name}: {path}")
