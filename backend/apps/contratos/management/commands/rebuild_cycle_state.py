from __future__ import annotations

import json
import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
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
    help = "Reconstrói o estado canônico de ciclos/parcelas/refinanciamentos a partir do financeiro atual."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--contract-id",
            dest="contract_ids",
            action="append",
            default=[],
            help="Restringe a reconstrução a um contrato específico. Pode ser repetido.",
        )
        parser.add_argument(
            "--contract-ids-file",
            dest="contract_ids_file",
            help=(
                "Arquivo texto/CSV com coluna contrato_id ou valores numéricos de contrato_id, "
                "um por linha."
            ),
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica a reconstrução no banco. Sem esta flag, executa apenas dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    @staticmethod
    def _parse_contract_ids(options) -> list[int]:
        parsed: set[int] = set()
        for raw in options.get("contract_ids") or []:
            if raw is None:
                continue
            normalized = str(raw).strip()
            if not normalized:
                continue
            if not normalized.isdigit():
                raise CommandError(f"contract-id inválido: {normalized}")
            parsed.add(int(normalized))

        file_path = options.get("contract_ids_file")
        if not file_path:
            return sorted(parsed)

        path = Path(file_path)
        if not path.exists():
            raise CommandError(f"Arquivo não encontrado: {path}")

        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return sorted(parsed)

        if "," in text.splitlines()[0]:
            reader = csv.DictReader(text.splitlines())
            if "contrato_id" not in (reader.fieldnames or []):
                raise CommandError(
                    "CSV informado em --contract-ids-file deve conter a coluna contrato_id."
                )
            for row in reader:
                raw = str(row.get("contrato_id") or "").strip()
                if raw.isdigit():
                    parsed.add(int(raw))
            return sorted(parsed)

        for line in text.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if not normalized.isdigit():
                raise CommandError(
                    f"Linha inválida em --contract-ids-file: {normalized}"
                )
            parsed.add(int(normalized))
        return sorted(parsed)

    def handle(self, *args, **options):
        execute = bool(options["execute"])
        queryset = Contrato.objects.select_related("associado", "agente").order_by(
            "associado__nome_completo",
            "id",
        )
        cpf = options.get("cpf")
        if cpf:
            queryset = queryset.filter(associado__cpf_cnpj=cpf)
        contract_ids = self._parse_contract_ids(options)
        if contract_ids:
            queryset = queryset.filter(id__in=contract_ids)

        contratos = list(queryset)
        if not contratos:
            raise CommandError("Nenhum contrato encontrado para reconstrução.")

        reports = [
            rebuild_contract_cycle_state(contrato, execute=execute).as_dict()
            for contrato in contratos
        ]
        summary = {
            "mode": "execute" if execute else "dry-run",
            "total_contratos": len(reports),
            "ciclos_materializados": sum(item["ciclos_materializados"] for item in reports),
            "ciclos_invalidos_soft_deleted": sum(
                item["ciclos_invalidos_soft_deleted"] for item in reports
            ),
            "parcelas_invalidas_soft_deleted": sum(
                item["parcelas_invalidas_soft_deleted"] for item in reports
            ),
            "itens_retorno_reassociados": sum(
                item["itens_retorno_reassociados"] for item in reports
            ),
            "itens_retorno_orfaos": sum(item["itens_retorno_orfaos"] for item in reports),
            "baixas_reassociadas": sum(item["baixas_reassociadas"] for item in reports),
            "refinanciamentos_ajustados": sum(
                item["refinanciamentos_ajustados"] for item in reports
            ),
            "refinanciamentos_soft_deleted": sum(
                item["refinanciamentos_soft_deleted"] for item in reports
            ),
        }
        payload = {
            "generated_at": datetime.now().isoformat(),
            "summary": summary,
            "contracts": reports,
        }

        target = Path(options["report_json"]) if options.get("report_json") else _default_report_path("rebuild_cycle_state")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Reconstrução concluída em modo {summary['mode']} para {summary['total_contratos']} contrato(s)."
            )
        )
        self.stdout.write(f"Relatório: {target}")
