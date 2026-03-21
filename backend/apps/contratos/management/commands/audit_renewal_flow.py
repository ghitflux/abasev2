from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Contrato
from apps.refinanciamento.models import Refinanciamento
from core.legacy_dump import LegacyDump, default_legacy_dump_path, parse_date, parse_str


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


def _normalize_document(value: str | None) -> str:
    return "".join(char for char in (value or "") if char.isdigit())


def _pick(row: dict[str, str], *candidates: str) -> str:
    for key in candidates:
        if key in row:
            return row[key]
    return ""


def _legacy_paid_map(dump: LegacyDump | None) -> dict[str, list[str]]:
    if dump is None:
        return {}

    result: dict[str, set[str]] = {}
    for table_name in ("pagamentos_mensalidades", "pagamento_mensalidades"):
        rows = dump.table_rows(table_name)
        if not rows:
            continue
        for row in rows:
            cpf = _normalize_document(
                parse_str(_pick(row, "cpf_cnpj", "cpf", "documento", "cpfcnpj"))
            )
            referencia = parse_date(
                _pick(row, "referencia_month", "referencia", "competencia", "month")
            )
            status_code = parse_str(_pick(row, "status_code", "status", "status_codigo"))
            manual_status = parse_str(_pick(row, "manual_status"))
            if not cpf or referencia is None:
                continue
            if status_code in {"1", "4"} or manual_status == "pago":
                result.setdefault(cpf, set()).add(referencia.strftime("%Y-%m"))
    return {cpf: sorted(values) for cpf, values in result.items()}


def _contract_payload(contrato: Contrato) -> dict[str, object]:
    projection = build_contract_cycle_projection(contrato)
    cycles = list(sorted(projection["cycles"], key=lambda item: item["numero"]))
    current_cycle = cycles[-1] if cycles else None
    return {
        "contrato_id": contrato.id,
        "contrato_codigo": contrato.codigo,
        "prazo_meses": get_contract_cycle_size(contrato),
        "status_contrato": contrato.status,
        "status_renovacao": projection["status_renovacao"],
        "refinanciamento_id": projection["refinanciamento_id"],
        "ciclos_materializados": len(cycles),
        "pagamentos_no_ciclo_atual": (
            [
                parcela["referencia_mes"].strftime("%Y-%m")
                for parcela in current_cycle["parcelas"]
                if parcela["status"] == "descontado"
            ]
            if current_cycle
            else []
        ),
        "ciclo_atual": current_cycle,
        "meses_nao_pagos": [
            item["referencia_mes"].strftime("%Y-%m")
            for item in projection["unpaid_months"]
        ],
        "refinanciamentos": [
            {
                "id": refinanciamento.id,
                "status": refinanciamento.status,
                "competencia_solicitada": (
                    refinanciamento.competencia_solicitada.isoformat()
                    if refinanciamento.competencia_solicitada
                    else None
                ),
                "executado_em": (
                    refinanciamento.executado_em.isoformat()
                    if refinanciamento.executado_em
                    else None
                ),
                "ciclo_origem_id": refinanciamento.ciclo_origem_id,
                "ciclo_destino_id": refinanciamento.ciclo_destino_id,
            }
            for refinanciamento in contrato.refinanciamentos.order_by("created_at", "id")
        ],
    }


class Command(BaseCommand):
    help = "Audita o fluxo global de renovação comparando o canônico atual com o dump legado quando disponível."

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--file",
            dest="legacy_file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado opcional usado para apoio na auditoria.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        legacy_path = Path(options["legacy_file"])
        dump = LegacyDump.from_file(legacy_path) if legacy_path.exists() else None
        legacy_paid_by_cpf = _legacy_paid_map(dump)

        queryset = Associado.objects.prefetch_related(
            "contratos__ciclos__parcelas",
            "contratos__refinanciamentos",
            "refinanciamentos",
            "tesouraria_pagamentos",
            "pagamentos_mensalidades",
        ).order_by("nome_completo", "id")
        cpf = options.get("cpf")
        if cpf:
            queryset = queryset.filter(cpf_cnpj=cpf)

        associados_payload: list[dict[str, object]] = []
        divergencias = 0
        for associado in queryset:
            contratos = list(
                associado.contratos.exclude(status=Contrato.Status.CANCELADO).order_by(
                    "created_at",
                    "id",
                )
            )
            if not contratos:
                continue

            current_paid = sorted(
                {
                    referencia
                    for contrato in contratos
                    for referencia in _contract_payload(contrato)["pagamentos_no_ciclo_atual"]
                }
            )
            legacy_paid = legacy_paid_by_cpf.get(_normalize_document(associado.cpf_cnpj), [])
            classification = "ok"
            detail = ""
            if legacy_paid and not set(current_paid).issubset(set(legacy_paid)):
                classification = "divergente"
                detail = "Pagamentos do canônico não estão contidos no legado."
                divergencias += 1

            associados_payload.append(
                {
                    "associado_id": associado.id,
                    "nome": associado.nome_completo,
                    "cpf_cnpj": associado.cpf_cnpj,
                    "status": associado.status,
                    "classification": classification,
                    "detail": detail,
                    "legacy_paid_refs": legacy_paid,
                    "contracts": [_contract_payload(contrato) for contrato in contratos],
                }
            )

        payload = {
            "generated_at": datetime.now().isoformat(),
            "legacy_file": str(legacy_path) if dump else None,
            "summary": {
                "total_associados": len(associados_payload),
                "divergencias": divergencias,
                "status": "ok" if divergencias == 0 else "requires_review",
            },
            "associados": associados_payload,
        }

        target = Path(options["report_json"]) if options.get("report_json") else _default_report_path("audit_renewal_flow")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Auditados {payload['summary']['total_associados']} associado(s)."
            )
        )
        self.stdout.write(
            f"Divergências: {payload['summary']['divergencias']} | Relatório: {target}"
        )
