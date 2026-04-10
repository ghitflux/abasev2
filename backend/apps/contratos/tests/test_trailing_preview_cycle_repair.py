from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.trailing_preview_cycle_repair import repair_trailing_preview_cycles
from apps.refinanciamento.models import Comprovante, Refinanciamento


class TrailingPreviewCycleRepairTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.agente = User.objects.create_user(
            email="agente-preview@test.local",
            password="123456",
            first_name="Agente",
            last_name="Preview",
        )

    def _create_contract(self) -> tuple[Contrato, Ciclo, Ciclo, Ciclo]:
        associado = Associado.objects.create(
            nome_completo="Justino Teste",
            cpf_cnpj="45125260304",
            email="justino@test.local",
            telefone="86999999999",
            orgao_publico="PM",
            matricula_orgao="MAT-JUSTINO",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-JUSTINO-TESTE",
            valor_bruto=Decimal("1881.03"),
            valor_liquido=Decimal("735.00"),
            valor_mensalidade=Decimal("350.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("735.00"),
            valor_total_antecipacao=Decimal("1050.00"),
            comissao_agente=Decimal("73.50"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 9, 2),
            data_aprovacao=date(2025, 9, 2),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 9, 6),
            admin_manual_layout_enabled=True,
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1050.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1050.00"),
        )
        ciclo_3 = Ciclo.objects.create(
            contrato=contrato,
            numero=3,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("350.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.CYCLE,
            data_pagamento=date(2025, 10, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 11, 1),
            status=Parcela.Status.NAO_DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.UNPAID,
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 12, 1),
            status="quitada",
            layout_bucket=Parcela.LayoutBucket.UNPAID,
            data_pagamento=date(2026, 1, 12),
        )
        for number, ref in enumerate([date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)], start=1):
            Parcela.objects.create(
                ciclo=ciclo_2,
                associado=associado,
                numero=number,
                referencia_mes=ref,
                valor=Decimal("350.00"),
                data_vencimento=ref,
                status=Parcela.Status.DESCONTADO,
                layout_bucket=Parcela.LayoutBucket.CYCLE,
                data_pagamento=ref,
            )
        Parcela.objects.create(
            ciclo=ciclo_3,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 4, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2026, 4, 1),
            status=Parcela.Status.EM_PREVISAO,
            layout_bucket=Parcela.LayoutBucket.CYCLE,
        )
        pending = Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            valor_refinanciamento=Decimal("735.00"),
            repasse_agente=Decimal("73.50"),
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2026-01|2026-02|2026-03",
            ciclo_origem=ciclo_2,
        )
        Comprovante.objects.create(
            refinanciamento=pending,
            contrato=contrato,
            ciclo=ciclo_2,
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.AGENTE,
            origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            arquivo="ANTECIPACAO-JUSTINO.pdf",
            arquivo_referencia_path="ANTECIPACAO-JUSTINO.pdf",
            nome_original="ANTECIPACAO-JUSTINO.pdf",
            enviado_por=self.agente,
        )
        pending.soft_delete()
        return contrato, ciclo_1, ciclo_2, ciclo_3

    def test_repair_collapses_trailing_april_cycle_and_restores_pending_operational(self):
        contrato, ciclo_1, ciclo_2, ciclo_3 = self._create_contract()

        payload = repair_trailing_preview_cycles(apply=True)

        self.assertEqual(payload["candidate_contracts"], 1)
        self.assertEqual(payload["corrected_contracts"], 1)
        self.assertEqual(payload["remaining_candidates"], 0)
        self.assertEqual(payload["restored_approved_operational"], 1)

        ciclos_ativos = list(
            Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True).order_by("numero")
        )
        self.assertEqual([ciclo.numero for ciclo in ciclos_ativos], [1, 2])

        refs_ciclo_1 = list(
            Parcela.all_objects.filter(ciclo=ciclo_1, deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .filter(layout_bucket=Parcela.LayoutBucket.CYCLE)
            .order_by("referencia_mes", "numero")
            .values_list("referencia_mes", flat=True)
        )
        refs_ciclo_2 = list(
            Parcela.all_objects.filter(ciclo=ciclo_2, deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .filter(layout_bucket=Parcela.LayoutBucket.CYCLE)
            .order_by("referencia_mes", "numero")
            .values_list("referencia_mes", flat=True)
        )
        self.assertEqual(
            refs_ciclo_1,
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 1, 1)],
        )
        self.assertEqual(
            refs_ciclo_2,
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )

        self.assertFalse(
            Ciclo.objects.filter(pk=ciclo_3.pk, deleted_at__isnull=True).exists()
        )

        operational = Refinanciamento.objects.get(
            contrato_origem=contrato,
            origem=Refinanciamento.Origem.OPERACIONAL,
            deleted_at__isnull=True,
        )
        self.assertEqual(operational.status, Refinanciamento.Status.APROVADO_PARA_RENOVACAO)
        self.assertEqual(operational.ciclo_origem_id, ciclo_2.id)
        self.assertEqual(operational.cycle_key, "2026-02|2026-03|2026-04")
        self.assertTrue(
            operational.comprovantes.filter(
                tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
                deleted_at__isnull=True,
            ).exists()
        )
