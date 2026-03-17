from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.associados.models import Associado
from apps.contratos.legacy_renewals import load_legacy_renewals, next_month_start
from apps.refinanciamento.models import Refinanciamento
from core.legacy_dump import LegacyDump


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
    help = "Audita se as renovações legadas foram convertidas no ledger canônico e nos ciclos corretos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="scriptsphp/abase (2).sql",
            help="Dump SQL legado.",
        )
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        dump = LegacyDump.from_file(dump_path)
        renewals = load_legacy_renewals(dump, cpf_filter=options.get("cpf"))
        if not renewals:
            raise CommandError("Nenhuma renovação legada encontrada para auditoria.")

        rows: list[dict[str, object]] = []
        conflicts = 0
        missing = 0
        start_mismatch = 0

        for renewal in renewals:
            associado = (
                Associado.all_objects.filter(cpf_cnpj=renewal.cpf_cnpj)
                .only("id", "nome_completo")
                .first()
            )
            refinanciamento = (
                Refinanciamento.all_objects.filter(
                    legacy_refinanciamento_id=renewal.legacy_id,
                    deleted_at__isnull=True,
                )
                .select_related("ciclo_destino", "contrato_origem")
                .first()
            )
            classifications: list[str] = []
            expected_first_reference = next_month_start(
                renewal.activation_at,
                ref1=renewal.ref1,
                ref2=renewal.ref2,
                ref3=renewal.ref3,
                ref4=renewal.ref4,
            )
            conflicting_refis = []

            if refinanciamento is None:
                classifications.append("missing_refinanciamento")
                missing += 1
            else:
                if refinanciamento.ciclo_destino_id is None:
                    classifications.append("missing_destination_cycle")
                    missing += 1
                elif refinanciamento.ciclo_destino.data_inicio != expected_first_reference:
                    classifications.append("cycle_start_mismatch")
                    start_mismatch += 1

                conflicting_refis = list(
                    Refinanciamento.all_objects.filter(
                        contrato_origem=refinanciamento.contrato_origem,
                        deleted_at__isnull=True,
                        legacy_refinanciamento_id__isnull=True,
                    )
                    .exclude(
                        status__in=[
                            Refinanciamento.Status.APTO_A_RENOVAR,
                            Refinanciamento.Status.PENDENTE_APTO,
                            Refinanciamento.Status.EM_ANALISE_RENOVACAO,
                            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                        ],
                        ciclo_destino__isnull=True,
                        data_ativacao_ciclo__isnull=True,
                        executado_em__isnull=True,
                    )
                    .exclude(pk=refinanciamento.pk)
                    .values("id", "status", "origem", "ciclo_destino_id")
                )
                if conflicting_refis:
                    classifications.append("synthetic_conflict")
                    conflicts += len(conflicting_refis)

                if refinanciamento.comprovantes.count() < len(renewal.proofs):
                    classifications.append("missing_proofs")

            if not classifications:
                classifications.append("ok")

            rows.append(
                {
                    "legacy_refinanciamento_id": renewal.legacy_id,
                    "associado_id": associado.id if associado else None,
                    "nome": associado.nome_completo if associado else "",
                    "cpf_cnpj": renewal.cpf_cnpj,
                    "expected_cycle_start": expected_first_reference.isoformat(),
                    "legacy_activation_at": renewal.activation_at.isoformat()
                    if renewal.activation_at
                    else None,
                    "proofs_in_legacy": len(renewal.proofs),
                    "term_in_legacy": renewal.term is not None,
                    "current_refinanciamento_id": refinanciamento.id if refinanciamento else None,
                    "current_status": refinanciamento.status if refinanciamento else "",
                    "current_origem": refinanciamento.origem if refinanciamento else "",
                    "current_cycle_id": refinanciamento.ciclo_destino_id if refinanciamento else None,
                    "current_cycle_start": (
                        refinanciamento.ciclo_destino.data_inicio.isoformat()
                        if refinanciamento and refinanciamento.ciclo_destino_id
                        else None
                    ),
                    "current_proofs": refinanciamento.comprovantes.count() if refinanciamento else 0,
                    "conflicting_refinanciamentos": conflicting_refis,
                    "classifications": classifications,
                }
            )

        payload = {
            "generated_at": datetime.now().isoformat(),
            "legacy_file": str(dump_path),
            "summary": {
                "total_legacy_renewals": len(rows),
                "with_legacy_proofs": sum(1 for item in renewals if item.proofs),
                "missing": missing,
                "cycle_start_mismatch": start_mismatch,
                "synthetic_conflicts": conflicts,
                "status": "ok"
                if missing == 0 and start_mismatch == 0 and conflicts == 0
                else "requires_review",
            },
            "renewals": rows,
        }

        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("audit_legacy_renewals")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Auditadas {payload['summary']['total_legacy_renewals']} renovação(ões) legadas."
            )
        )
        self.stdout.write(f"Relatório: {target}")
