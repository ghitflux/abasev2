from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.tesouraria.initial_payment import build_initial_payment_payload, get_initial_payment_for_contract
from apps.tesouraria.legacy_initial_payments import (
    load_initial_payment_overrides,
    load_legacy_initial_payments,
    merge_initial_payment_overrides,
)
from core.legacy_dump import LegacyDump, default_legacy_dump_path


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


def _same_decimal(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None and right is None:
        return True
    return left == right


class Command(BaseCommand):
    help = "Audita a evidência do pagamento inicial entre legado, banco atual e storage local."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado.",
        )
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--overrides",
            help="Arquivo JSON/CSV com pagamentos mais novos que o dump.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional para o relatório JSON.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        dump = LegacyDump.from_file(dump_path)
        records = load_legacy_initial_payments(dump, cpf_filter=options.get("cpf"))
        overrides = load_initial_payment_overrides(options.get("overrides"))
        if overrides:
            records = merge_initial_payment_overrides(records, overrides)
        if not records:
            raise CommandError("Nenhum pagamento inicial legado encontrado para auditoria.")

        rows = [self._audit_record(record) for record in records]
        summary = {
            "records": len(rows),
            "ok_arquivo_local": sum(1 for row in rows if row["classification"] == "ok_arquivo_local"),
            "ok_referencia_legado": sum(1 for row in rows if row["classification"] == "ok_referencia_legado"),
            "ok_placeholder_recebido": sum(1 for row in rows if row["classification"] == "ok_placeholder_recebido"),
            "sem_pagamento_inicial": sum(1 for row in rows if row["classification"] == "sem_pagamento_inicial"),
            "pagamento_sem_evidencia": sum(1 for row in rows if row["classification"] == "pagamento_sem_evidencia"),
            "divergencia_valor": sum(1 for row in rows if row["classification"] == "divergencia_valor"),
            "divergencia_data": sum(1 for row in rows if row["classification"] == "divergencia_data"),
        }
        payload = {
            "generated_at": datetime.now().isoformat(),
            "legacy_file": str(dump_path),
            "summary": summary,
            "payments": rows,
        }
        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("audit_initial_payment_evidence")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Auditoria concluída: {summary['records']} pagamento(s) avaliados."
            )
        )
        self.stdout.write(f"Relatório: {target}")

    def _resolve_associado(self, cpf_cnpj: str) -> Associado | None:
        return Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).first()

    def _resolve_contrato(self, contrato_codigo: str, associado: Associado | None) -> Contrato | None:
        contrato = Contrato.all_objects.filter(codigo=contrato_codigo).first()
        if contrato is not None:
            return contrato
        if associado is None:
            return None
        return (
            Contrato.all_objects.filter(associado=associado)
            .exclude(status=Contrato.Status.CANCELADO)
            .order_by("created_at", "id")
            .first()
        )

    def _audit_record(self, record):
        associado = self._resolve_associado(record.cpf_cnpj)
        contrato = self._resolve_contrato(record.contrato_codigo, associado)
        if associado is None or contrato is None:
            return {
                "legacy_payment_id": record.legacy_id,
                "cpf_cnpj": record.cpf_cnpj,
                "contrato_codigo": record.contrato_codigo,
                "classification": "sem_pagamento_inicial",
            }

        pagamento = get_initial_payment_for_contract(contrato)
        if pagamento is None:
            return {
                "legacy_payment_id": record.legacy_id,
                "cpf_cnpj": record.cpf_cnpj,
                "contrato_codigo": contrato.codigo,
                "classification": "sem_pagamento_inicial",
            }

        payload = build_initial_payment_payload(contrato)
        expected_value = record.valor_pago or record.contrato_margem_disponivel
        if not _same_decimal(pagamento.valor_pago or pagamento.contrato_margem_disponivel, expected_value):
            classification = "divergencia_valor"
        elif record.paid_at and pagamento.paid_at and pagamento.paid_at != record.paid_at:
            classification = "divergencia_data"
        elif payload.evidencia_status == "arquivo_local":
            classification = "ok_arquivo_local"
        elif payload.evidencia_status == "referencia_legado":
            classification = "ok_referencia_legado"
        elif payload.evidencia_status == "placeholder_recebido":
            classification = "ok_placeholder_recebido"
        elif pagamento.status == pagamento.Status.PAGO:
            classification = "pagamento_sem_evidencia"
        else:
            classification = "sem_pagamento_inicial"

        return {
            "legacy_payment_id": record.legacy_id,
            "cpf_cnpj": record.cpf_cnpj,
            "contrato_codigo": contrato.codigo,
            "pagamento_id": pagamento.id,
            "classification": classification,
            "status_atual": pagamento.status,
            "valor_atual": pagamento.valor_pago or pagamento.contrato_margem_disponivel,
            "paid_at_atual": pagamento.paid_at,
            "evidencia_status": payload.evidencia_status,
        }
