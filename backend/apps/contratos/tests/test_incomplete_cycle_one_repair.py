from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.contratos.incomplete_cycle_one_repair import repair_incomplete_cycle_one
from apps.contratos.models import Ciclo, Contrato, Parcela


class IncompleteCycleOneRepairTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.agente = User.objects.create_user(
            email="agente-ciclo1@test.local",
            password="123456",
            first_name="Agente",
            last_name="Ciclo1",
        )

    def _create_associado(self, cpf: str) -> Associado:
        return Associado.objects.create(
            nome_completo=f"Associado {cpf}",
            cpf_cnpj=cpf,
            email=f"{cpf}@test.local",
            telefone="86999999999",
            orgao_publico="PM",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )

    def test_move_primeira_parcela_resolvida_do_ciclo_seguinte_para_completar_ciclo_um(self):
        associado = self._create_associado("45125260304")
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-CICLO1-MOVE",
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("600.00"),
            valor_mensalidade=Decimal("200.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("600.00"),
            valor_total_antecipacao=Decimal("600.00"),
            comissao_agente=Decimal("60.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 31),
            data_aprovacao=date(2025, 10, 31),
            data_primeira_mensalidade=date(2025, 12, 1),
            mes_averbacao=date(2025, 12, 1),
            admin_manual_layout_enabled=True,
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 12, 1),
            data_fim=date(2026, 1, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("400.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 5, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("600.00"),
        )
        for number, ref in enumerate([date(2025, 12, 1), date(2026, 1, 1)], start=1):
            Parcela.objects.create(
                ciclo=ciclo_1,
                associado=associado,
                numero=number,
                referencia_mes=ref,
                valor=Decimal("200.00"),
                data_vencimento=ref,
                status=Parcela.Status.DESCONTADO,
                layout_bucket=Parcela.LayoutBucket.CYCLE,
                data_pagamento=ref,
            )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("200.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.CYCLE,
            data_pagamento=date(2026, 2, 1),
        )
        for number, ref in enumerate([date(2026, 4, 1), date(2026, 5, 1)], start=2):
            Parcela.objects.create(
                ciclo=ciclo_2,
                associado=associado,
                numero=number,
                referencia_mes=ref,
                valor=Decimal("200.00"),
                data_vencimento=ref,
                status=Parcela.Status.EM_PREVISAO,
                layout_bucket=Parcela.LayoutBucket.CYCLE,
            )

        payload = repair_incomplete_cycle_one(apply=True)

        self.assertEqual(payload["candidate_contracts"], 1)
        self.assertEqual(payload["moved_contracts"], 1)
        self.assertEqual(payload["downgraded_to_pending"], 0)
        self.assertEqual(payload["remaining_invalid_completed_cycle_one"], 0)

        refs_ciclo_1 = list(
            Parcela.all_objects.filter(ciclo=ciclo_1, deleted_at__isnull=True, layout_bucket=Parcela.LayoutBucket.CYCLE)
            .order_by("numero")
            .values_list("referencia_mes", flat=True)
        )
        refs_ciclo_2 = list(
            Parcela.all_objects.filter(ciclo=ciclo_2, deleted_at__isnull=True, layout_bucket=Parcela.LayoutBucket.CYCLE)
            .order_by("numero")
            .values_list("referencia_mes", flat=True)
        )
        self.assertEqual(refs_ciclo_1, [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)])
        self.assertEqual(refs_ciclo_2, [date(2026, 4, 1), date(2026, 5, 1)])

    def test_downgrade_ciclo_um_para_pendencia_quando_nao_ha_parcela_resolvida_para_puxar(self):
        associado = self._create_associado("74274274274")
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-CICLO1-PEND",
            valor_bruto=Decimal("600.00"),
            valor_liquido=Decimal("200.00"),
            valor_mensalidade=Decimal("200.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("200.00"),
            valor_total_antecipacao=Decimal("200.00"),
            comissao_agente=Decimal("20.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 4, 9),
            data_aprovacao=date(2026, 4, 9),
            data_primeira_mensalidade=date(2026, 2, 1),
            mes_averbacao=date(2026, 2, 1),
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 2, 1),
            status=Ciclo.Status.FECHADO,
            valor_total=Decimal("200.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("200.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.CYCLE,
            data_pagamento=date(2026, 2, 1),
        )

        payload = repair_incomplete_cycle_one(apply=True)

        self.assertEqual(payload["candidate_contracts"], 1)
        self.assertEqual(payload["moved_contracts"], 0)
        self.assertEqual(payload["downgraded_to_pending"], 1)
        ciclo_1.refresh_from_db()
        self.assertEqual(ciclo_1.status, Ciclo.Status.PENDENCIA)
