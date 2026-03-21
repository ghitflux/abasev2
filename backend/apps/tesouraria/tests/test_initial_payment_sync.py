from __future__ import annotations

import json
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.initial_payment import build_initial_payment_payload
from apps.tesouraria.models import Pagamento


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class SyncLegacyInitialPaymentsCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_tesoureiro = Role.objects.create(
            codigo="TESOUREIRO",
            nome="Tesoureiro",
        )
        cls.user = User.objects.create_user(
            email="tesoureiro@abase.local",
            password="Senha@123",
            first_name="Tes",
            last_name="ABASE",
            is_active=True,
        )
        cls.user.roles.add(cls.role_tesoureiro)

    def _create_contract(self, *, cpf: str, nome: str, codigo: str) -> Contrato:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.user,
            orgao_publico="SEFAZ",
            contrato_margem_disponivel=Decimal("420.00"),
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.user,
            codigo=codigo,
            valor_bruto=Decimal("500.00"),
            valor_liquido=Decimal("420.00"),
            valor_mensalidade=Decimal("200.00"),
            prazo_meses=3,
            margem_disponivel=Decimal("420.00"),
            valor_total_antecipacao=Decimal("420.00"),
            status=Contrato.Status.EM_ANALISE,
            data_contrato=date(2026, 3, 13),
            data_aprovacao=date(2026, 3, 13),
            auxilio_liberado_em=date(2026, 3, 13),
        )
        Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("600.00"),
        )
        return contrato

    @staticmethod
    def _aware(value: datetime):
        return timezone.make_aware(value)

    def _write_dump(self, path: Path, *, legacy_payment_id: int, legacy_cadastro_id: int, cpf: str, contrato_codigo: str, status: str, valor_pago: str | None, paid_at: str | None, notes: str = "Gerado pelo Analista após validação.", created_at: str = "2026-03-13 16:58:01", path_assoc: str = "", path_agente: str = ""):
        paid_at_sql = f"'{paid_at}'" if paid_at else "NULL"
        assoc_sql = f"'{path_assoc}'" if path_assoc else "NULL"
        agente_sql = f"'{path_agente}'" if path_agente else "NULL"
        dump_sql = f"""
INSERT INTO `tesouraria_pagamentos` (`id`,`agente_cadastro_id`,`created_by_user_id`,`contrato_codigo_contrato`,`contrato_margem_disponivel`,`cpf_cnpj`,`full_name`,`agente_responsavel`,`status`,`valor_pago`,`paid_at`,`forma_pagamento`,`comprovante_associado_path`,`comprovante_agente_path`,`notes`,`created_at`) VALUES
({legacy_payment_id},{legacy_cadastro_id},1,'{contrato_codigo}','420.00','{cpf}','Associada Teste','Tes ABASE','{status}',{valor_pago if valor_pago is not None else 'NULL'},{paid_at_sql},'pix',{assoc_sql},{agente_sql},'{notes}','{created_at}');
"""
        path.write_text(dump_sql.strip() + "\n", encoding="utf-8")

    def test_sync_override_updates_payment_and_returns_placeholder(self):
        contrato = self._create_contract(
            cpf="22716050325",
            nome="MARIA DO PERPETUO SOCORRO MENDES DE MELO",
            codigo="CTR-20260313135654-L4VJE",
        )
        pagamento = Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=self.user,
            contrato_codigo=contrato.codigo,
            contrato_margem_disponivel=Decimal("420.00"),
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=self.user.full_name,
            status=Pagamento.Status.PENDENTE,
            notes="Gerado pelo Analista após validação.",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dump_path = temp_path / "legacy.sql"
            self._write_dump(
                dump_path,
                legacy_payment_id=736,
                legacy_cadastro_id=702,
                cpf=contrato.associado.cpf_cnpj,
                contrato_codigo=contrato.codigo,
                status="pendente",
                valor_pago=None,
                paid_at=None,
            )
            override_path = temp_path / "overrides.json"
            override_path.write_text(
                json.dumps(
                    [
                        {
                            "legacy_payment_id": 736,
                            "cpf_cnpj": contrato.associado.cpf_cnpj,
                            "contrato_codigo": contrato.codigo,
                            "status": "pago",
                            "paid_at": "2026-03-16 09:06:00",
                            "valor_pago": "420.00",
                            "assoc_legacy_url": "https://abasepiaui.com/tesoureiro/comprovantes/736?i=1",
                            "agente_legacy_url": "https://abasepiaui.com/tesoureiro/comprovantes/736?i=2",
                            "observacao": "Pagamento recebido em 16/03/2026 09:06",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            call_command(
                "sync_legacy_initial_payments",
                "--file",
                str(dump_path),
                "--legacy-media-root",
                str(temp_path),
                "--overrides",
                str(override_path),
                "--cpf",
                contrato.associado.cpf_cnpj,
                "--execute",
            )

        pagamento.refresh_from_db()
        self.assertEqual(pagamento.status, Pagamento.Status.PAGO)
        self.assertEqual(pagamento.valor_pago, Decimal("420.00"))
        self.assertEqual(pagamento.legacy_tesouraria_pagamento_id, 736)
        self.assertEqual(pagamento.origem, Pagamento.Origem.OVERRIDE_MANUAL)
        self.assertEqual(
            timezone.localtime(pagamento.paid_at).strftime("%Y-%m-%d %H:%M"),
            "2026-03-16 09:06",
        )
        payload = build_initial_payment_payload(contrato)
        self.assertEqual(payload.evidencia_status, "placeholder_recebido")
        self.assertEqual(len(payload.evidencias), 2)
        self.assertEqual(
            {item["tipo_referencia"] for item in payload.evidencias},
            {"placeholder_recebido"},
        )

    def test_sync_copies_legacy_files_and_creates_contract_comprovantes(self):
        contrato = self._create_contract(
            cpf="11122233344",
            nome="Associada Acervo",
            codigo="CTR-20260315090000-TESTE",
        )
        Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=self.user,
            contrato_codigo=contrato.codigo,
            contrato_margem_disponivel=Decimal("420.00"),
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=self.user.full_name,
            status=Pagamento.Status.PENDENTE,
            notes="Gerado pelo Analista após validação.",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            acervo_root = temp_path / "storage" / "storage" / "app" / "public" / "tesouraria" / "comprovantes" / "12"
            acervo_root.mkdir(parents=True, exist_ok=True)
            assoc_file = acervo_root / "20260315_090601_0_assoc.pdf"
            agent_file = acervo_root / "20260315_090601_1_agente.pdf"
            assoc_file.write_bytes(b"assoc")
            agent_file.write_bytes(b"agente")
            dump_path = temp_path / "legacy.sql"
            self._write_dump(
                dump_path,
                legacy_payment_id=20,
                legacy_cadastro_id=12,
                cpf=contrato.associado.cpf_cnpj,
                contrato_codigo=contrato.codigo,
                status="pago",
                valor_pago="'420.00'",
                paid_at="2026-03-15 09:06:01",
            )

            call_command(
                "sync_legacy_initial_payments",
                "--file",
                str(dump_path),
                "--legacy-media-root",
                str(temp_path),
                "--cpf",
                contrato.associado.cpf_cnpj,
                "--execute",
            )

        pagamento = Pagamento.objects.get(cadastro=contrato.associado, contrato_codigo=contrato.codigo)
        self.assertEqual(pagamento.status, Pagamento.Status.PAGO)
        self.assertTrue(pagamento.comprovante_associado_path.startswith("refinanciamentos/efetivacao_contrato/"))
        self.assertTrue(pagamento.comprovante_agente_path.startswith("refinanciamentos/efetivacao_contrato/"))
        self.assertTrue(default_storage.exists(pagamento.comprovante_associado_path))
        self.assertTrue(default_storage.exists(pagamento.comprovante_agente_path))

        comprovantes = list(
            Comprovante.objects.filter(
                contrato=contrato,
                refinanciamento__isnull=True,
                origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
            ).order_by("papel")
        )
        self.assertEqual(len(comprovantes), 2)
        self.assertEqual(
            {comprovante.papel for comprovante in comprovantes},
            {Comprovante.Papel.ASSOCIADO, Comprovante.Papel.AGENTE},
        )
        self.assertEqual(
            {
                timezone.localtime(comprovante.created_at).strftime("%Y-%m-%d %H:%M:%S")
                for comprovante in comprovantes
            },
            {"2026-03-15 09:06:01"},
        )
        payload = build_initial_payment_payload(contrato)
        self.assertEqual(payload.evidencia_status, "arquivo_local")
        self.assertTrue(all(item["arquivo_disponivel_localmente"] for item in payload.evidencias))

    def test_payload_uses_legacy_refinanciamento_comprovantes_as_fallback(self):
        contrato = self._create_contract(
            cpf="33322211100",
            nome="Associado Fallback Refi",
            codigo="CTR-20260315090000-FALL",
        )
        ciclo_origem = contrato.ciclos.get()
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.user,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            ciclo_origem=ciclo_origem,
            executado_em=self._aware(datetime(2026, 3, 16, 9, 6)),
            data_ativacao_ciclo=self._aware(datetime(2026, 3, 16, 9, 6)),
            cycle_key="2026-01|2026-02|2026-03",
            ref1=date(2026, 1, 1),
            ref2=date(2026, 2, 1),
            ref3=date(2026, 3, 1),
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            origem=Comprovante.Origem.LEGADO,
            arquivo=SimpleUploadedFile("assoc.jpeg", b"assoc", content_type="image/jpeg"),
            nome_original="assoc.jpeg",
            enviado_por=self.user,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            origem=Comprovante.Origem.LEGADO,
            arquivo=SimpleUploadedFile("agente.jpeg", b"agente", content_type="image/jpeg"),
            nome_original="agente.jpeg",
            enviado_por=self.user,
        )

        payload = build_initial_payment_payload(contrato)

        self.assertEqual(payload.status, Pagamento.Status.PAGO)
        self.assertEqual(payload.status_label, Pagamento.Status.PAGO.label)
        self.assertEqual(payload.evidencia_status, "arquivo_local")
        self.assertEqual(len(payload.evidencias), 2)
        self.assertEqual(
            {item["papel"] for item in payload.evidencias},
            {Comprovante.Papel.ASSOCIADO, Comprovante.Papel.AGENTE},
        )

    def test_sync_reuses_existing_legacy_payment_without_contract_code(self):
        contrato = self._create_contract(
            cpf="44433322211",
            nome="Associado Pagamento Legado",
            codigo="CTR-20260315090000-REUSE",
        )
        pagamento = Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=self.user,
            contrato_codigo="",
            contrato_margem_disponivel=Decimal("420.00"),
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=self.user.full_name,
            status=Pagamento.Status.PENDENTE,
            valor_pago=Decimal("420.00"),
            paid_at=self._aware(datetime(2026, 3, 15, 9, 6, 1)),
            legacy_tesouraria_pagamento_id=20,
            origem=Pagamento.Origem.LEGADO,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            dump_path = temp_path / "legacy.sql"
            self._write_dump(
                dump_path,
                legacy_payment_id=20,
                legacy_cadastro_id=12,
                cpf=contrato.associado.cpf_cnpj,
                contrato_codigo=contrato.codigo,
                status="pago",
                valor_pago="'420.00'",
                paid_at="2026-03-15 09:06:01",
            )

            call_command(
                "sync_legacy_initial_payments",
                "--file",
                str(dump_path),
                "--cpf",
                contrato.associado.cpf_cnpj,
                "--execute",
            )

        pagamento.refresh_from_db()
        self.assertEqual(pagamento.contrato_codigo, contrato.codigo)
        self.assertEqual(pagamento.status, Pagamento.Status.PAGO)
        self.assertEqual(pagamento.legacy_tesouraria_pagamento_id, 20)
