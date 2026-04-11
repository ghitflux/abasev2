from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.contratos.manual_cycle_layout_repair import repair_manual_cycle_layouts
from apps.contratos.models import Ciclo, Contrato, Parcela


class ManualCycleLayoutRepairTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.agente = User.objects.create_user(
            email="agente-manual@test.local",
            password="123456",
            first_name="Agente",
            last_name="Manual",
        )

    def test_repair_renumbers_active_rows_even_with_soft_deleted_number_conflict(self):
        associado = Associado.objects.create(
            nome_completo="Associado Manual",
            cpf_cnpj="70000000999",
            email="associado-manual@test.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-MANUAL",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-MANUAL-REPAIR",
            valor_bruto=Decimal("400.00"),
            valor_liquido=Decimal("300.00"),
            valor_mensalidade=Decimal("100.00"),
            prazo_meses=4,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("400.00"),
            comissao_agente=Decimal("30.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 10, 1),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("300.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=4,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("100.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=5,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("100.00"),
            data_vencimento=date(2025, 11, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=6,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("100.00"),
            data_vencimento=date(2025, 12, 1),
            status=Parcela.Status.EM_PREVISAO,
        )
        parcela_soft_deleted = Parcela.all_objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("100.00"),
            data_vencimento=date(2026, 1, 1),
            status=Parcela.Status.CANCELADO,
        )
        parcela_soft_deleted.soft_delete()

        report = repair_manual_cycle_layouts(apply=True, contrato_id=contrato.id)

        numeros_ativos = list(
            Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("numero", "id")
            .values_list("numero", flat=True)
        )
        self.assertEqual(report["changed_contracts"], 1)
        self.assertEqual(numeros_ativos, [1, 2, 3])

    def test_repair_preserves_november_inside_cycle_when_layout_is_explicit(self):
        associado = Associado.objects.create(
            nome_completo="Associado Novembro",
            cpf_cnpj="70000000888",
            email="associado-novembro@test.local",
            telefone="86999999998",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-NOV",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo="CTR-MANUAL-NOV",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("700.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("300.00"),
            comissao_agente=Decimal("30.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 10, 1),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        for numero, referencia in enumerate(
            [date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=(
                    Parcela.Status.DESCONTADO
                    if referencia.month in {10, 11}
                    else Parcela.Status.EM_PREVISAO
                ),
                data_pagamento=referencia if referencia.month in {10, 11} else None,
                layout_bucket=Parcela.LayoutBucket.CYCLE,
                observacao="Mantido no ciclo por override manual.",
            )

        report = repair_manual_cycle_layouts(apply=True, contrato_id=contrato.id)

        parcela_novembro = Parcela.all_objects.get(
            ciclo=ciclo,
            referencia_mes=date(2025, 11, 1),
            deleted_at__isnull=True,
        )
        self.assertEqual(report["changed_contracts"], 0)
        self.assertEqual(parcela_novembro.layout_bucket, Parcela.LayoutBucket.CYCLE)
        self.assertEqual(parcela_novembro.status, Parcela.Status.DESCONTADO)
