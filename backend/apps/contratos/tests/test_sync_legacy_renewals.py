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
from apps.contratos.models import Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Pagamento


class SyncLegacyRenewalsCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.admin = User.objects.create_user(
            email="admin@abase.local",
            password="Senha@123",
            first_name="Admin",
            is_active=True,
        )
        cls.admin.roles.add(role)

    def _legacy_dump_sql(self) -> str:
        return """
INSERT INTO `refinanciamentos` (`id`,`agente_cadastro_id`,`created_by_user_id`,`cpf_cnpj`,`cycle_key`,`ref1`,`ref2`,`ref3`,`ref4`,`contrato_codigo_origem`,`nome_snapshot`,`agente_snapshot`,`filial_snapshot`,`notes`,`created_at`)
VALUES
(73,512,1,'22808922353','2025-10|2025-11|2025-12','2025-10-01','2025-11-01','2025-12-01',NULL,'CTR-20250903204013-SGNPD','JOAQUIM VIEIRA FILHO','Agente Padrão','Matriz','renovacao legado','2026-01-19 16:40:21');

INSERT INTO `refinanciamento_comprovantes` (`id`,`refinanciamento_id`,`kind`,`path`,`original_name`,`uploaded_by_user_id`,`agente_snapshot`,`filial_snapshot`)
VALUES
(149,73,'associado','refinanciamentos/73/comprovantes/5151e008-29f1-44ce-ad13-68eee6e1ffa7.jpeg','assoc.jpeg',1,'Agente Padrão','Matriz'),
(150,73,'agente','refinanciamentos/73/comprovantes/17cf4ed5-2bc2-4d1d-aba3-8a8055055c44.jpeg','agente.jpeg',1,'Agente Padrão','Matriz');

INSERT INTO `refinanciamento_solicitacoes` (`id`,`refinanciamento_id`,`cadastro_id`,`created_by_user_id`,`cpf_cnpj`,`cycle_key`,`ref1`,`ref2`,`ref3`,`contrato_codigo_origem`,`termo_antecipacao_path`,`termo_antecipacao_original_name`,`termo_antecipacao_mime`,`termo_antecipacao_size_bytes`,`termo_antecipacao_uploaded_at`,`created_at`)
VALUES
(57,73,512,1,'22808922353','2025-10|2025-11|2025-12','2025-10-01','2025-11-01','2025-12-01','CTR-20250903204013-SGNPD','refinanciamentos/solicitacoes/2025-10_2025-11_2025-12/22808922353/57/20260119_163043_termo_antecipacao_N9DWsV.pdf','termo.pdf','application/pdf',12345,'2026-01-19 16:30:43','2026-01-19 16:30:43');
""".strip()

    def test_sync_command_materializes_legacy_renewal_and_links_documents(self):
        associado = Associado.objects.create(
            nome_completo="JOAQUIM VIEIRA FILHO",
            cpf_cnpj="22808922353",
            email="joaquim@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao="0028029",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.admin,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.admin,
            codigo="CTR-20250903204013-SGNPD",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 9, 3),
            data_aprovacao=date(2025, 9, 3),
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.admin,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=Decimal("900.00"),
            contrato_margem_disponivel=Decimal("900.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.admin.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("900.00"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "legacy.sql"
            report_path = Path(tmpdir) / "sync.json"
            dump_path.write_text(self._legacy_dump_sql(), encoding="utf-8")

            call_command(
                "sync_legacy_renewals",
                file=str(dump_path),
                execute=True,
                cpf="22808922353",
                report_json=str(report_path),
            )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        refinanciamento = Refinanciamento.objects.get(legacy_refinanciamento_id=73)
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.EFETIVADO)
        self.assertEqual(refinanciamento.origem, Refinanciamento.Origem.LEGADO)
        self.assertEqual(
            timezone.localtime(refinanciamento.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            "2026-01-19 16:40:21",
        )
        self.assertEqual(refinanciamento.ciclo_destino.numero, 2)
        self.assertEqual(refinanciamento.ciclo_destino.data_inicio, date(2026, 1, 1))
        self.assertEqual(
            list(
                refinanciamento.ciclo_destino.parcelas.order_by("numero").values_list(
                    "referencia_mes", flat=True
                )
            ),
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
        )
        self.assertEqual(refinanciamento.comprovantes.count(), 3)
        self.assertTrue(
            Comprovante.objects.filter(
                refinanciamento=refinanciamento,
                tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            ).exists()
        )
        self.assertEqual(
            set(
                refinanciamento.comprovantes.values_list("created_at", flat=True)
            ),
            {timezone.make_aware(datetime(2026, 1, 19, 16, 40, 21))},
        )
        self.assertEqual(payload["summary"]["synced"], 1)

    def test_sync_command_skips_orphan_legacy_renewal_with_refs_before_contract_timeline(self):
        associado = Associado.objects.create(
            nome_completo="FRANCISCO FERNANDES NETO",
            cpf_cnpj="53729226304",
            email="francisco@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao="605MAT",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.admin,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.admin,
            codigo="CTR-20260105143052-RTJCX",
            valor_bruto=Decimal("750.00"),
            valor_liquido=Decimal("750.00"),
            valor_mensalidade=Decimal("250.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_contrato=date(2026, 1, 5),
            data_aprovacao=date(2026, 1, 5),
            data_primeira_mensalidade=date(2026, 2, 6),
            mes_averbacao=date(2026, 1, 1),
            auxilio_liberado_em=date(2026, 1, 5),
        )
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.admin,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=Decimal("750.00"),
            contrato_margem_disponivel=Decimal("750.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.admin.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("525.00"),
        )

        dump_sql = """
INSERT INTO `refinanciamentos` (`id`,`agente_cadastro_id`,`created_by_user_id`,`cpf_cnpj`,`cycle_key`,`ref1`,`ref2`,`ref3`,`ref4`,`contrato_codigo_origem`,`nome_snapshot`,`agente_snapshot`,`filial_snapshot`,`notes`,`created_at`)
VALUES
(350,605,1,'53729226304','2025-10|2025-11|2025-12','2025-10-01','2025-11-01','2025-12-01',NULL,NULL,'FRANCISCO FERNANDES NETO','Agente Padrão','Matriz','refinanciamento órfão legado','2026-03-13 12:13:29');
""".strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "legacy.sql"
            report_path = Path(tmpdir) / "sync.json"
            dump_path.write_text(dump_sql, encoding="utf-8")

            call_command(
                "sync_legacy_renewals",
                file=str(dump_path),
                execute=True,
                cpf="53729226304",
                report_json=str(report_path),
            )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertFalse(
            Refinanciamento.objects.filter(legacy_refinanciamento_id=350).exists()
        )
        self.assertEqual(payload["summary"]["synced"], 0)
        self.assertEqual(payload["summary"]["skipped"], 1)
        self.assertEqual(
            payload["renewals"][0]["status"],
            "skipped_contrato_not_found",
        )

    def test_sync_command_restores_treasury_backed_legacy_renewal_with_blank_contract_code(self):
        associado = Associado.objects.create(
            nome_completo="ABNER OLIVEIRA NETO",
            cpf_cnpj="49684639368",
            email="abner@teste.local",
            telefone="86999999999",
            orgao_publico="SSP",
            matricula_orgao="430436-5",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.admin,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.admin,
            codigo="CTR-20251104121629-9TILV",
            valor_bruto=Decimal("600.00"),
            valor_liquido=Decimal("600.00"),
            valor_mensalidade=Decimal("200.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 11, 4),
            data_aprovacao=date(2025, 11, 4),
            data_primeira_mensalidade=date(2025, 12, 5),
            mes_averbacao=date(2025, 11, 1),
            auxilio_liberado_em=date(2025, 11, 4),
        )
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.admin,
            contrato_codigo="",
            contrato_valor_antecipacao=Decimal("420.00"),
            contrato_margem_disponivel=Decimal("420.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.admin.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("200.00"),
            paid_at=timezone.make_aware(datetime(2026, 2, 4, 11, 40, 27)),
            forma_pagamento="manual",
            legacy_tesouraria_pagamento_id=359,
            origem=Pagamento.Origem.LEGADO,
            notes="Registro manual (COORDENADOR) a partir do arquivo retorno",
        )

        dump_sql = """
INSERT INTO `refinanciamentos` (`id`,`agente_cadastro_id`,`created_by_user_id`,`cpf_cnpj`,`cycle_key`,`ref1`,`ref2`,`ref3`,`ref4`,`contrato_codigo_origem`,`nome_snapshot`,`agente_snapshot`,`filial_snapshot`,`notes`,`created_at`)
VALUES
(233,370,548,'49684639368','2025-10|2025-11|2025-12','2025-10-01','2025-11-01','2025-12-01',NULL,NULL,'ABNER OLIVEIRA NETO','fernandaleonardo','fernandaleonardo','renovacao legado','2026-02-10 10:12:55');
""".strip()

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / "legacy.sql"
            report_path = Path(tmpdir) / "sync.json"
            dump_path.write_text(dump_sql, encoding="utf-8")

            call_command(
                "sync_legacy_renewals",
                file=str(dump_path),
                execute=True,
                cpf="49684639368",
                report_json=str(report_path),
            )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        refinanciamento = Refinanciamento.objects.get(legacy_refinanciamento_id=233)
        self.assertIsNone(refinanciamento.deleted_at)
        self.assertEqual(refinanciamento.contrato_origem_id, contrato.id)
        self.assertIsNotNone(refinanciamento.ciclo_destino_id)
        self.assertEqual(refinanciamento.ciclo_destino.numero, 2)
        self.assertEqual(refinanciamento.ciclo_destino.data_inicio, date(2026, 2, 1))
        self.assertEqual(
            list(
                refinanciamento.ciclo_destino.parcelas.order_by("numero").values_list(
                    "referencia_mes", flat=True
                )
            ),
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )
        self.assertEqual(payload["summary"]["synced"], 1)
