from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.initial_payment import get_initial_payment_for_contract


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
    help = "Backfill de datas de ativação para refinanciamentos e comprovantes já sincronizados."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica alterações no banco. Sem esta flag, executa dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional para o relatório JSON.",
        )

    def handle(self, *args, **options):
        execute = bool(options["execute"])
        cpf = options.get("cpf")

        refinanciamentos = Refinanciamento.all_objects.select_related(
            "associado",
            "contrato_origem",
        ).order_by("id")
        comprovantes = Comprovante.all_objects.select_related(
            "refinanciamento",
            "contrato",
        ).order_by("id")

        if cpf:
            refinanciamentos = refinanciamentos.filter(associado__cpf_cnpj=cpf)
            comprovantes = comprovantes.filter(
                Q(contrato__associado__cpf_cnpj=cpf)
                | Q(refinanciamento__associado__cpf_cnpj=cpf)
            )

        refi_updates = []
        comprovante_updates = []

        for refinanciamento in refinanciamentos:
            reference_at = (
                refinanciamento.data_ativacao_ciclo
                or refinanciamento.executado_em
                or refinanciamento.created_at
            )
            if reference_at is None:
                continue
            if (
                refinanciamento.created_at != reference_at
                or refinanciamento.updated_at != reference_at
            ):
                refi_updates.append(
                    {
                        "id": refinanciamento.id,
                        "legacy_refinanciamento_id": refinanciamento.legacy_refinanciamento_id,
                        "cpf_cnpj": refinanciamento.associado.cpf_cnpj,
                        "from_created_at": refinanciamento.created_at,
                        "to_created_at": reference_at,
                    }
                )
                if execute:
                    Refinanciamento.all_objects.filter(pk=refinanciamento.pk).update(
                        created_at=reference_at,
                        updated_at=reference_at,
                    )

        for comprovante in comprovantes:
            reference_at = None
            if comprovante.refinanciamento_id:
                reference_at = (
                    getattr(comprovante.refinanciamento, "data_ativacao_ciclo", None)
                    or getattr(comprovante.refinanciamento, "executado_em", None)
                    or getattr(comprovante.refinanciamento, "created_at", None)
                )
            if reference_at is None:
                reference_at = comprovante.data_pagamento
            if reference_at is None and comprovante.contrato_id:
                pagamento = get_initial_payment_for_contract(comprovante.contrato)
                reference_at = (
                    comprovante.data_pagamento
                    or (pagamento.paid_at if pagamento is not None else None)
                    or (pagamento.created_at if pagamento is not None else None)
                    or comprovante.created_at
                )
            if reference_at is None:
                continue
            if comprovante.created_at != reference_at or comprovante.updated_at != reference_at:
                comprovante_updates.append(
                    {
                        "id": comprovante.id,
                        "contrato_id": comprovante.contrato_id,
                        "refinanciamento_id": comprovante.refinanciamento_id,
                        "tipo": comprovante.tipo,
                        "papel": comprovante.papel,
                        "from_created_at": comprovante.created_at,
                        "to_created_at": reference_at,
                    }
                )
                if execute:
                    Comprovante.all_objects.filter(pk=comprovante.pk).update(
                        created_at=reference_at,
                        updated_at=reference_at,
                    )

        payload = {
            "generated_at": datetime.now().isoformat(),
            "mode": "execute" if execute else "dry-run",
            "summary": {
                "refinanciamentos_updated": len(refi_updates),
                "comprovantes_updated": len(comprovante_updates),
            },
            "refinanciamentos": refi_updates,
            "comprovantes": comprovante_updates,
        }

        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("backfill_activation_reference_timestamps")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill concluído em modo {payload['mode']}."
            )
        )
        self.stdout.write(f"Relatório: {target}")
