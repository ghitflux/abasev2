from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia
from apps.importacao.models import ArquivoRetorno
from apps.refinanciamento.models import Refinanciamento
from apps.relatorios.models import RelatorioGerado


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RelatoriosViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")

    @classmethod
    def _create_user(cls, email: str, role: Role, first_name: str) -> User:
        user = User.objects.create_user(
            email=email,
            password="Senha@123",
            first_name=first_name,
            last_name="ABASE",
            is_active=True,
        )
        user.roles.add(role)
        return user

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _seed_operational_data(self):
        associado = Associado.objects.create(
            nome_completo="Maria Teste",
            cpf_cnpj="12345678901",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("1200.00"),
            valor_liquido=Decimal("1000.00"),
            valor_mensalidade=Decimal("300.00"),
            comissao_agente=Decimal("45.00"),
            status=Contrato.Status.ATIVO,
        )
        Parcela.objects.create(
            ciclo=contrato.ciclos.create(
                numero=1,
                data_inicio=date(2026, 1, 1),
                data_fim=date(2026, 3, 1),
                status="aberto",
                valor_total=Decimal("900.00"),
            ),
            numero=1,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 3, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date.today(),
        )
        EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        Pendencia.objects.create(
            esteira_item=associado.esteira_item,
            tipo="documentacao",
            descricao="Documento pendente",
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.PENDENTE_APTO,
            valor_refinanciamento=Decimal("1500.00"),
            repasse_agente=Decimal("120.00"),
        )
        ArquivoRetorno.objects.create(
            arquivo_nome="retorno_teste.txt",
            arquivo_url="arquivos_retorno/retorno_teste.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=date(2026, 3, 1),
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=self.admin,
            total_registros=10,
            processados=9,
            nao_encontrados=1,
            erros=0,
        )
        return associado, contrato

    def test_resumo_agrega_dados_operacionais(self):
        self._seed_operational_data()

        response = self.client.get("/api/v1/relatorios/resumo/")
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["associados_ativos"], 1)
        self.assertEqual(payload["contratos_ativos"], 1)
        self.assertEqual(payload["pendencias_abertas"], 1)
        self.assertEqual(payload["refinanciamentos_pendentes"], 1)
        self.assertEqual(payload["importacoes_concluidas"], 1)
        self.assertEqual(payload["ultima_importacao"]["arquivo_nome"], "retorno_teste.txt")

    def test_exportar_gera_arquivo_e_download(self):
        Associado.objects.create(
            nome_completo="Joao Exportacao",
            cpf_cnpj="22345678901",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )

        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {"tipo": "associados", "formato": "json"},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()
        self.assertTrue(payload["download_url"].endswith("/download/"))
        self.assertEqual(RelatorioGerado.objects.count(), 1)

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        content = b"".join(download_response.streaming_content)
        exported = json.loads(content.decode("utf-8"))
        self.assertEqual(exported[0]["nome_completo"], "Joao Exportacao")

    def test_exportar_gera_json_para_todos_os_tipos(self):
        self._seed_operational_data()

        expected_keys = {
            "associados": "nome_completo",
            "tesouraria": "codigo",
            "refinanciamentos": "valor_refinanciamento",
            "importacao": "arquivo_nome",
        }

        for tipo, expected_key in expected_keys.items():
            with self.subTest(tipo=tipo):
                response = self.client.post(
                    "/api/v1/relatorios/exportar/",
                    {"tipo": tipo, "formato": "json"},
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.json())
                payload = response.json()

                download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
                self.assertEqual(download_response.status_code, 200)
                self.assertTrue(download_response["Content-Type"].startswith("application/json"))

                content = b"".join(download_response.streaming_content)
                exported = json.loads(content.decode("utf-8"))
                self.assertGreaterEqual(len(exported), 1)
                self.assertIn(expected_key, exported[0])

    def test_exportar_gera_pdf_personalizado_para_todos_os_tipos(self):
        self._seed_operational_data()

        for tipo in ["associados", "tesouraria", "refinanciamentos", "importacao"]:
            with self.subTest(tipo=tipo):
                response = self.client.post(
                    "/api/v1/relatorios/exportar/",
                    {"tipo": tipo, "formato": "pdf"},
                    format="json",
                )
                self.assertEqual(response.status_code, 201, response.json())
                payload = response.json()
                self.assertEqual(payload["formato"], "pdf")

                download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
                self.assertEqual(download_response.status_code, 200)
                self.assertEqual(download_response["Content-Type"], "application/pdf")

                content = b"".join(download_response.streaming_content)
                self.assertTrue(content.startswith(b"%PDF-"))
