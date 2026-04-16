from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.models import Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento


def _default_report_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "auditorias"
        / f"missing_agent_payment_proofs_{timestamp}.json"
    )


def _proof_payload(comprovante: Comprovante | None) -> dict[str, object] | None:
    if comprovante is None:
        return None
    return {
        "id": comprovante.id,
        "tipo": comprovante.tipo,
        "papel": comprovante.papel,
        "nome_original": comprovante.nome_original,
        "arquivo_referencia": comprovante.arquivo_referencia,
        "data_pagamento": comprovante.data_pagamento.isoformat()
        if comprovante.data_pagamento
        else None,
        "created_at": comprovante.created_at.isoformat()
        if comprovante.created_at
        else None,
        "updated_at": comprovante.updated_at.isoformat()
        if comprovante.updated_at
        else None,
    }


class Command(BaseCommand):
    help = (
        "Audita contratos efetivados e renovações efetivadas/concluídas com "
        "comprovante do associado, mas sem comprovante do agente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional para salvar o relatório JSON.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Limita a quantidade de registros listados por categoria.",
        )

    def handle(self, *args, **options):
        contract_rows = self._collect_contract_rows(limit=options["limit"] or None)
        renewal_rows = self._collect_renewal_rows(limit=options["limit"] or None)
        payload = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "contracts_missing_agent_proof": len(contract_rows),
                "renewals_missing_agent_proof": len(renewal_rows),
                "total": len(contract_rows) + len(renewal_rows),
            },
            "contracts": contract_rows,
            "renewals": renewal_rows,
        }

        target = (
            Path(options["report_json"]).expanduser()
            if options.get("report_json")
            else _default_report_path()
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Auditoria concluída: "
                f"{payload['summary']['contracts_missing_agent_proof']} contrato(s) e "
                f"{payload['summary']['renewals_missing_agent_proof']} renovação(ões) "
                "sem comprovante do agente."
            )
        )
        self.stdout.write(f"Relatório: {target}")

    def _latest_contract_proof(
        self,
        contrato: Contrato,
        *,
        papel: str,
        tipo: str,
    ) -> Comprovante | None:
        return (
            contrato.comprovantes.filter(
                refinanciamento__isnull=True,
                deleted_at__isnull=True,
                papel=papel,
                tipo=tipo,
            )
            .order_by("-updated_at", "-created_at", "-id")
            .first()
        )

    def _latest_renewal_proof(
        self,
        refinanciamento: Refinanciamento,
        *,
        papel: str,
        tipo: str,
    ) -> Comprovante | None:
        return (
            refinanciamento.comprovantes.filter(
                deleted_at__isnull=True,
                papel=papel,
                tipo=tipo,
            )
            .order_by("-updated_at", "-created_at", "-id")
            .first()
        )

    def _collect_contract_rows(self, *, limit: int | None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        queryset = (
            Contrato.objects.select_related("associado", "agente")
            .prefetch_related("comprovantes")
            .filter(auxilio_liberado_em__isnull=False)
            .order_by("-auxilio_liberado_em", "-id")
        )

        for contrato in queryset:
            comprovante_associado = self._latest_contract_proof(
                contrato,
                papel=Comprovante.Papel.ASSOCIADO,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            )
            comprovante_agente = self._latest_contract_proof(
                contrato,
                papel=Comprovante.Papel.AGENTE,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            )
            if comprovante_associado is None or comprovante_agente is not None:
                continue
            rows.append(
                {
                    "contrato_id": contrato.id,
                    "contrato_codigo": contrato.codigo,
                    "status": contrato.status,
                    "auxilio_liberado_em": contrato.auxilio_liberado_em.isoformat()
                    if contrato.auxilio_liberado_em
                    else None,
                    "associado": {
                        "id": contrato.associado_id,
                        "nome": contrato.associado.nome_completo,
                        "cpf_cnpj": contrato.associado.cpf_cnpj,
                        "status": contrato.associado.status,
                    },
                    "agente_nome": contrato.agente.full_name if contrato.agente else "",
                    "comprovante_associado": _proof_payload(comprovante_associado),
                    "comprovante_agente": None,
                }
            )
            if limit and len(rows) >= limit:
                break
        return rows

    def _collect_renewal_rows(self, *, limit: int | None) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        queryset = (
            Refinanciamento.objects.select_related(
                "associado",
                "contrato_origem",
                "contrato_origem__agente",
            )
            .prefetch_related("comprovantes")
            .filter(
                status__in=[
                    Refinanciamento.Status.EFETIVADO,
                    Refinanciamento.Status.CONCLUIDO,
                ]
            )
            .order_by("-executado_em", "-updated_at", "-id")
        )

        for refinanciamento in queryset:
            comprovante_associado = self._latest_renewal_proof(
                refinanciamento,
                papel=Comprovante.Papel.ASSOCIADO,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            )
            comprovante_agente = self._latest_renewal_proof(
                refinanciamento,
                papel=Comprovante.Papel.AGENTE,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            )
            if comprovante_associado is None or comprovante_agente is not None:
                continue
            rows.append(
                {
                    "refinanciamento_id": refinanciamento.id,
                    "status": refinanciamento.status,
                    "executado_em": refinanciamento.executado_em.isoformat()
                    if refinanciamento.executado_em
                    else None,
                    "contrato_codigo": refinanciamento.contrato_origem.codigo
                    if refinanciamento.contrato_origem
                    else "",
                    "associado": {
                        "id": refinanciamento.associado_id,
                        "nome": refinanciamento.associado.nome_completo,
                        "cpf_cnpj": refinanciamento.associado.cpf_cnpj,
                        "status": refinanciamento.associado.status,
                    },
                    "agente_nome": (
                        refinanciamento.contrato_origem.agente.full_name
                        if refinanciamento.contrato_origem
                        and refinanciamento.contrato_origem.agente
                        else refinanciamento.agente_snapshot
                    ),
                    "comprovante_associado": _proof_payload(comprovante_associado),
                    "comprovante_agente": None,
                }
            )
            if limit and len(rows) >= limit:
                break
        return rows
