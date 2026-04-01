from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.contratos.models import Contrato


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


class Command(BaseCommand):
    help = "Recalcula a comissão do agente em todos os contratos usando a margem disponível."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica as alterações no banco. Sem esta flag, executa dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        execute = bool(options["execute"])
        cpf = options.get("cpf")

        queryset = Contrato.objects.select_related("associado").order_by("id")
        if cpf:
            queryset = queryset.filter(associado__cpf_cnpj=cpf)

        contratos = list(queryset)
        if not contratos:
            raise CommandError("Nenhum contrato encontrado para recálculo.")

        updates: list[dict[str, object]] = []
        skipped = 0
        for contrato in contratos:
            expected = contrato.calculate_comissao_agente()
            if expected is None:
                skipped += 1
                continue
            if contrato.comissao_agente == expected:
                continue

            updates.append(
                {
                    "id": contrato.id,
                    "codigo": contrato.codigo,
                    "cpf_cnpj": contrato.associado.cpf_cnpj,
                    "percentual_repasse": str(contrato.resolve_percentual_repasse()),
                    "margem_disponivel": str(contrato.margem_disponivel),
                    "comissao_anterior": str(contrato.comissao_agente),
                    "comissao_nova": str(expected),
                }
            )
            if execute:
                contrato.comissao_agente = expected
                contrato.save(update_fields=["comissao_agente", "updated_at"])

        payload = {
            "generated_at": datetime.now().isoformat(),
            "mode": "execute" if execute else "dry-run",
            "summary": {
                "total_contratos": len(contratos),
                "updated": len(updates),
                "skipped": skipped,
            },
            "contracts": updates,
        }

        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("recalculate_agent_commissions")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Recálculo concluído em modo {payload['mode']} para {len(updates)} contrato(s)."
            )
        )
        self.stdout.write(f"Relatório: {target}")
