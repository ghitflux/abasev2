from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.pre_october_cycle_repair import repair_contract_pre_october_cycles
from apps.importacao.models import PagamentoMensalidade
from apps.importacao.tests.base import ImportacaoBaseTestCase


class RepairPreOctoberCyclesCommandTestCase(ImportacaoBaseTestCase):
    def _run_command(self, *args: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            call_command(
                "repair_pre_october_cycles",
                *args,
                "--report-json",
                str(report_path),
            )
            return json.loads(report_path.read_text(encoding="utf-8"))

    def _create_payment(
        self,
        *,
        associado: Associado,
        referencia: date,
        status_code: str,
        valor: Decimal,
        manual_status: str | None = None,
    ) -> None:
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid=f"{associado.cpf_cnpj}-{referencia.isoformat()}-{status_code}",
            referencia_month=referencia,
            status_code=status_code,
            manual_status=manual_status,
            matricula=associado.matricula_orgao,
            orgao_pagto=associado.orgao_publico,
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=valor,
            source_file_path="retornos/teste.txt",
        )

    def test_command_repairs_non_manual_contract_and_removes_pre_october_refs(self):
        associado = Associado.objects.create(
            nome_completo="Associado Setembro",
            cpf_cnpj="71000000101",
            email="setembro@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-101",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("1800.00"),
            valor_liquido=Decimal("1800.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=6,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("1800.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 8, 8),
            data_aprovacao=date(2025, 8, 8),
            data_primeira_mensalidade=date(2025, 10, 6),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 8, 8),
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 9, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("900.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 9, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 9, 1),
            status=Parcela.Status.EM_PREVISAO,
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 12, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 12, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 1, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 1, 5),
        )

        self._create_payment(
            associado=associado,
            referencia=date(2025, 10, 1),
            status_code="1",
            valor=Decimal("300.00"),
        )
        self._create_payment(
            associado=associado,
            referencia=date(2025, 11, 1),
            status_code="2",
            valor=Decimal("300.00"),
        )
        self._create_payment(
            associado=associado,
            referencia=date(2025, 12, 1),
            status_code="1",
            valor=Decimal("300.00"),
        )
        self._create_payment(
            associado=associado,
            referencia=date(2026, 1, 1),
            status_code="1",
            valor=Decimal("300.00"),
        )

        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=date(2025, 10, 1),
            force_candidate=True,
            execute=True,
        )

        contrato.refresh_from_db()
        refs = list(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("referencia_mes", "ciclo__numero", "numero")
            .values_list("referencia_mes", "ciclo__numero", "numero", "status")
        )

        self.assertTrue(result["applied"])
        self.assertEqual(
            refs,
            [
                (date(2025, 10, 1), 1, 1, Parcela.Status.DESCONTADO),
                (date(2025, 11, 1), 1, 2, Parcela.Status.NAO_DESCONTADO),
                (date(2025, 12, 1), 1, 3, Parcela.Status.DESCONTADO),
                (date(2026, 1, 1), 2, 1, Parcela.Status.DESCONTADO),
            ],
        )
        self.assertFalse(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
                referencia_mes__lt=date(2025, 10, 1),
            ).exclude(status=Parcela.Status.CANCELADO).exists()
        )
        self.assertEqual(contrato.data_primeira_mensalidade, date(2025, 10, 1))
        self.assertEqual(contrato.data_aprovacao, date(2025, 9, 1))

    def test_command_repairs_manual_contract_preserving_manual_flag(self):
        associado = Associado.objects.create(
            nome_completo="Associado Manual",
            cpf_cnpj="71000000102",
            email="manual@teste.local",
            telefone="86999999998",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-102",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("1050.00"),
            valor_liquido=Decimal("1050.00"),
            valor_mensalidade=Decimal("350.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("350.00"),
            valor_total_antecipacao=Decimal("1050.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 8, 11),
            data_aprovacao=date(2025, 8, 11),
            data_primeira_mensalidade=date(2025, 10, 6),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 8, 11),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 9, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1050.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 9, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 9, 1),
            status=Parcela.Status.EM_PREVISAO,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        self._create_payment(
            associado=associado,
            referencia=date(2025, 10, 1),
            status_code="1",
            valor=Decimal("350.00"),
        )
        self._create_payment(
            associado=associado,
            referencia=date(2025, 11, 1),
            status_code="2",
            valor=Decimal("350.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
        )
        self._create_payment(
            associado=associado,
            referencia=date(2025, 12, 1),
            status_code="1",
            valor=Decimal("350.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
        )

        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=date(2025, 10, 1),
            force_candidate=True,
            execute=True,
        )

        contrato.refresh_from_db()
        refs = list(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("referencia_mes", "ciclo__numero", "numero")
            .values_list("referencia_mes", "status")
        )

        self.assertTrue(result["applied"])
        self.assertTrue(contrato.admin_manual_layout_enabled)
        self.assertEqual(
            refs,
            [
                (date(2025, 10, 1), Parcela.Status.DESCONTADO),
                (date(2025, 11, 1), "quitada"),
                (date(2025, 12, 1), Parcela.Status.DESCONTADO),
            ],
        )
        self.assertFalse(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
                referencia_mes__lt=date(2025, 10, 1),
            ).exclude(status=Parcela.Status.CANCELADO).exists()
        )

    def test_command_respects_four_month_cycle_size_when_rebuilding_chunks(self):
        associado = Associado.objects.create(
            nome_completo="Associado Ciclo 4",
            cpf_cnpj="71000000103",
            email="ciclo4@teste.local",
            telefone="86999999997",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-103",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("1200.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=4,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("1200.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 8, 8),
            data_aprovacao=date(2025, 8, 8),
            data_primeira_mensalidade=date(2025, 10, 6),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 8, 8),
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 9, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1200.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 2, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("600.00"),
        )
        for numero, referencia, status in [
            (1, date(2025, 9, 1), Parcela.Status.EM_PREVISAO),
            (2, date(2025, 10, 1), Parcela.Status.DESCONTADO),
            (3, date(2025, 11, 1), Parcela.Status.DESCONTADO),
            (4, date(2025, 12, 1), Parcela.Status.DESCONTADO),
        ]:
            Parcela.objects.create(
                ciclo=ciclo_1,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=status,
                data_pagamento=referencia if status == Parcela.Status.DESCONTADO else None,
            )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 1, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 1, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.EM_PREVISAO,
        )

        for referencia in [
            date(2025, 10, 1),
            date(2025, 11, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
        ]:
            self._create_payment(
                associado=associado,
                referencia=referencia,
                status_code="1",
                valor=Decimal("300.00"),
            )

        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=date(2025, 10, 1),
            force_candidate=True,
            execute=True,
        )

        contrato.refresh_from_db()
        ciclos = list(
            Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True)
            .order_by("numero", "id")
            .values_list("numero", "data_inicio", "data_fim")
        )
        refs = list(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("ciclo__numero", "numero", "referencia_mes")
            .values_list("ciclo__numero", "numero", "referencia_mes")
        )

        self.assertTrue(result["applied"])
        self.assertEqual(
            ciclos,
            [
                (1, date(2025, 10, 1), date(2026, 1, 1)),
                (2, date(2026, 2, 1), date(2026, 2, 1)),
            ],
        )
        self.assertEqual(
            refs,
            [
                (1, 1, date(2025, 10, 1)),
                (1, 2, date(2025, 11, 1)),
                (1, 3, date(2025, 12, 1)),
                (1, 4, date(2026, 1, 1)),
                (2, 1, date(2026, 2, 1)),
            ],
        )

    def test_command_reuses_cycle_slot_even_when_soft_deleted_duplicate_exists(self):
        associado = Associado.objects.create(
            nome_completo="Associado Soft Delete",
            cpf_cnpj="71000000104",
            email="softdelete@teste.local",
            telefone="86999999996",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-104",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 8, 8),
            data_aprovacao=date(2025, 8, 8),
            data_primeira_mensalidade=date(2025, 10, 6),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 8, 8),
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 9, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("900.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 1, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("300.00"),
        )
        parcela_soft_deleted = Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 9, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 9, 1),
            status=Parcela.Status.EM_PREVISAO,
        )
        parcela_soft_deleted.soft_delete()
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 11, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 11, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 12, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 12, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )

        for referencia in [date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)]:
            self._create_payment(
                associado=associado,
                referencia=referencia,
                status_code="1",
                valor=Decimal("300.00"),
            )

        result = repair_contract_pre_october_cycles(
            contrato,
            floor_reference=date(2025, 10, 1),
            force_candidate=True,
            execute=True,
        )

        refs = list(
            Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("ciclo__numero", "numero", "referencia_mes")
            .values_list("ciclo__numero", "numero", "referencia_mes")
        )

        self.assertTrue(result["applied"])
        self.assertEqual(
            refs,
            [
                (1, 1, date(2025, 10, 1)),
                (1, 2, date(2025, 11, 1)),
                (1, 3, date(2025, 12, 1)),
            ],
        )
