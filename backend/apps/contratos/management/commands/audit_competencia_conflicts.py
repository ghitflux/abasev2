from __future__ import annotations

import csv
import json

from django.core.management.base import BaseCommand

from apps.contratos.competencia import (
    find_competencia_conflict_groups,
    flatten_conflict_groups,
)


class Command(BaseCommand):
    help = "Audita conflitos de competência por associado entre contratos/ciclos/parcelas."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--associado-id",
            type=int,
            dest="associado_id",
            help="Filtra por associado.",
        )
        parser.add_argument(
            "--format",
            choices=["table", "json", "csv"],
            default="table",
            help="Formato de saída.",
        )

    def handle(self, *args, **options):
        groups = find_competencia_conflict_groups(
            associado_id=options.get("associado_id"),
            cpf_cnpj=options.get("cpf_cnpj"),
        )

        output_format = options["format"]
        if output_format == "json":
            self.stdout.write(json.dumps(groups, ensure_ascii=False, indent=2, default=str))
            return

        if output_format == "csv":
            rows = flatten_conflict_groups(groups)
            fieldnames = [
                "group_id",
                "associado_id",
                "cpf_cnpj",
                "nome_associado",
                "classification",
                "auto_repairable",
                "canonical_contract_id",
                "canonical_cycle_id",
                "strategy",
                "resolution_status",
                "referencia_mes",
                "contrato_id",
                "contrato_codigo",
                "ciclo_id",
                "parcela_id",
                "status",
            ]
            writer = csv.DictWriter(self.stdout, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            return

        if not groups:
            self.stdout.write("Nenhum conflito de competência encontrado.")
            return

        self.stdout.write(
            "\n".join(
                [
                    f"Grupos: {len(groups)}",
                    f"Auto-reparáveis: {sum(1 for item in groups if item['auto_repairable'])}",
                    (
                        "Manuais: "
                        f"{sum(1 for item in groups if item['classification'] == 'manual_required')}"
                    ),
                ]
            )
        )
        for group in groups:
            self.stdout.write(
                (
                    "[{group_id}] associado={associado_id} cpf={cpf} class={classification} "
                    "auto={auto} canonical_cycle={canonical} months={months}"
                ).format(
                    group_id=group["group_id"],
                    associado_id=group["associado_id"],
                    cpf=group["cpf_cnpj"],
                    classification=group["classification"],
                    auto="yes" if group["auto_repairable"] else "no",
                    canonical=group["canonical_cycle_id"] or "-",
                    months=",".join(group["months"]),
                )
            )
            if group["manual_reasons"]:
                self.stdout.write(f"  manual: {' | '.join(group['manual_reasons'])}")
