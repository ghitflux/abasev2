from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia
from apps.importacao.models import ArquivoRetorno
from apps.refinanciamento.models import Refinanciamento
from apps.relatorios.models import RelatorioGerado
from apps.relatorios.services import RelatorioService


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
            "tesouraria": "agente",
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

    def test_exportar_relatorio_de_associados_com_uma_parcela_paga_retorna_linhas(self):
        associado = Associado.objects.create(
            nome_completo="Associado Um Pagamento",
            cpf_cnpj="22345678902",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_mensalidade=Decimal("180.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo = contrato.ciclos.create(
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status="aberto",
            valor_total=Decimal("540.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("180.00"),
            data_vencimento=date(2026, 3, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date.today(),
        )

        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {
                "tipo": "associados_ativos_com_1_parcela_paga",
                "formato": "json",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        content = b"".join(download_response.streaming_content)
        exported = json.loads(content.decode("utf-8"))
        self.assertGreaterEqual(len(exported), 1)
        self.assertEqual(exported[0]["parcelas_pagas"], 1)

    def test_exportar_relatorio_de_associados_pagadores_respeita_periodo_agente_e_faixa(self):
        hoje = date.today()
        agente_secundario = self._create_user(
            "agente-secundario@abase.local",
            self.role_agente,
            "AgenteSec",
        )

        associado_ok = Associado.objects.create(
            nome_completo="Associado Faixa Alvo",
            cpf_cnpj="32345678901",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato_ok = Contrato.objects.create(
            associado=associado_ok,
            agente=self.agente,
            valor_mensalidade=Decimal("250.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo_ok = contrato_ok.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="aberto",
            valor_total=Decimal("750.00"),
        )
        for numero in range(1, 4):
            Parcela.objects.create(
                ciclo=ciclo_ok,
                associado=associado_ok,
                numero=numero,
                referencia_mes=hoje.replace(day=1),
                valor=Decimal("250.00"),
                data_vencimento=hoje,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=hoje - timedelta(days=numero),
            )

        associado_outro_agente = Associado.objects.create(
            nome_completo="Associado Outro Agente",
            cpf_cnpj="32345678902",
            status=Associado.Status.ATIVO,
            agente_responsavel=agente_secundario,
        )
        contrato_outro_agente = Contrato.objects.create(
            associado=associado_outro_agente,
            agente=agente_secundario,
            valor_mensalidade=Decimal("250.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo_outro = contrato_outro_agente.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="aberto",
            valor_total=Decimal("750.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_outro,
            associado=associado_outro_agente,
            numero=1,
            referencia_mes=hoje.replace(day=1),
            valor=Decimal("250.00"),
            data_vencimento=hoje,
            status=Parcela.Status.DESCONTADO,
            data_pagamento=hoje,
        )

        associado_faixa_errada = Associado.objects.create(
            nome_completo="Associado Faixa Errada",
            cpf_cnpj="32345678903",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato_faixa_errada = Contrato.objects.create(
            associado=associado_faixa_errada,
            agente=self.agente,
            valor_mensalidade=Decimal("550.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo_faixa_errada = contrato_faixa_errada.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="aberto",
            valor_total=Decimal("1650.00"),
        )
        for numero in range(1, 3):
            Parcela.objects.create(
                ciclo=ciclo_faixa_errada,
                associado=associado_faixa_errada,
                numero=numero,
                referencia_mes=hoje.replace(day=1),
                valor=Decimal("550.00"),
                data_vencimento=hoje,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=hoje,
            )

        associado_faixa_alta = Associado.objects.create(
            nome_completo="Associado Faixa Alta",
            cpf_cnpj="32345678904",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato_faixa_alta = Contrato.objects.create(
            associado=associado_faixa_alta,
            agente=self.agente,
            valor_mensalidade=Decimal("650.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo_faixa_alta = contrato_faixa_alta.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="aberto",
            valor_total=Decimal("1950.00"),
        )
        for numero in range(1, 4):
            Parcela.objects.create(
                ciclo=ciclo_faixa_alta,
                associado=associado_faixa_alta,
                numero=numero,
                referencia_mes=hoje.replace(day=1),
                valor=Decimal("650.00"),
                data_vencimento=hoje,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=hoje - timedelta(days=numero),
            )

        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {
                "tipo": "associados_ativos_com_3_parcelas_pagas",
                "formato": "csv",
                "filtros": {
                    "data_inicio": (hoje - timedelta(days=10)).isoformat(),
                    "data_fim": hoje.isoformat(),
                    "agente_id": str(self.agente.id),
                    "faixa_mensalidade": ["200_300", "acima_500"],
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        self.assertTrue(download_response["Content-Type"].startswith("text/csv"))
        content = b"".join(download_response.streaming_content).decode("utf-8")
        self.assertIn("Associado Faixa Alvo", content)
        self.assertIn("Associado Faixa Alta", content)
        self.assertNotIn("Associado Outro Agente", content)
        self.assertNotIn("Associado Faixa Errada", content)

    def test_exportar_relatorio_de_associados_inativos_pagadores_filtra_por_status_mae(self):
        hoje = date.today()

        associado_ativo = Associado.objects.create(
            nome_completo="Associado Ativo",
            cpf_cnpj="32345678911",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato_ativo = Contrato.objects.create(
            associado=associado_ativo,
            agente=self.agente,
            valor_mensalidade=Decimal("180.00"),
            status=Contrato.Status.ATIVO,
        )
        ciclo_ativo = contrato_ativo.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="aberto",
            valor_total=Decimal("540.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_ativo,
            associado=associado_ativo,
            numero=1,
            referencia_mes=hoje.replace(day=1),
            valor=Decimal("180.00"),
            data_vencimento=hoje,
            status=Parcela.Status.DESCONTADO,
            data_pagamento=hoje,
        )

        associado_inativo = Associado.objects.create(
            nome_completo="Associado Inativo",
            cpf_cnpj="32345678912",
            status=Associado.Status.INATIVO,
            agente_responsavel=self.agente,
        )
        contrato_inativo = Contrato.objects.create(
            associado=associado_inativo,
            agente=self.agente,
            valor_mensalidade=Decimal("180.00"),
            status=Contrato.Status.ENCERRADO,
        )
        ciclo_inativo = contrato_inativo.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="fechado",
            valor_total=Decimal("540.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_inativo,
            associado=associado_inativo,
            numero=1,
            referencia_mes=hoje.replace(day=1),
            valor=Decimal("180.00"),
            data_vencimento=hoje,
            status=Parcela.Status.LIQUIDADA,
            data_pagamento=hoje,
        )

        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {
                "tipo": "associados_inativos_com_1_parcela_paga",
                "formato": "json",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        content = b"".join(download_response.streaming_content)
        exported = json.loads(content.decode("utf-8"))

        self.assertEqual([row["nome_completo"] for row in exported], ["Associado Inativo"])

    def test_exportar_relatorio_de_associados_inativos_inclui_contrato_cancelado(self):
        hoje = date.today()

        associado = Associado.objects.create(
            nome_completo="Associado Contrato Cancelado",
            cpf_cnpj="32345678913",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_mensalidade=Decimal("180.00"),
            status=Contrato.Status.CANCELADO,
        )
        ciclo = contrato.ciclos.create(
            numero=1,
            data_inicio=hoje.replace(day=1),
            data_fim=hoje.replace(day=28),
            status="fechado",
            valor_total=Decimal("540.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=hoje.replace(day=1),
            valor=Decimal("180.00"),
            data_vencimento=hoje,
            status=Parcela.Status.DESCONTADO,
            data_pagamento=hoje,
        )

        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {
                "tipo": "associados_inativos_com_1_parcela_paga",
                "formato": "json",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        content = b"".join(download_response.streaming_content)
        exported = json.loads(content.decode("utf-8"))

        self.assertEqual(
            [row["nome_completo"] for row in exported],
            ["Associado Contrato Cancelado"],
        )

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

    def test_exportar_aceita_rota_analise_com_rows_customizados(self):
        response = self.client.post(
            "/api/v1/relatorios/exportar/",
            {
                "rota": "/analise",
                "formato": "xlsx",
                "filtros": {
                    "rows": [
                        {
                            "nome": "Maria Analise",
                            "cpf_cnpj": "123.456.789-01",
                            "matricula": "MAT-0001",
                            "contrato_codigo": "CTR-001",
                            "etapa": "analise",
                            "status": "aguardando",
                            "agente": "Agente Teste",
                            "criado_em": "2026-04-11T10:30:00",
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        download_response = self.client.get(f"/api/v1/relatorios/{payload['id']}/download/")
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(
            download_response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_render_pdf_mantem_markup_de_resumo_sem_escapar_tags_html(self):
        recorded_texts: list[str] = []

        from reportlab.platypus import Paragraph as RealParagraph

        def paragraph_spy(text, style, *args, **kwargs):
            recorded_texts.append(text)
            return RealParagraph(text, style, *args, **kwargs)

        with patch("reportlab.platypus.Paragraph", side_effect=paragraph_spy):
            content = RelatorioService._render_pdf(
                "/coordenacao/refinanciamento",
                [],
                {},
            )

        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertTrue(
            any(text.startswith("<b>Rota:</b>") for text in recorded_texts),
            recorded_texts,
        )
        self.assertFalse(
            any("&lt;b&gt;Rota:&lt;/b&gt;" in text for text in recorded_texts),
            recorded_texts,
        )

    def test_definicao_tesouraria_reflete_colunas_da_secao(self):
        definition = RelatorioService._definition_for_route("/tesouraria")

        self.assertEqual(
            [column.key for column in definition.columns],
            [
                "anexos",
                "dados_bancarios",
                "chave_pix",
                "acao",
                "nome",
                "matricula_cpf",
                "agente",
                "auxilio_comissao",
                "data_solicitacao",
                "status",
            ],
        )

    def test_definicao_analise_reflete_colunas_do_dashboard(self):
        definition = RelatorioService._definition_for_route("/analise")

        self.assertEqual(
            [column.key for column in definition.columns],
            [
                "nome",
                "cpf_cnpj",
                "matricula",
                "contrato_codigo",
                "etapa",
                "status",
                "agente",
                "criado_em",
            ],
        )

    def test_summary_for_route_inclui_totais_customizados(self):
        summary = RelatorioService._summary_for_route(
            "/tesouraria",
            [{"nome": "Maria Teste"}],
            {
                "totais": {
                    "total_auxilio_liberado": "1500.00",
                    "total_comissao_agente": "120.00",
                }
            },
        )

        self.assertIn(("Total Auxilio Liberado", "1500.00"), summary)
        self.assertIn(("Total Comissao Agente", "120.00"), summary)
