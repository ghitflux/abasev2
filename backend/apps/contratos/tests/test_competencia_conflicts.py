from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal

from django.core.management import call_command

from apps.importacao.tests.base import ImportacaoBaseTestCase

from ..competencia import find_competencia_conflict_groups, repair_conflict_group
from ..models import Ciclo, Contrato, Parcela


class CompetenciaConflictTestCase(ImportacaoBaseTestCase):
    def _create_duplicate_cycle(
        self,
        *,
        associado,
        source_cycle: Ciclo,
        status_primeira_parcela: str = Parcela.Status.EM_ABERTO,
        with_payment: bool = False,
    ) -> tuple[Contrato, Ciclo]:
        self.release_cycle_competencia_locks(source_cycle)
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_primeira_mensalidade=source_cycle.data_inicio,
            data_aprovacao=date(2025, 2, 20),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=source_cycle.numero,
            data_inicio=source_cycle.data_inicio,
            data_fim=source_cycle.data_fim,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2025, 3, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 3, 1),
                    status=status_primeira_parcela,
                    data_pagamento=date(2025, 3, 10) if with_payment else None,
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2025, 4, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 4, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=date(2025, 5, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 5, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )
        return contrato, ciclo

    def test_find_conflict_groups_classifies_exact_duplicate_and_prefers_progress(self):
        associado, _contrato, ciclo = self.create_associado_com_contrato(
            cpf="71000000001",
            nome="Associado Duplicado",
        )
        self._create_duplicate_cycle(associado=associado, source_cycle=ciclo)

        groups = find_competencia_conflict_groups(cpf_cnpj=associado.cpf_cnpj)

        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["classification"], "exact_duplicate_cycle")
        self.assertTrue(group["auto_repairable"])
        self.assertEqual(group["canonical_cycle_id"], ciclo.id)

    def test_find_conflict_groups_marks_manual_when_same_month_has_two_evidenced_parcelas(self):
        associado, _contrato, ciclo = self.create_associado_com_contrato(
            cpf="71000000002",
            nome="Associado Manual",
        )
        self._create_duplicate_cycle(
            associado=associado,
            source_cycle=ciclo,
            status_primeira_parcela=Parcela.Status.DESCONTADO,
            with_payment=True,
        )

        groups = find_competencia_conflict_groups(cpf_cnpj=associado.cpf_cnpj)

        self.assertEqual(len(groups), 1)
        group = groups[0]
        self.assertEqual(group["classification"], "manual_required")
        self.assertFalse(group["auto_repairable"])

    def test_repair_conflict_group_syncs_duplicate_cycle_without_canceling_contract(self):
        associado, _contrato_ativo, ciclo_ativo = self.create_associado_com_contrato(
            cpf="71000000003",
            nome="Associado Reparado",
        )
        contrato_duplicado, ciclo_duplicado = self._create_duplicate_cycle(
            associado=associado,
            source_cycle=ciclo_ativo,
        )
        duplicate_parcela = ciclo_duplicado.parcelas.get(numero=1)

        group = find_competencia_conflict_groups(cpf_cnpj=associado.cpf_cnpj)[0]
        summary = repair_conflict_group(group_id=group["group_id"], execute=True)

        contrato_duplicado.refresh_from_db()
        ciclo_duplicado.refresh_from_db()
        duplicate_parcela.refresh_from_db()

        self.assertEqual(summary["cancelled_cycles"], 0)
        self.assertEqual(summary["cancelled_contracts"], 0)
        self.assertEqual(summary["reassigned_return_items"], 0)
        self.assertEqual(contrato_duplicado.status, Contrato.Status.EM_ANALISE)
        self.assertEqual(ciclo_duplicado.status, Ciclo.Status.ABERTO)
        self.assertEqual(duplicate_parcela.status, ciclo_ativo.parcelas.get(numero=1).status)
        self.assertEqual(
            duplicate_parcela.data_pagamento,
            ciclo_ativo.parcelas.get(numero=1).data_pagamento,
        )

    def test_commands_export_audit_and_dry_run_repair(self):
        associado, _contrato, ciclo = self.create_associado_com_contrato(
            cpf="71000000004",
            nome="Associado Command",
        )
        self._create_duplicate_cycle(associado=associado, source_cycle=ciclo)
        group = find_competencia_conflict_groups(cpf_cnpj=associado.cpf_cnpj)[0]

        audit_stdout = io.StringIO()
        call_command(
            "audit_competencia_conflicts",
            "--cpf",
            associado.cpf_cnpj,
            "--format",
            "json",
            stdout=audit_stdout,
        )
        audit_payload = json.loads(audit_stdout.getvalue())
        self.assertEqual(audit_payload[0]["group_id"], group["group_id"])

        repair_stdout = io.StringIO()
        call_command(
            "repair_competencia_conflicts",
            "--group-id",
            group["group_id"],
            "--format",
            "json",
            stdout=repair_stdout,
        )
        repair_payload = json.loads(repair_stdout.getvalue())
        self.assertEqual(repair_payload["group_id"], group["group_id"])
        self.assertTrue(repair_payload["auto_repairable"])
