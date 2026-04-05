from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command

from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.manual_payment_flags import (
    MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE,
    MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE,
)
from apps.importacao.models import PagamentoMensalidade

from .base import ImportacaoBaseTestCase


class RepairMaristelaCycleMembershipCommandTestCase(ImportacaoBaseTestCase):
    def _run_command(self, *args: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            call_command(
                "repair_maristela_cycle_membership",
                *args,
                "--sheet-file",
                "anexos_legado/Conciliacao/planilha_manual_maristela.xlsx",
                "--report-json",
                str(report_path),
            )
            return json.loads(report_path.read_text(encoding="utf-8"))

    def _create_contract(
        self,
        *,
        cpf: str,
        status_associado: str,
        codigo: str,
        data_primeira_mensalidade: date,
        referencias: list[tuple[date, str]],
        mensalidade: Decimal = Decimal("100.00"),
    ) -> tuple[Associado, Contrato]:
        associado = Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=status_associado,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=codigo,
            valor_bruto=Decimal("400.00"),
            valor_liquido=Decimal("300.00"),
            valor_mensalidade=mensalidade,
            prazo_meses=4,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("400.00"),
            comissao_agente=Decimal("30.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=data_primeira_mensalidade,
            data_aprovacao=data_primeira_mensalidade,
            data_primeira_mensalidade=data_primeira_mensalidade,
            mes_averbacao=data_primeira_mensalidade,
            auxilio_liberado_em=data_primeira_mensalidade,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=referencias[0][0],
            data_fim=referencias[-1][0],
            status=Ciclo.Status.ABERTO,
            valor_total=mensalidade * Decimal(str(len(referencias))),
        )
        for numero, (referencia, status) in enumerate(referencias, start=1):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=mensalidade,
                data_vencimento=referencia,
                status=status,
                data_pagamento=referencia if status == Parcela.Status.DESCONTADO else None,
            )
        return associado, contrato

    def test_execute_moves_manual_march_back_into_cycle_and_updates_status(self):
        associado, contrato = self._create_contract(
            cpf="70000000001",
            status_associado=Associado.Status.INADIMPLENTE,
            codigo="CTR-MAR-0001",
            data_primeira_mensalidade=date(2025, 12, 1),
            referencias=[
                (date(2025, 12, 1), Parcela.Status.DESCONTADO),
                (date(2026, 1, 1), Parcela.Status.DESCONTADO),
                (date(2026, 2, 1), Parcela.Status.DESCONTADO),
                (date(2026, 3, 1), Parcela.Status.EM_ABERTO),
            ],
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="mar-old-manual",
            referencia_month=date(2026, 3, 1),
            status_code="M",
            matricula=associado.matricula_orgao,
            orgao_pagto="SEDUC",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            recebido_manual=Decimal("100.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=self.make_aware(date(2026, 3, 1)),
            manual_forma_pagamento="conciliacao_planilha_maristela",
            source_file_path="planilhas/maristela.xlsx",
        )

        rebuild_contract_cycle_state(contrato, execute=True)
        self.assertFalse(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=date(2026, 3, 1),
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .exists()
        )
        self.assertTrue(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=date(2026, 4, 1),
                deleted_at__isnull=True,
            ).exists()
        )

        payload = self._run_command("--execute", "--cpf", associado.cpf_cnpj)

        associado.refresh_from_db()
        pagamento = PagamentoMensalidade.objects.get(associado=associado, referencia_month=date(2026, 3, 1))
        projection = build_contract_cycle_projection(contrato)
        march_parcelas = list(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=date(2026, 3, 1),
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
        )

        self.assertEqual(payload["summary"]["repaired"], 1)
        self.assertEqual(payload["results"][0]["classification"], "repaired")
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(len(march_parcelas), 1)
        self.assertEqual(march_parcelas[0].status, Parcela.Status.DESCONTADO)
        self.assertFalse(
            any(
                row["referencia_mes"] == date(2026, 3, 1)
                for row in projection["movimentos_financeiros_avulsos"]
            )
        )
        self.assertTrue(
            any(
                parcela["referencia_mes"] == date(2026, 3, 1)
                for ciclo in projection["cycles"]
                for parcela in ciclo["parcelas"]
            )
        )
        self.assertFalse(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=date(2026, 4, 1),
                deleted_at__isnull=True,
            ).exists()
        )
        self.assertEqual(
            pagamento.manual_forma_pagamento,
            MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE,
        )

    def test_execute_forces_november_outside_cycle_and_does_not_reactivate_inactive(self):
        associado, contrato = self._create_contract(
            cpf="70000000002",
            status_associado=Associado.Status.INATIVO,
            codigo="CTR-NOV-0002",
            data_primeira_mensalidade=date(2025, 10, 1),
            referencias=[
                (date(2025, 10, 1), Parcela.Status.DESCONTADO),
                (date(2025, 11, 1), Parcela.Status.DESCONTADO),
                (date(2025, 12, 1), Parcela.Status.EM_ABERTO),
                (date(2026, 1, 1), Parcela.Status.EM_PREVISAO),
            ],
        )

        payload = self._run_command("--execute", "--cpf", associado.cpf_cnpj)

        associado.refresh_from_db()
        projection = build_contract_cycle_projection(contrato)
        novembro_pagamento = PagamentoMensalidade.objects.get(
            associado=associado,
            referencia_month=date(2025, 11, 1),
        )

        self.assertEqual(payload["summary"]["repaired"], 1)
        self.assertEqual(payload["results"][0]["classification"], "repaired")
        self.assertEqual(associado.status, Associado.Status.INATIVO)
        self.assertFalse(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes=date(2025, 11, 1),
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .exists()
        )
        self.assertTrue(
            any(
                row["referencia_mes"] == date(2025, 11, 1)
                and str(row.get("status")) == "quitada"
                for row in projection["unpaid_months"]
            )
        )
        self.assertFalse(
            any(
                parcela["referencia_mes"] == date(2025, 11, 1)
                for ciclo in projection["cycles"]
                for parcela in ciclo["parcelas"]
            )
        )
        self.assertEqual(
            novembro_pagamento.manual_forma_pagamento,
            MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE,
        )

    def make_aware(self, value: date):
        from django.utils import timezone
        from datetime import datetime, time

        return timezone.make_aware(datetime.combine(value, time(12, 0)))
