from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.contratos.shifted_discount_repair import (
    audit_and_repair_shifted_discount_references,
    parse_reference_month,
    write_shifted_discount_report,
)


class Command(BaseCommand):
    help = (
        "Audita e corrige casos em que um desconto foi gravado no mês seguinte "
        "por engano, sem rebuildar os ciclos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--paid-ref",
            default="2026-04",
            help="Competência atualmente marcada como paga (YYYY-MM).",
        )
        parser.add_argument(
            "--correct-ref",
            default="2026-03",
            help="Competência que deveria estar paga (YYYY-MM).",
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

        paid_ref = parse_reference_month(options["paid_ref"])
        correct_ref = parse_reference_month(options["correct_ref"])

        payload = audit_and_repair_shifted_discount_references(
            paid_ref=paid_ref,
            correct_ref=correct_ref,
            cpf_cnpj=options.get("cpf_cnpj"),
            associado_id=options.get("associado_id"),
            execute=execute,
        )

        report_path = write_shifted_discount_report(
            payload,
            Path(options["report_json"]) if options.get("report_json") else None,
        )
        summary = payload["summary"]

        self.stdout.write(f"modo: {payload['mode']}")
        self.stdout.write(f"paid_ref: {payload['paid_ref']}")
        self.stdout.write(f"correct_ref: {payload['correct_ref']}")
        self.stdout.write(f"scanned_associados: {summary['scanned_associados']}")
        self.stdout.write(f"results: {summary['results']}")
        self.stdout.write(f"repairable: {summary['repairable']}")
        self.stdout.write(f"repaired: {summary['repaired']}")
        self.stdout.write(f"manual_review: {summary['manual_review']}")
        self.stdout.write(
            f"projection_only_regularized: {summary['projection_only_regularized']}"
        )
        self.stdout.write(f"report_json: {report_path}")
        if dry_run:
            self.stdout.write("Dry-run concluído. Use --execute para persistir as alterações.")
