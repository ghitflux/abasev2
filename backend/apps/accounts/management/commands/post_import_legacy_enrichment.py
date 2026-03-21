from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, OutputWrapper

from apps.accounts.management.commands.sync_legacy_media_assets import (
    Command as SyncLegacyMediaAssetsCommand,
)
from apps.contratos.management.commands.audit_cycle_timeline import (
    Command as AuditCycleTimelineCommand,
)
from apps.contratos.management.commands.rebuild_cycle_state import (
    Command as RebuildCycleStateCommand,
)
from apps.contratos.management.commands.sync_legacy_renewals import (
    Command as SyncLegacyRenewalsCommand,
)
from apps.importacao.management.commands.sync_legacy_pagamento_manual_fields import (
    Command as SyncLegacyPagamentoManualFieldsCommand,
)
from apps.tesouraria.management.commands.sync_legacy_initial_payments import (
    Command as SyncLegacyInitialPaymentsCommand,
)
from core.legacy_dump import default_legacy_dump_path


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class Command(BaseCommand):
    help = (
        "Executa o estágio 2 pós-importação do legado: sync manual, renovações, "
        "pagamentos iniciais, mídia, rebuild de ciclos e auditoria final."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado usado na importação base.",
        )
        parser.add_argument(
            "--legacy-media-root",
            default="anexos_legado",
            help="Diretório raiz do acervo legado para sincronização de mídia.",
        )
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--skip-media",
            action="store_true",
            help="Pula a sincronização de mídia legada neste run.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Persiste o estágio 2. Sem esta flag, executa em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON consolidado.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        legacy_media_root = Path(options["legacy_media_root"]).expanduser()
        execute = bool(options["execute"])
        cpf = options.get("cpf")
        skip_media = bool(options["skip_media"])

        target = (
            Path(options["report_json"]).expanduser()
            if options.get("report_json")
            else _default_report_path("post_import_legacy_enrichment")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        renewals_report = target.parent / f"sync_legacy_renewals_{timestamp}.json"
        initial_report = target.parent / f"sync_legacy_initial_payments_{timestamp}.json"
        media_report = target.parent / f"sync_legacy_media_assets_{timestamp}.json"
        rebuild_report = target.parent / f"rebuild_cycle_state_{timestamp}.json"
        audit_report = target.parent / f"audit_cycle_timeline_{timestamp}.json"

        self.stdout.write(
            f"Modo={'EXECUTE' if execute else 'DRY-RUN'} dump={dump_path} cpf={cpf or 'todos'}"
        )

        manual_summary = self._run_subcommand(
            SyncLegacyPagamentoManualFieldsCommand,
            file=str(dump_path),
            competencia=None,
            execute=execute,
            include_refi_flags=True,
        ) or {}
        self._emit_stage_summary("1.sync_legacy_pagamento_manual_fields", manual_summary)

        self._run_subcommand(
            SyncLegacyRenewalsCommand,
            file=str(dump_path),
            cpf=cpf,
            execute=execute,
            report_json=str(renewals_report),
        )
        renewals_payload = _read_json(renewals_report)
        self._emit_stage_summary(
            "2.sync_legacy_renewals",
            renewals_payload.get("summary", {}),
        )

        self._run_subcommand(
            SyncLegacyInitialPaymentsCommand,
            file=str(dump_path),
            legacy_media_root=str(legacy_media_root),
            overrides=None,
            cpf=cpf,
            execute=execute,
            report_json=str(initial_report),
        )
        initial_payload = _read_json(initial_report)
        self._emit_stage_summary(
            "3.sync_legacy_initial_payments",
            initial_payload.get("summary", {}),
        )

        if skip_media:
            media_payload = {
                "summary": {
                    "skipped": True,
                    "reason": "skip_media_flag",
                    "legacy_root": str(legacy_media_root),
                }
            }
            self._emit_stage_summary("4.sync_legacy_media_assets", media_payload["summary"])
        else:
            self._run_subcommand(
                SyncLegacyMediaAssetsCommand,
                legacy_root=str(legacy_media_root),
                families="cadastro,renovacao,tesouraria,manual,esteira",
                cpf=cpf,
                execute=execute,
                report_json=str(media_report),
            )
            media_payload = _read_json(media_report)
            self._emit_stage_summary(
                "4.sync_legacy_media_assets",
                media_payload.get("summary", {}),
            )

        self._run_subcommand(
            RebuildCycleStateCommand,
            cpf=cpf,
            execute=execute,
            report_json=str(rebuild_report),
        )
        rebuild_payload = _read_json(rebuild_report)
        self._emit_stage_summary("5.rebuild_cycle_state", rebuild_payload.get("summary", {}))

        self._run_subcommand(
            AuditCycleTimelineCommand,
            cpf=cpf,
            json_path=str(audit_report),
            csv_path=None,
        )
        audit_payload = _read_json(audit_report)
        self._emit_stage_summary("6.audit_cycle_timeline", audit_payload.get("summary", {}))

        summary = {
            "mode": "execute" if execute else "dry-run",
            "cpf": cpf,
            "dump": str(dump_path),
            "legacy_media_root": str(legacy_media_root),
            "skip_media": skip_media,
            "manual_updates": manual_summary.get("pagamentos_alterados", 0),
            "renewals_synced": renewals_payload.get("summary", {}).get("synced", 0),
            "initial_payments_synced": initial_payload.get("summary", {}).get("synced", 0),
            "media_updated": media_payload.get("summary", {}).get("updated", 0),
            "contracts_rebuilt": rebuild_payload.get("summary", {}).get("total_contratos", 0),
            "associados_auditados": audit_payload.get("summary", {}).get("total_associados", 0),
            "associados_com_achados": audit_payload.get("summary", {}).get(
                "associados_com_achados", 0
            ),
        }
        payload = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "stages": {
                "manual_fields": manual_summary,
                "renewals": renewals_payload,
                "initial_payments": initial_payload,
                "media_assets": media_payload,
                "rebuild": rebuild_payload,
                "audit": audit_payload,
            },
        }
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.summary = summary

        self.stdout.write(
            self.style.SUCCESS(
                "Estágio 2 pós-importação concluído "
                f"em modo {summary['mode']}."
            )
        )
        self.stdout.write(f"Relatório consolidado: {target}")

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

    def _emit_stage_summary(self, stage: str, summary):
        if not isinstance(summary, dict):
            self.stdout.write(f"{stage}: concluído")
            return
        compact = ", ".join(f"{key}={value}" for key, value in summary.items())
        self.stdout.write(f"{stage}: {compact}")
