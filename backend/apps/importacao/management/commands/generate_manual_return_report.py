from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.importacao.audit import write_report_json
from apps.importacao.manual_return_service import ManualReturnReportService
from core.legacy_dump import default_legacy_dump_path


def _parse_competencia(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise CommandError("Competência inválida. Use YYYY-MM.") from exc


class Command(BaseCommand):
    help = (
        "Gera um ArquivoRetorno sintético para baixas manuais a partir de um PDF mensal "
        "e do dump legado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pdf",
            required=True,
            help="Caminho do PDF do relatório mensal de baixa manual.",
        )
        parser.add_argument(
            "--file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado com pagamentos_mensalidades.",
        )
        parser.add_argument(
            "--competencia",
            help="Competência esperada no formato YYYY-MM.",
        )
        parser.add_argument(
            "--user-email",
            help="Usuário que ficará como responsável pelo arquivo sintético.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Persiste o arquivo retorno sintético. Sem isso, roda em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            help="Caminho opcional para salvar o relatório JSON da execução.",
        )

    def handle(self, *args, **options):
        pdf_path = Path(options["pdf"]).expanduser().resolve()
        if not pdf_path.exists():
            raise CommandError(f"PDF não encontrado: {pdf_path}")

        dump_path = Path(options["file"]).expanduser().resolve()
        if not dump_path.exists():
            raise CommandError(f"Dump não encontrado: {dump_path}")

        uploaded_by = None
        expected_competencia = _parse_competencia(options.get("competencia"))
        if options.get("user_email"):
            uploaded_by = User.objects.filter(email=options["user_email"]).first()
            if uploaded_by is None:
                raise CommandError(
                    f"Usuário não encontrado para --user-email={options['user_email']}"
                )

        result, report = ManualReturnReportService().create_or_update_from_pdf(
            pdf_path=pdf_path,
            dump_path=dump_path,
            uploaded_by=uploaded_by,
            expected_competencia=expected_competencia,
            execute=bool(options["execute"]),
        )

        payload = {
            "mode": "execute" if options["execute"] else "dry-run",
            "pdf_path": str(pdf_path),
            "dump_path": str(dump_path),
            "report": {
                "competencia": report.competencia.isoformat(),
                "generated_at": report.generated_at.isoformat()
                if report.generated_at
                else None,
                "esperado_total": f"{report.esperado_total:.2f}",
                "recebido_total": f"{report.recebido_total:.2f}",
                "ok_total": report.ok_total,
                "total": report.total,
            },
            "result": result.as_dict(),
        }

        report_json = options.get("report_json")
        if report_json:
            output = write_report_json(report_json, payload)
            self.stdout.write(f"relatorio_json: {output}")

        self.stdout.write(f"modo: {payload['mode']}")
        self.stdout.write(f"competencia: {payload['report']['competencia']}")
        self.stdout.write(f"linhas_pdf: {payload['report']['total']}")
        self.stdout.write(f"pagamentos_encontrados: {result.matched_pagamentos}")
        self.stdout.write(f"parcelas_encontradas: {result.matched_parcelas}")
        self.stdout.write(f"arquivo_id: {result.arquivo_id}")
