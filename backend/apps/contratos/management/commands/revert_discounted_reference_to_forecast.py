from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.contratos.revert_discounted_reference import (
    audit_and_revert_discounted_reference_to_forecast,
    parse_reference_month,
    write_revert_report,
)


class Command(BaseCommand):
    help = (
        "Audita e reverte competências marcadas como descontadas por engano, "
        "voltando a referência para previsão e rebuildando os ciclos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--target-ref",
            default="2026-04",
            help="Competência a ser revertida para previsão (YYYY-MM).",
        )
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--associado-id",
            type=int,
            dest="associado_id",
            help="Filtra por associado.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analisa sem persistir alterações.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica as correções definitivamente.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        execute = bool(options.get("execute"))
        if dry_run and execute:
            raise CommandError("Use apenas um modo: --dry-run ou --execute.")
        if not dry_run and not execute:
            dry_run = True

        target_ref = parse_reference_month(options["target_ref"])
        payload = audit_and_revert_discounted_reference_to_forecast(
            target_ref=target_ref,
            cpf_cnpj=options.get("cpf_cnpj"),
            associado_id=options.get("associado_id"),
            execute=execute,
        )

        report_path = write_revert_report(
            payload,
            Path(options["report_json"]) if options.get("report_json") else None,
        )
        summary = payload["summary"]

        self.stdout.write(f"modo: {payload['mode']}")
        self.stdout.write(f"target_ref: {payload['target_ref']}")
        self.stdout.write(f"scanned_associados: {summary['scanned_associados']}")
        self.stdout.write(f"scanned_contracts: {summary['scanned_contracts']}")
        self.stdout.write(f"results: {summary['results']}")
        self.stdout.write(f"repairable: {summary['repairable']}")
        self.stdout.write(f"reverted: {summary['reverted']}")
        self.stdout.write(f"manual_review: {summary['manual_review']}")
        self.stdout.write(f"evidence_changes: {summary['evidence_changes']}")
        self.stdout.write(f"report_json: {report_path}")
        if dry_run:
            self.stdout.write("Dry-run concluído. Use --execute para persistir as alterações.")
