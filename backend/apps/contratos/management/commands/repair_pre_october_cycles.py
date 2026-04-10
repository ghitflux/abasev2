from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.contratos.pre_october_cycle_repair import (
    audit_and_repair_pre_october_cycles,
    write_pre_october_repair_report,
)


def _parse_floor(value: str):
    year, month = str(value).split("-", 1)
    from datetime import date

    return date(int(year), int(month), 1)


class Command(BaseCommand):
    help = (
        "Remove referências anteriores a uma competência-base e reconstrói a linha "
        "mensal contínua dos contratos afetados."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--floor-reference",
            default="2025-10",
            help="Competência mínima aceitável para os ciclos (YYYY-MM).",
        )
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analisa sem persistir alterações.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica as alterações no banco.",
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

        floor_reference = _parse_floor(options["floor_reference"])
        payload = audit_and_repair_pre_october_cycles(
            floor_reference=floor_reference,
            cpf_cnpj=options.get("cpf_cnpj"),
            execute=execute,
        )
        report_path = write_pre_october_repair_report(
            payload,
            Path(options["report_json"]) if options.get("report_json") else None,
        )
        summary = payload["summary"]

        self.stdout.write(f"mode: {payload['mode']}")
        self.stdout.write(f"floor_reference: {payload['floor_reference']}")
        self.stdout.write(f"contracts_scanned: {summary['contracts_scanned']}")
        self.stdout.write(f"contracts_candidate: {summary['contracts_candidate']}")
        self.stdout.write(f"contracts_applied: {summary['contracts_applied']}")
        self.stdout.write(f"pre_floor_removed: {summary['pre_floor_removed']}")
        self.stdout.write(f"parcelas_created: {summary['parcelas_created']}")
        self.stdout.write(f"parcelas_updated: {summary['parcelas_updated']}")
        self.stdout.write(f"parcelas_soft_deleted: {summary['parcelas_soft_deleted']}")
        self.stdout.write(f"cycles_created: {summary['cycles_created']}")
        self.stdout.write(f"cycles_updated: {summary['cycles_updated']}")
        self.stdout.write(f"cycles_soft_deleted: {summary['cycles_soft_deleted']}")
        self.stdout.write(f"report_json: {report_path}")
        if dry_run:
            self.stdout.write("Dry-run concluído. Use --execute para persistir as alterações.")
