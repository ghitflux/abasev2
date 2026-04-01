from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, OutputWrapper

from apps.accounts.legacy_import_audit import SUCCESS_STATUS
from apps.accounts.legacy_restore_runtime import (
    capture_preserved_auth_snapshot,
    stage_return_files,
    validate_preserved_auth_snapshot,
)
from core.legacy_dump import default_legacy_dump_path


def _default_workspace_path(*parts: str) -> Path:
    workspace_root = Path("/workspace")
    if workspace_root.exists():
        return workspace_root.joinpath(*parts)
    return Path(settings.BASE_DIR).joinpath(*parts)


def _default_dump_path() -> Path:
    candidates = [
        _default_workspace_path("dumps_legado", "abase_banco_legado_31.03.2026.sql"),
        _default_workspace_path("dumps_legado", "abase_dump_legado_21.03.2026.sql"),
        Path(default_legacy_dump_path()),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _default_legacy_media_root() -> Path:
    candidates = [
        _default_workspace_path("anexos_legado"),
        Path("anexos_legado"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


class Command(BaseCommand):
    help = (
        "Orquestra a restauração do dump legado, reaplica o enriquecimento canônico "
        "e reimporta os arquivos retorno de 10/2025 a 02/2026."
    )

    def add_arguments(self, parser):
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        default_root = _default_workspace_path("backups", f"legacy_restore_{timestamp}")
        parser.add_argument(
            "--file",
            default=str(_default_dump_path()),
            help="Dump SQL legado a restaurar.",
        )
        parser.add_argument(
            "--legacy-media-root",
            default=str(_default_legacy_media_root()),
            help="Diretório raiz do acervo legado.",
        )
        parser.add_argument(
            "--staging-dir",
            default=str(default_root / "staged_return_files"),
            help="Diretório de staging para os 5 arquivos retorno atuais.",
        )
        parser.add_argument(
            "--report-json",
            default=str(default_root / "restore_report.json"),
            help="Relatório consolidado da restauração.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Executa a restauração definitivamente.",
        )

    def handle(self, *args, **options):
        if not options["execute"]:
            raise CommandError("Use `--execute` para rodar a restauração completa.")

        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        legacy_media_root = Path(options["legacy_media_root"]).expanduser()
        if not legacy_media_root.exists():
            raise CommandError(f"Acervo legado não encontrado: {legacy_media_root}")

        staging_dir = Path(options["staging_dir"]).expanduser()
        report_path = Path(options["report_json"]).expanduser()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        staging_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        import_report = report_path.parent / f"import_legacy_full_{timestamp}.json"
        verify_report = report_path.parent / f"verify_legacy_import_{timestamp}.json"
        enrichment_report = report_path.parent / f"post_import_legacy_enrichment_{timestamp}.json"
        reimport_report = report_path.parent / f"reimport_staged_return_files_{timestamp}.json"
        rebuild_report = report_path.parent / f"rebuild_cycle_state_{timestamp}.json"
        audit_cycle_report = report_path.parent / f"audit_cycle_timeline_{timestamp}.json"
        audit_return_report = report_path.parent / f"audit_return_consistency_2026_02_{timestamp}.json"
        audit_media_report = report_path.parent / f"audit_legacy_media_assets_{timestamp}.json"

        payload: dict[str, object] = {
            "generated_at": datetime.now().isoformat(),
            "dump_path": str(dump_path),
            "legacy_media_root": str(legacy_media_root),
            "staging_dir": str(staging_dir),
            "report_path": str(report_path),
            "status": "running",
            "stages": {},
        }
        self._write_report(report_path, payload)

        try:
            pre_auth_snapshot = capture_preserved_auth_snapshot()
            payload["pre_auth_counts"] = pre_auth_snapshot["counts"]
            self.stdout.write("1/8 staging dos arquivos retorno atuais")
            payload["stages"]["staging"] = stage_return_files(staging_dir)
            self._write_report(report_path, payload)

            self.stdout.write("2/8 limpeza do banco preservando auth")
            self._run_subcommand(
                "apps.accounts.management.commands.reset_database_preserving_auth",
                "Command",
                dry_run=False,
                execute=True,
            )
            payload["stages"]["reset_database_preserving_auth"] = {
                "mode": "execute",
                "status": "completed",
            }
            self._write_report(report_path, payload)

            self.stdout.write("3/8 importação fiel do dump legado")
            self._run_subcommand(
                "apps.accounts.management.commands.import_legacy_full",
                "Command",
                file=str(dump_path),
                report_file=str(import_report),
                dry_run=False,
                execute=True,
            )
            payload["stages"]["import_legacy_full"] = self._read_json(import_report)
            self._write_report(report_path, payload)

            self.stdout.write("4/8 verificação estrutural da importação")
            self._run_subcommand(
                "apps.accounts.management.commands.verify_legacy_import",
                "Command",
                file=str(dump_path),
                report_file=str(verify_report),
                no_fail=False,
            )
            verify_payload = self._read_json(verify_report)
            payload["stages"]["verify_legacy_import"] = verify_payload
            if verify_payload["status"] != SUCCESS_STATUS:
                raise CommandError(
                    f"Verificação falhou após restauração. Consulte {verify_report}"
                )
            self._write_report(report_path, payload)

            self.stdout.write("5/8 enriquecimento canônico pós-importação")
            self._run_subcommand(
                "apps.accounts.management.commands.post_import_legacy_enrichment",
                "Command",
                file=str(dump_path),
                legacy_media_root=str(legacy_media_root),
                cpf=None,
                skip_media=False,
                execute=True,
                report_json=str(enrichment_report),
            )
            payload["stages"]["post_import_legacy_enrichment"] = self._read_json(enrichment_report)
            self._write_report(report_path, payload)

            self.stdout.write("6/8 reimportação síncrona dos retornos de 10/2025 a 02/2026")
            self._run_subcommand(
                "apps.importacao.management.commands.reimport_staged_return_files",
                "Command",
                staging_dir=str(staging_dir),
                user_email=None,
                report_json=str(reimport_report),
                dry_run=False,
                execute=True,
            )
            payload["stages"]["reimport_staged_return_files"] = self._read_json(reimport_report)
            self._write_report(report_path, payload)

            self.stdout.write("7/8 reparos e reconstrução final")
            repair_summary = self._run_subcommand(
                "apps.importacao.management.commands.repair_manual_return_conflicts",
                "Command",
                competencia="2026-02",
                cpf=None,
                execute=True,
            )
            payload["stages"]["repair_manual_return_conflicts"] = repair_summary or {}

            self._run_subcommand(
                "apps.contratos.management.commands.rebuild_cycle_state",
                "Command",
                cpf=None,
                execute=True,
                report_json=str(rebuild_report),
            )
            payload["stages"]["rebuild_cycle_state"] = self._read_json(rebuild_report)
            self._write_report(report_path, payload)

            self.stdout.write("8/8 auditorias finais")
            self._run_subcommand(
                "apps.contratos.management.commands.audit_cycle_timeline",
                "Command",
                cpf=None,
                json_path=str(audit_cycle_report),
                csv_path=None,
            )
            payload["stages"]["audit_cycle_timeline"] = self._read_json(audit_cycle_report)

            self._run_subcommand(
                "apps.importacao.management.commands.audit_return_consistency",
                "Command",
                file=str(dump_path),
                competencia="2026-02",
                cpf=None,
                report_json=str(audit_return_report),
            )
            payload["stages"]["audit_return_consistency"] = self._read_json(audit_return_report)

            self._run_subcommand(
                "apps.accounts.management.commands.audit_legacy_media_assets",
                "Command",
                legacy_root=str(legacy_media_root),
                families="cadastro,renovacao,tesouraria,manual,esteira",
                report_json=str(audit_media_report),
            )
            payload["stages"]["audit_legacy_media_assets"] = self._read_json(audit_media_report)

            auth_validation = validate_preserved_auth_snapshot(pre_auth_snapshot)
            payload["post_auth_counts"] = auth_validation["post_counts"]
            payload["auth_validation"] = auth_validation
            if not auth_validation["ok"]:
                error_preview = " | ".join(auth_validation["errors"][:5])
                raise CommandError(
                    "Validação de auth preservado falhou. "
                    f"Consulte {report_path}. Detalhes: {error_preview}"
                )

            payload["status"] = "completed"
            self._write_report(report_path, payload)
        except Exception as exc:
            payload["status"] = "failed"
            payload["error"] = str(exc)
            self._write_report(report_path, payload)
            raise

        self.stdout.write(self.style.SUCCESS(f"Restauração concluída. Relatório: {report_path}"))

    def _run_subcommand(self, module_path: str, class_name: str, **kwargs):
        import importlib

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        module = importlib.import_module(module_path)
        command_class = getattr(module, class_name)
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
            raise CommandError(f"Falha em {module_path}: {exc}{suffix}") from exc
        return getattr(command, "summary", None)

    def _read_json(self, path: Path) -> dict[str, object]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_report(self, path: Path, payload: dict[str, object]) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
