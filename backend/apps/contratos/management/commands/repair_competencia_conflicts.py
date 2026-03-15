from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import ValidationError

from apps.contratos.competencia import (
    find_competencia_conflict_groups,
    repair_conflict_group,
)


class Command(BaseCommand):
    help = (
        "Repara um grupo de conflito de competência, cancelando ciclos perdedores "
        "e reatribuindo referências inequívocas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--group-id", dest="group_id", help="Identificador do grupo.")
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--associado-id",
            type=int,
            dest="associado_id",
            help="Filtra por associado.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica o reparo. Sem este flag, roda em dry-run.",
        )
        parser.add_argument(
            "--format",
            choices=["table", "json"],
            default="table",
            help="Formato de saída.",
        )

    def handle(self, *args, **options):
        group_id = options.get("group_id")
        groups = find_competencia_conflict_groups(
            associado_id=options.get("associado_id"),
            cpf_cnpj=options.get("cpf_cnpj"),
        )

        if not groups:
            self.stdout.write("Nenhum grupo elegível encontrado para o filtro informado.")
            return

        if not group_id:
            if len(groups) != 1:
                raise CommandError(
                    "Informe --group-id ou filtre até restar exatamente um grupo."
                )
            group_id = groups[0]["group_id"]

        matching_group = next((group for group in groups if group["group_id"] == group_id), None)
        if not matching_group:
            raise CommandError(f"Grupo não encontrado para os filtros informados: {group_id}")

        try:
            summary = repair_conflict_group(
                group_id=group_id,
                execute=options["execute"],
            )
        except ValidationError as exc:
            if options["format"] == "json":
                self.stdout.write(
                    json.dumps(exc.detail, ensure_ascii=False, indent=2, default=str)
                )
                return
            detail = exc.detail
            if isinstance(detail, dict):
                message = detail.get("detail") or str(detail)
            else:
                message = str(detail)
            raise CommandError(message)

        if options["format"] == "json":
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
            return

        mode = "EXECUTE" if options["execute"] else "DRY-RUN"
        self.stdout.write(f"{mode} group={summary['group_id']}")
        self.stdout.write(
            "\n".join(
                [
                    f"classification={summary['classification']}",
                    f"auto_repairable={summary['auto_repairable']}",
                    f"canonical_cycle_id={summary['canonical_cycle_id']}",
                    f"losing_cycle_ids={','.join(map(str, summary['losing_cycle_ids'])) or '-'}",
                    f"reassigned_return_items={summary['reassigned_return_items']}",
                    f"reassigned_baixas_manuais={summary['reassigned_baixas_manuais']}",
                    f"reassigned_confirmacoes={summary['reassigned_confirmacoes']}",
                    f"reassigned_refinanciamentos={summary['reassigned_refinanciamentos']}",
                    f"reassigned_comprovantes={summary['reassigned_comprovantes']}",
                    f"cancelled_cycles={summary['cancelled_cycles']}",
                    f"cancelled_contracts={summary['cancelled_contracts']}",
                ]
            )
        )
        for message in summary["manual_actions"]:
            self.stdout.write(f"manual: {message}")
        if not options["execute"]:
            self.stdout.write("Dry-run concluído. Use --execute para aplicar.")
