from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.audit import build_return_consistency_report, write_report_json
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
        "Audita a consistência entre dump legado, importacao_pagamentomensalidade, "
        "itens de retorno e baixas manuais."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado com a tabela pagamentos_mensalidades.",
        )
        parser.add_argument(
            "--competencia",
            help="Competência no formato YYYY-MM para limitar a auditoria.",
        )
        parser.add_argument(
            "--cpf",
            help="CPF específico para auditar.",
        )
        parser.add_argument(
            "--report-json",
            help="Caminho de saída opcional para o relatório JSON.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).resolve()
        if not dump_path.exists():
            raise CommandError(f"Dump não encontrado: {dump_path}")

        report = build_return_consistency_report(
            dump_path=dump_path,
            competencia=_parse_competencia(options.get("competencia")),
            cpf=options.get("cpf"),
        )

        report_json = options.get("report_json")
        if report_json:
            output = write_report_json(report_json, report)
            self.stdout.write(f"relatorio_json: {output}")

        summary = report["summary"]
        self.stdout.write(f"status: {summary['status']}")
        self.stdout.write(
            f"timezone_only_paid_at_total: {summary['timezone_only_paid_at_total']}"
        )
        self.stdout.write(f"real_mismatch_total: {summary['real_mismatch_total']}")
        self.stdout.write(f"missing_current_total: {summary['missing_current_total']}")
        self.stdout.write(f"missing_legacy_total: {summary['missing_legacy_total']}")
        self.stdout.write(f"itens_retorno_orfaos: {summary['itens_retorno_orfaos']}")
        self.stdout.write(f"baixas_manuais_total: {summary['baixas_manuais_total']}")
        self.stdout.write(
            f"manual_rows_with_baixa_manual_total: {summary['manual_rows_with_baixa_manual_total']}"
        )
        self.stdout.write(
            f"parcelas_sem_retorno_ou_baixa: {summary['parcelas_sem_retorno_ou_baixa']}"
        )
