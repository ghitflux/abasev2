from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AgentePagamentosViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_tesoureiro = Role.objects.create(
            codigo="TESOUREIRO",
            nome="Tesoureiro",
        )

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.outro_agente = cls._create_user(
            "outro-agente@abase.local",
            cls.role_agente,
            "Outro",
        )
        cls.tesoureiro = cls._create_user(
            "tes@abase.local",
            cls.role_tesoureiro,
            "Tesoureiro",
        )

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
        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente)

        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

    def _create_contract(self, *, cpf: str, nome: str, agente: User) -> Contrato:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            status=Associado.Status.ATIVO,
            agente_responsavel=agente,
            orgao_publico="SEFAZ",
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 10),
            data_aprovacao=date(2026, 1, 12),
            auxilio_liberado_em=date(2026, 1, 12),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 20),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 3, 20),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            numero=3,
            referencia_mes=date(2026, 4, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 4, 5),
            status=Parcela.Status.EM_ABERTO,
        )
        return contrato

    def test_agente_lista_apenas_proprios_pagamentos_com_anexos(self):
        contrato = self._create_contract(
            cpf="12345678901",
            nome="Associado do Agente",
            agente=self.agente,
        )
        self._create_contract(
            cpf="10987654321",
            nome="Associado de Outro Agente",
            agente=self.outro_agente,
        )

        Comprovante.objects.create(
            contrato=contrato,
            refinanciamento=None,
            tipo=Comprovante.Tipo.PIX,
            papel=Comprovante.Papel.ASSOCIADO,
            arquivo=SimpleUploadedFile(
                "contrato-associado.pdf",
                b"arquivo associado",
                content_type="application/pdf",
            ),
            enviado_por=self.tesoureiro,
        )
        Comprovante.objects.create(
            contrato=contrato,
            refinanciamento=None,
            tipo=Comprovante.Tipo.PIX,
            papel=Comprovante.Papel.AGENTE,
            arquivo=SimpleUploadedFile(
                "contrato-agente.pdf",
                b"arquivo agente",
                content_type="application/pdf",
            ),
            enviado_por=self.tesoureiro,
        )

        arquivo_retorno = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-fevereiro.txt",
            arquivo_url="arquivos_retorno/retorno-fevereiro.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=date(2026, 2, 1),
            uploaded_by=self.tesoureiro,
        )
        parcela_fevereiro = contrato.ciclos.get().parcelas.get(numero=1)
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_retorno,
            linha_numero=1,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            matricula_servidor=contrato.associado.matricula,
            nome_servidor=contrato.associado.nome_completo,
            cargo="Servidor",
            competencia="02/2026",
            valor_descontado=Decimal("500.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Efetivado",
            orgao_codigo="001",
            orgao_pagto_codigo="001",
            orgao_pagto_nome="SEFAZ",
            associado=contrato.associado,
            parcela=parcela_fevereiro,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )

        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-marco",
            referencia_month=date(2026, 3, 1),
            status_code="1",
            matricula=contrato.associado.matricula,
            orgao_pagto="001",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=Decimal("500.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_forma_pagamento="PIX",
            manual_comprovante_path="comprovantes/manual-marco.pdf",
            source_file_path="arquivos_retorno/retorno-marco.txt",
        )

        response = self.agent_client.get("/api/v1/agente/pagamentos/")
        self.assertEqual(response.status_code, 200, response.json())

        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["resumo"]["total"], 1)
        self.assertEqual(payload["resumo"]["efetivados"], 1)
        self.assertEqual(payload["resumo"]["com_anexos"], 1)
        self.assertEqual(payload["resumo"]["parcelas_pagas"], 2)

        row = payload["results"][0]
        self.assertEqual(row["contrato_codigo"], contrato.codigo)
        self.assertEqual(len(row["comprovantes_efetivacao"]), 2)
        self.assertEqual(row["parcelas_total"], 3)
        self.assertEqual(row["parcelas_pagas"], 2)

        ciclo = row["ciclos"][0]
        parcela_fev = next(parcela for parcela in ciclo["parcelas"] if parcela["numero"] == 1)
        parcela_mar = next(parcela for parcela in ciclo["parcelas"] if parcela["numero"] == 2)

        self.assertEqual(parcela_fev["comprovantes"][0]["origem"], "arquivo_retorno")
        self.assertIn("/media/arquivos_retorno/retorno-fevereiro.txt", parcela_fev["comprovantes"][0]["url"])
        self.assertEqual(parcela_mar["comprovantes"][0]["origem"], "manual")
        self.assertIn("/media/comprovantes/manual-marco.pdf", parcela_mar["comprovantes"][0]["url"])

    def test_filtro_por_mes_retorna_apenas_parcelas_da_competencia(self):
        contrato = self._create_contract(
            cpf="55544433322",
            nome="Associado Filtro",
            agente=self.agente,
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-marco-2",
            referencia_month=date(2026, 3, 1),
            status_code="1",
            matricula=contrato.associado.matricula,
            orgao_pagto="001",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=Decimal("500.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_forma_pagamento="PIX",
            manual_comprovante_path="comprovantes/manual-marco-2.pdf",
            source_file_path="arquivos_retorno/retorno-marco-2.txt",
        )

        response = self.agent_client.get(
            "/api/v1/agente/pagamentos/",
            {"mes": "2026-03"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        row = response.json()["results"][0]
        self.assertEqual(row["parcelas_total"], 1)
        self.assertEqual(row["parcelas_pagas"], 1)
        self.assertEqual(len(row["ciclos"]), 1)
        self.assertEqual(len(row["ciclos"][0]["parcelas"]), 1)
        self.assertEqual(row["ciclos"][0]["parcelas"][0]["referencia_mes"], "2026-03-01")

    def test_tesoureiro_pode_listar_contratos_efetivados(self):
        contrato_agente = self._create_contract(
            cpf="11122233344",
            nome="Associado Tesouraria A",
            agente=self.agente,
        )
        contrato_outro_agente = self._create_contract(
            cpf="99988877766",
            nome="Associado Tesouraria B",
            agente=self.outro_agente,
        )

        response = self.tes_client.get("/api/v1/agente/pagamentos/")
        self.assertEqual(response.status_code, 200, response.json())

        payload = response.json()
        self.assertEqual(payload["count"], 2)
        codigos = {row["contrato_codigo"] for row in payload["results"]}

        self.assertIn(contrato_agente.codigo, codigos)
        self.assertIn(contrato_outro_agente.codigo, codigos)
