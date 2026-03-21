from __future__ import annotations

import json
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import Pagamento


class AuditCycleTimelineCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            last_name="ABASE",
            is_active=True,
        )
        cls.admin.roles.add(role_admin)

    def _create_contract(self, cpf: str, start_month: date) -> tuple[Associado, Contrato, Ciclo]:
        def add_months(base_date: date, months: int) -> date:
            month_index = base_date.month - 1 + months
            year = base_date.year + month_index // 12
            month = month_index % 12 + 1
            return date(year, month, 1)

        associado = Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.admin,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=start_month,
            data_aprovacao=start_month,
            data_primeira_mensalidade=start_month.replace(day=1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=start_month.replace(day=1),
            data_fim=add_months(start_month.replace(day=1), 2),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        parcelas = []
        for index in range(3):
            month = start_month.month + index
            year = start_month.year + (month - 1) // 12
            normalized_month = ((month - 1) % 12) + 1
            referencia = date(year, normalized_month, 1)
            parcelas.append(
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=index + 1,
                    referencia_mes=referencia,
                    valor=Decimal("300.00"),
                    data_vencimento=referencia,
                    status=Parcela.Status.DESCONTADO if index < 2 else Parcela.Status.EM_ABERTO,
                    data_pagamento=referencia if index < 2 else None,
                )
            )
        Parcela.objects.bulk_create(parcelas)
        return associado, contrato, ciclo

    def _add_tesouraria_payment(
        self,
        associado: Associado,
        contrato: Contrato,
        paid_at: datetime,
    ) -> Pagamento:
        if timezone.is_naive(paid_at):
            paid_at = timezone.make_aware(paid_at)
        return Pagamento.objects.create(
            cadastro=associado,
            created_by=self.admin,
            contrato_codigo=contrato.codigo,
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.admin.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("900.00"),
            paid_at=paid_at,
        )

    def _run_command(self, cpf: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "audit.json"
            call_command("audit_cycle_timeline", cpf=cpf, json_path=str(output_path))
            return json.loads(output_path.read_text(encoding="utf-8"))

    def test_command_reports_ok_for_effectivated_renewal(self):
        associado, contrato, ciclo_1 = self._create_contract("11122233344", date(2026, 1, 1))
        self._add_tesouraria_payment(
            associado,
            contrato,
            datetime(2025, 12, 20, 12, 0),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_2,
                    associado=associado,
                    numero=index + 1,
                    referencia_mes=date(2026, 4 + index, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 4 + index, 1),
                    status=Parcela.Status.EM_ABERTO,
                )
                for index in range(3)
            ]
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.admin,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            ciclo_origem=ciclo_1,
            ciclo_destino=ciclo_2,
            executado_em=timezone.make_aware(datetime(2026, 4, 10, 14, 0)),
            cycle_key="2026-01|2026-02|2026-03",
            ref1=date(2026, 1, 1),
            ref2=date(2026, 2, 1),
            ref3=date(2026, 3, 1),
        )

        report = self._run_command(associado.cpf_cnpj)
        classifications = set(report["associados"][0]["classifications"])
        self.assertIn("divergencia_materializado_canonico", classifications)
        self.assertIn("parcela_vencida_materializada_no_ciclo", classifications)
        self.assertIn("renovacao_com_ciclo_incompleto", classifications)
        contrato_payload = report["associados"][0]["contratos"][0]
        self.assertEqual(contrato_payload["cycle_size"], 3)
        self.assertIn("divergencia_materializado_canonico", contrato_payload["scenario_tags"])
        self.assertIn("renovacao_com_ciclo_incompleto", contrato_payload["scenario_tags"])

    def test_command_reports_inferred_tesouraria_and_missing_future_cycle(self):
        associado, contrato, ciclo_1 = self._create_contract("22808922353", date(2025, 10, 1))
        self._add_tesouraria_payment(
            associado,
            contrato,
            datetime(2025, 9, 3, 12, 0),
        )
        self._add_tesouraria_payment(
            associado,
            contrato,
            datetime(2026, 1, 15, 12, 16),
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.admin,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EM_ANALISE,
            ciclo_origem=ciclo_1,
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
        )

        report = self._run_command(associado.cpf_cnpj)
        classifications = set(report["associados"][0]["classifications"])
        self.assertIn("ciclo_futuro_ausente", classifications)
        self.assertIn("ativacao_inferida_tesouraria", classifications)

    def test_command_reports_cycle_activated_before_effectivation(self):
        associado, contrato, ciclo_1 = self._create_contract("55566677788", date(2026, 1, 1))
        self._add_tesouraria_payment(
            associado,
            contrato,
            datetime(2025, 12, 22, 12, 0),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_2,
                    associado=associado,
                    numero=index + 1,
                    referencia_mes=date(2026, 4 + index, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 4 + index, 1),
                    status=Parcela.Status.EM_ABERTO,
                )
                for index in range(3)
            ]
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.admin,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.CONCLUIDO,
            ciclo_origem=ciclo_1,
            ciclo_destino=ciclo_2,
            cycle_key="2026-01|2026-02|2026-03",
            ref1=date(2026, 1, 1),
            ref2=date(2026, 2, 1),
            ref3=date(2026, 3, 1),
        )

        report = self._run_command(associado.cpf_cnpj)
        classifications = set(report["associados"][0]["classifications"])
        self.assertIn("ciclo_ativado_antes_da_efetivacao", classifications)
