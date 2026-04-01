from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato


class RecalculateAgentCommissionsCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="ABASE",
            is_active=True,
        )
        cls.agente.roles.add(role_agente)

    def test_command_recalculates_existing_contract_commissions(self):
        associado = Associado.objects.create(
            nome_completo="Associado Teste",
            cpf_cnpj="12345678901",
            agente_responsavel=self.agente,
            auxilio_taxa=Decimal("10.00"),
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("1050.00"),
            valor_liquido=Decimal("1050.00"),
            valor_mensalidade=Decimal("350.00"),
            margem_disponivel=Decimal("735.00"),
            comissao_agente=Decimal("35.00"),
        )
        Contrato.objects.filter(pk=contrato.pk).update(comissao_agente=Decimal("35.00"))
        contrato.refresh_from_db()
        self.assertEqual(contrato.comissao_agente, Decimal("35.00"))

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "commissions.json"
            stdout = StringIO()
            call_command(
                "recalculate_agent_commissions",
                "--execute",
                "--report-json",
                str(report_path),
                stdout=stdout,
            )

            contrato.refresh_from_db()
            self.assertEqual(contrato.comissao_agente, Decimal("73.50"))

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["summary"]["updated"], 1)
            self.assertEqual(report["contracts"][0]["comissao_anterior"], "35.00")
            self.assertEqual(report["contracts"][0]["comissao_nova"], "73.50")
