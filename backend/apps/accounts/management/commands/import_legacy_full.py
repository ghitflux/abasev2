from __future__ import annotations

import io
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, OutputWrapper
from django.db import transaction

from apps.accounts.legacy_import_audit import (
    SUCCESS_STATUS,
    backfill_all_business_references,
    build_legacy_verification_report,
    default_legacy_report_path,
    save_legacy_report,
)


class Command(BaseCommand):
    help = (
        "Orquestra a importação completa do legado ABASE para o schema "
        "canônico Django, com relatório final obrigatório."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Caminho para o dump SQL legado.",
        )
        parser.add_argument(
            "--report-file",
            help="Caminho opcional para salvar o relatório JSON final.",
        )
        mode_group = parser.add_mutually_exclusive_group(required=True)
        mode_group.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa toda a importação em transação revertida ao final.",
        )
        mode_group.add_argument(
            "--execute",
            action="store_true",
            help="Executa e persiste a importação completa.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        dry_run = bool(options["dry_run"])
        report_path = (
            Path(options["report_file"]).expanduser()
            if options.get("report_file")
            else default_legacy_report_path("import_legacy_full")
        )

        self.stdout.write(
            f"Modo={'DRY-RUN' if dry_run else 'EXECUTE'} arquivo={dump_path}"
        )

        phase_summaries: dict[str, dict] = {}
        with transaction.atomic():
            from apps.accounts.management.commands.import_legacy_associados_current_flow import (
                Command as ImportAssociadosCurrentFlowCommand,
            )
            from apps.accounts.management.commands.import_legacy_complements import (
                COMPLEMENT_TABLES,
                Command as ImportLegacyComplementsCommand,
            )
            from apps.accounts.management.commands.import_legacy_operational_users import (
                Command as ImportOperationalUsersCommand,
            )
            from apps.associados.management.commands.create_associado_users import (
                Command as CreateAssociadoUsersCommand,
            )

            phase_summaries["fase_1_usuarios_operacionais"] = self._run_subcommand(
                ImportOperationalUsersCommand,
                file=str(dump_path),
                dry_run=False,
            )
            self._emit_phase_summary(
                "Fase 1",
                phase_summaries["fase_1_usuarios_operacionais"],
            )

            phase_summaries["fase_2_agente_cadastros"] = self._run_subcommand(
                ImportAssociadosCurrentFlowCommand,
                file=str(dump_path),
                limit=None,
                dry_run=False,
                fallback_agent_email=None,
            )
            self._emit_phase_summary(
                "Fase 2",
                phase_summaries["fase_2_agente_cadastros"],
            )

            phase_summaries["fase_3_associado_users"] = self._run_subcommand(
                CreateAssociadoUsersCommand,
                dry_run=False,
                cpf=None,
                overwrite=False,
            )
            self._emit_phase_summary(
                "Fase 3",
                phase_summaries["fase_3_associado_users"],
            )

            phase_summaries["fase_4_complementos"] = self._run_subcommand(
                ImportLegacyComplementsCommand,
                file=str(dump_path),
                tables=COMPLEMENT_TABLES,
                dry_run=False,
            )
            self._emit_phase_summary(
                "Fase 4",
                phase_summaries["fase_4_complementos"],
            )

            business_reference_backfill = backfill_all_business_references()
            phase_summaries["fase_5_data_referencia_negocio"] = business_reference_backfill
            self._emit_phase_summary("Fase 5", business_reference_backfill)

            report = build_legacy_verification_report(
                dump_path,
                dry_run=dry_run,
                phases=phase_summaries,
                business_reference_backfill=business_reference_backfill,
            )
            report["report_file"] = str(report_path)
            save_legacy_report(report, report_path)

            self.stdout.write(f"status={report['status']}")
            self.stdout.write(f"report_file={report_path}")
            self.stdout.write(json.dumps(report["summary"], ensure_ascii=False, indent=2))

            if report["status"] != SUCCESS_STATUS:
                raise CommandError(
                    f"Importação divergente. Consulte o relatório em {report_path}"
                )

            if dry_run:
                transaction.set_rollback(True)

        self.report = report

    def _run_subcommand(self, command_class, **kwargs):
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        command = command_class()
        command.stdout = OutputWrapper(stdout_buffer)
        command.stderr = OutputWrapper(stderr_buffer)
        try:
            command.handle(**kwargs)
        except Exception as exc:
            captured_stdout = stdout_buffer.getvalue().strip()
            captured_stderr = stderr_buffer.getvalue().strip()
            details = []
            if captured_stdout:
                details.append(f"stdout={captured_stdout}")
            if captured_stderr:
                details.append(f"stderr={captured_stderr}")
            suffix = f" ({'; '.join(details)})" if details else ""
            raise CommandError(f"Falha em {command_class.__name__}: {exc}{suffix}") from exc
        return getattr(command, "summary", None)

    def _emit_phase_summary(self, phase_label: str, summary):
        if not isinstance(summary, dict):
            self.stdout.write(f"{phase_label}: concluída")
            return
        compact = ", ".join(f"{key}={value}" for key, value in summary.items())
        self.stdout.write(f"{phase_label}: {compact}")
