from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.legacy_restore_runtime import (
    load_staged_return_manifest,
    select_restore_uploaded_by,
)
from apps.importacao.models import ArquivoRetorno
from apps.importacao.services import ArquivoRetornoService


class Command(BaseCommand):
    help = (
        "Reimporta em ordem cronológica os arquivos retorno staged antes da "
        "restauração do legado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--staging-dir",
            required=True,
            help="Diretório com os arquivos staged e o manifesto JSON.",
        )
        parser.add_argument(
            "--user-email",
            help="Sobrescreve o usuário uploaded_by selecionado automaticamente.",
        )
        parser.add_argument(
            "--report-json",
            help="Caminho opcional para salvar o relatório consolidado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida manifesto e arquivos sem recriar ArquivoRetorno.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Reimporta definitivamente os arquivos staged.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        execute = bool(options["execute"])
        if dry_run == execute:
            raise CommandError("Informe exatamente um modo: use `--dry-run` ou `--execute`.")

        staging_dir = Path(options["staging_dir"]).expanduser()
        if not staging_dir.exists():
            raise CommandError(f"Diretório de staging não encontrado: {staging_dir}")

        manifest = load_staged_return_manifest(staging_dir)
        user = self._resolve_user(options.get("user_email"))
        results: list[dict[str, object]] = []
        service = ArquivoRetornoService()

        for item in sorted(manifest["files"], key=lambda row: row["competencia"]):
            competencia = item["competencia"]
            staged_path = staging_dir / item["staged_path"]
            if not staged_path.exists():
                raise CommandError(f"Arquivo staged não encontrado: {staged_path}")

            if dry_run:
                results.append(
                    {
                        "competencia": competencia,
                        "arquivo_nome": item["source_name"],
                        "staged_path": str(staged_path),
                        "status": "validated",
                    }
                )
                continue

            with staged_path.open("rb") as source:
                arquivo = service.upload(File(source, name=Path(item["source_name"]).name), user)

            if arquivo.status != ArquivoRetorno.Status.CONCLUIDO:
                raise CommandError(
                    f"Arquivo {arquivo.arquivo_nome} não concluiu processamento: {arquivo.status}"
                )
            if arquivo.competencia.isoformat() != competencia:
                raise CommandError(
                    f"Competência divergente para {arquivo.arquivo_nome}: "
                    f"esperado={competencia} atual={arquivo.competencia.isoformat()}"
                )

            results.append(
                {
                    "competencia": competencia,
                    "arquivo_nome": arquivo.arquivo_nome,
                    "arquivo_id": arquivo.id,
                    "status": arquivo.status,
                    "total_registros": arquivo.total_registros,
                    "processados": arquivo.processados,
                }
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"[EXECUTE] {competencia}: arquivo_id={arquivo.id} status={arquivo.status}"
                )
            )

        payload = {
            "generated_at": datetime.now().isoformat(),
            "mode": "dry-run" if dry_run else "execute",
            "staging_dir": str(staging_dir.resolve()),
            "uploaded_by": user.email,
            "results": results,
        }
        if options.get("report_json"):
            target = Path(options["report_json"]).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.stdout.write(f"Relatório: {target}")

        self.summary = {
            "mode": payload["mode"],
            "uploaded_by": user.email,
            "files": len(results),
            "competencias": [row["competencia"] for row in results],
        }

    def _resolve_user(self, user_email: str | None):
        if not user_email:
            return select_restore_uploaded_by()

        from apps.accounts.models import User

        user = User.objects.filter(email__iexact=user_email, is_active=True).first()
        if user is None:
            raise CommandError(f"Usuário não encontrado ou inativo: {user_email}")
        return user
