from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.canonicalization import (
    apply_canonicalization,
    build_canonicalization_payload,
    write_canonicalization_report,
)


def _default_report_path(fmt: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    extension = "csv" if fmt == "csv" else "json"
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "canonicalizacao"
        / f"canonicalizar_contratos_duplicados_{timestamp}.{extension}"
    )


class Command(BaseCommand):
    help = "Marca contratos canônicos e contratos sombra por associado sem alterar ciclos."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persiste a canonicidade. Sem a flag, roda em dry-run.",
        )
        parser.add_argument(
            "--format",
            choices=["json", "csv"],
            default="json",
            help="Formato do relatório de saída.",
        )
        parser.add_argument(
            "--report-path",
            dest="report_path",
            help="Caminho opcional para gravar o relatório.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        fmt = options["format"]
        payload = (
            apply_canonicalization(cpf_cnpj=options.get("cpf_cnpj"))
            if apply_changes
            else build_canonicalization_payload(cpf_cnpj=options.get("cpf_cnpj"))
        )
        report_path = (
            Path(options["report_path"])
            if options.get("report_path")
            else _default_report_path(fmt)
        )
        write_canonicalization_report(payload, output_path=report_path, fmt=fmt)

        summary = payload["summary"]
        mode = "apply" if apply_changes else "dry-run"
        updated = summary.get("updated_contracts", 0) if apply_changes else summary["changed_contracts"]
        self.stdout.write(
            self.style.SUCCESS(
                (
                    f"Canonicalização concluída em {mode}: "
                    f"{summary['groups']} grupo(s), "
                    f"{summary['shadow_contracts']} contrato(s) sombra, "
                    f"{updated} contrato(s) {'atualizado(s)' if apply_changes else 'com mudança pendente'}."
                )
            )
        )
        self.stdout.write(f"Relatório: {report_path}")
