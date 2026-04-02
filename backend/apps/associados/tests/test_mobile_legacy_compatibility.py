import tempfile
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetRequest, Role, User
from apps.associados.models import Associado, Auxilio2Filiacao, Documento
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import DocIssue, DocReupload, EsteiraItem, Pendencia, Transicao


@override_settings(
    MEDIA_ROOT=tempfile.mkdtemp(),
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class MobileLegacyCompatibilityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_associado = Role.objects.create(codigo="ASSOCIADO", nome="Associado")
        cls.role_associadodois = Role.objects.create(codigo="ASSOCIADODOIS", nome="Associado 2")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")

        cls.user = User.objects.create_user(
            email="associado@teste.local",
            password="Senha@123",
            first_name="Associado",
            last_name="Legado",
            is_active=True,
        )
        cls.user.roles.add(cls.role_associado, cls.role_associadodois)

        cls.analista = User.objects.create_user(
            email="analista@teste.local",
            password="Senha@123",
            first_name="Analista",
            last_name="ABASE",
            is_active=True,
        )
        cls.analista.roles.add(cls.role_analista)

        cls.associado = Associado.objects.create(
            user=cls.user,
            nome_completo="Associado Legado",
            cpf_cnpj="12345678901",
            rg="998877",
            orgao_expedidor="SSPPI",
            email=cls.user.email,
            telefone="86999999999",
            data_nascimento=date(1980, 1, 2),
            profissao="Professor",
            estado_civil=Associado.EstadoCivil.CASADO,
            cep="64000000",
            logradouro="Rua Teste",
            numero="10",
            bairro="Centro",
            cidade="Teresina",
            uf="PI",
            orgao_publico="SEFAZ",
            matricula_orgao="445566",
            situacao_servidor="Ativo",
            banco="Banco do Brasil",
            agencia="1234",
            conta="12345-6",
            tipo_conta="corrente",
            chave_pix="12345678901",
            contrato_mensalidade=Decimal("500.00"),
            contrato_prazo_meses=3,
            contrato_taxa_antecipacao=Decimal("30.00"),
            contrato_margem_disponivel=Decimal("1050.00"),
            contrato_data_aprovacao=date(2026, 1, 10),
            contrato_data_envio_primeira=date(2026, 2, 5),
            contrato_valor_antecipacao=Decimal("1500.00"),
            contrato_status_contrato="Pendente",
            contrato_mes_averbacao=date(2026, 1, 1),
            contrato_codigo_contrato="CTR-LEG-001",
            contrato_doacao_associado=Decimal("450.00"),
            calc_valor_bruto=Decimal("17082.33"),
            calc_liquido_cc=Decimal("7958.46"),
            calc_prazo_antecipacao=3,
            calc_mensalidade_associativa=Decimal("500.00"),
            anticipations_json=[
                {
                    "numeroMensalidade": 1,
                    "valorAuxilio": 500,
                    "dataEnvio": "2026-03-05",
                    "status": "Autorizado",
                }
            ],
            documents_json=[
                {"field": "cpf_frente", "relative_path": "documentos/cpf_frente.pdf"},
                {"field": "comp_endereco", "relative_path": "documentos/comp.pdf"},
            ],
            status=Associado.Status.ATIVO,
            aceite_termos=False,
            auxilio1_status="liberado",
            auxilio1_updated_at=timezone.now(),
            auxilio2_status="bloqueado",
            agente_filial="APP",
        )

        cls.contrato = Contrato.objects.create(
            associado=cls.associado,
            codigo="CTR-LEG-001",
            valor_bruto=Decimal("17082.33"),
            valor_liquido=Decimal("7958.46"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("1050.00"),
            valor_total_antecipacao=Decimal("1500.00"),
            doacao_associado=Decimal("450.00"),
            status=Contrato.Status.ATIVO,
            data_aprovacao=date(2026, 1, 10),
            data_primeira_mensalidade=date(2026, 2, 5),
            mes_averbacao=date(2026, 1, 1),
        )
        cls.ciclo = Ciclo.objects.create(
            contrato=cls.contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 30),
            status="aberto",
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )
        Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("500.00"),
            data_vencimento=date.today() - timedelta(days=10),
            status=Parcela.Status.EM_ABERTO,
        )
        Parcela.objects.create(
            ciclo=cls.ciclo,
            associado=cls.associado,
            numero=3,
            referencia_mes=date(2026, 4, 1),
            valor=Decimal("500.00"),
            data_vencimento=date.today() + timedelta(days=20),
            status=Parcela.Status.EM_ABERTO,
        )

        Documento.objects.create(
            associado=cls.associado,
            tipo=Documento.Tipo.TERMO_ADESAO,
            arquivo=SimpleUploadedFile(
                "termo_adesao.pdf",
                b"pdf",
                content_type="application/pdf",
            ),
            status=Documento.Status.APROVADO,
        )

        cls.issue = DocIssue.objects.create(
            associado=cls.associado,
            cpf_cnpj=cls.associado.cpf_cnpj,
            contrato_codigo=cls.contrato.codigo,
            analista=cls.analista,
            status=DocIssue.Status.INCOMPLETO,
            mensagem="Enviar CPF frente e comprovante.",
            documents_snapshot_json=[
                {"field": "cpf_frente"},
                {"field": "comp_endereco"},
            ],
        )
        cls.esteira = EsteiraItem.objects.create(
            associado=cls.associado,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.PENDENCIADO,
        )
        Pendencia.objects.create(
            esteira_item=cls.esteira,
            tipo="documento",
            descricao="Pendência geral de análise.",
            status=Pendencia.Status.ABERTA,
        )

    def setUp(self):
        self.client = APIClient()

    def login_legacy(self, login=None, password=None):
        response = self.client.post(
            "/api/login",
            {
                "login": login or self.associado.cpf_cnpj,
                "password": password or self.associado.matricula_orgao,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        token = response.json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return token, response.json()

    def login_v1(self, login=None, password=None):
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "login": login or self.associado.cpf_cnpj,
                "password": password or self.associado.matricula_orgao,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        access = payload["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return access, payload

    def test_legacy_login_and_core_endpoints(self):
        token, payload = self.login_legacy()
        self.assertTrue(payload["ok"])
        self.assertIn("ASSOCIADODOIS", payload["roles"])
        self.assertEqual(payload["pessoa"]["documento"], self.associado.cpf_cnpj)
        self.assertEqual(payload["resumo"]["parcelas_pagas"], 1)
        self.assertEqual(payload["resumo"]["prazo"], 3)
        self.assertIsNotNone(payload["termo_adesao"])

        home = self.client.get("/api/home")
        self.assertEqual(home.status_code, 200, home.json())
        self.assertEqual(home.json()["resumo"]["parcelas_pagas"], 1)
        self.assertEqual(home.json()["cadastro"]["auxilio1_status"], "liberado")

        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.json())
        self.assertEqual(me.json()["user"]["email"], self.user.email)

        associado_me = self.client.get("/api/associado/me")
        self.assertEqual(associado_me.status_code, 200, associado_me.json())
        self.assertEqual(
            associado_me.json()["pessoa"]["nome_razao_social"],
            self.associado.nome_completo,
        )

        a2_status = self.client.get("/api/associado/a2/status")
        self.assertEqual(a2_status.status_code, 200, a2_status.json())
        self.assertTrue(a2_status.json()["exists"])

        cadastro_status = self.client.get("/api/associadodois/status")
        self.assertEqual(cadastro_status.status_code, 200, cadastro_status.json())
        self.assertTrue(cadastro_status.json()["permissions"]["auxilio1"])

        cadastro_show = self.client.get("/api/associadodois/cadastro")
        self.assertEqual(cadastro_show.status_code, 200, cadastro_show.json())
        self.assertEqual(cadastro_show.json()["cadastro"]["cpf_cnpj"], self.associado.cpf_cnpj)

        mensalidades = self.client.get("/api/app/mensalidades")
        self.assertEqual(mensalidades.status_code, 200, mensalidades.json())
        self.assertEqual(len(mensalidades.json()["parcelas"]), 3)

        mensalidades_ciclo = self.client.get("/api/app/mensalidades/ciclo")
        self.assertEqual(mensalidades_ciclo.status_code, 200, mensalidades_ciclo.json())
        self.assertEqual(len(mensalidades_ciclo.json()["parcelas"]), 3)

        antecipacao = self.client.get("/api/app/antecipacao/historico")
        self.assertEqual(antecipacao.status_code, 200, antecipacao.json())
        self.assertEqual(antecipacao.json()["historico"][0]["valor"], 500)

        client_log = self.client.post("/api/app/client-log", {"scope": "test"}, format="json")
        self.assertEqual(client_log.status_code, 200, client_log.json())
        self.assertTrue(client_log.json()["ok"])

        termo = self.client.get(f"/api/associado/termo-adesao?token={token}")
        self.assertEqual(termo.status_code, 302)
        self.assertIn("/media/", termo["Location"])

    def test_legacy_issue_reupload_terms_contact_auxilio2_and_logout(self):
        self.login_legacy(login=self.user.email, password="Senha@123")

        issues = self.client.get("/api/associadodois/issues/my")
        self.assertEqual(issues.status_code, 200, issues.json())
        self.assertEqual(len(issues.json()["issues"]), 1)
        self.assertIn("doc_front", issues.json()["issues"][0]["required_docs"])
        self.assertIn("comprovante_endereco", issues.json()["issues"][0]["required_docs"])

        reupload = self.client.post(
            "/api/associadodois/reuploads",
            {
                "associadodois_doc_issue_id": self.issue.id,
                "notes": "Reenvio mobile",
                "cpf_frente": SimpleUploadedFile("cpf_frente.jpg", b"123", content_type="image/jpeg"),
                "comp_endereco": SimpleUploadedFile("comp.png", b"456", content_type="image/png"),
            },
            format="multipart",
        )
        self.assertEqual(reupload.status_code, 200, reupload.json())
        self.assertEqual(reupload.json()["saved_count"], 2)
        self.assertEqual(DocReupload.objects.filter(doc_issue=self.issue).count(), 2)
        self.issue.refresh_from_db()
        self.assertEqual(len(self.issue.agent_uploads_json), 2)

        aceite = self.client.post("/api/associadodois/aceite-termos")
        self.assertEqual(aceite.status_code, 200, aceite.json())
        self.associado.refresh_from_db()
        self.assertTrue(self.associado.aceite_termos)

        contato = self.client.post("/api/associadodois/contato")
        self.assertEqual(contato.status_code, 200, contato.json())
        self.associado.refresh_from_db()
        self.assertEqual(self.associado.contato_status, "solicitado")

        aux_status = self.client.get("/api/associadodois/auxilio2/status")
        self.assertEqual(aux_status.status_code, 200, aux_status.json())
        self.assertEqual(aux_status.json()["status"], "bloqueado")

        charge = self.client.post("/api/associadodois/auxilio2/charge-30")
        self.assertEqual(charge.status_code, 200, charge.json())
        self.assertTrue(charge.json()["ok"])
        self.assertEqual(charge.json()["status"], "pendente")
        self.assertIsNotNone(charge.json()["chargeId"])
        self.assertIsNotNone(charge.json()["filiacaoId"])
        self.assertEqual(Auxilio2Filiacao.objects.count(), 1)

        aux_resumo = self.client.get("/api/associadodois/auxilio2/resumo")
        self.assertEqual(aux_resumo.status_code, 200, aux_resumo.json())
        self.assertEqual(aux_resumo.json()["status"], "pendente")

        logout = self.client.post("/api/logout")
        self.assertEqual(logout.status_code, 200, logout.json())
        home_after_logout = self.client.get("/api/home")
        self.assertEqual(home_after_logout.status_code, 401)

    def test_legacy_register_check_email_update_basico_and_password_reset(self):
        check_existing = self.client.get("/api/auth/check-email", {"email": self.user.email})
        self.assertEqual(check_existing.status_code, 200, check_existing.json())
        self.assertTrue(check_existing.json()["exists"])
        self.assertIn("users", check_existing.json()["sources"])

        register = self.client.post(
            "/api/auth/register",
            {
                "name": "Novo Cadastro",
                "email": "novo@teste.local",
                "password": "Senha@123",
                "password_confirmation": "Senha@123",
                "terms": True,
                "terms_version": "1.0",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201, register.json())
        self.assertTrue(register.json()["ok"])
        self.assertIn("ASSOCIADODOIS", register.json()["roles"])

        token = register.json()["token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        check_cpf = self.client.get("/api/associadodois/check-cpf", {"cpf": self.associado.cpf_cnpj})
        self.assertEqual(check_cpf.status_code, 200, check_cpf.json())
        self.assertTrue(check_cpf.json()["exists"])

        atualizar = self.client.post(
            "/api/associadodois/atualizar-basico",
            {
                "doc_type": "CPF",
                "cpf_cnpj": "98765432100",
                "full_name": "Novo Cadastro",
                "birth_date": "01/02/1990",
                "cep": "64000000",
                "address": "Rua Nova",
                "address_number": "100",
                "neighborhood": "Centro",
                "city": "Teresina",
                "uf": "PI",
                "cellphone": "86988887777",
                "orgao_publico": "SEDUC",
                "situacao_servidor": "Ativo",
                "matricula_servidor_publico": "778899",
                "email": "novo@teste.local",
                "bank_name": "104",
                "bank_agency": "1111",
                "bank_account": "22222-3",
                "account_type": "corrente",
                "pix_key": "98765432100",
            },
            format="multipart",
        )
        self.assertEqual(atualizar.status_code, 200, atualizar.json())
        self.assertTrue(atualizar.json()["ok"])
        novo_associado = Associado.objects.get(cpf_cnpj="98765432100")
        self.assertEqual(novo_associado.user.email, "novo@teste.local")
        self.assertTrue(EsteiraItem.objects.filter(associado=novo_associado).exists())
        self.assertEqual(
            Transicao.objects.filter(
                esteira_item__associado=novo_associado,
                acao="criar_cadastro",
            ).count(),
            1,
        )

        forgot = self.client.post(
            "/api/auth/forgot-password",
            {"email": "novo@teste.local"},
            format="json",
        )
        self.assertEqual(forgot.status_code, 200, forgot.json())
        self.assertEqual(len(mail.outbox), 1)

        reset_request = PasswordResetRequest.objects.get(email="novo@teste.local")
        reset = self.client.post(
            "/api/auth/reset-password",
            {
                "email": "novo@teste.local",
                "token": reset_request.token,
                "password": "NovaSenha@123",
                "password_confirmation": "NovaSenha@123",
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200, reset.json())
        registered_user = User.objects.get(email="novo@teste.local")
        self.assertTrue(registered_user.check_password("NovaSenha@123"))

    def test_v1_login_and_app_endpoints(self):
        _access, payload = self.login_v1()
        self.assertIn("refresh", payload)
        self.assertIn("ASSOCIADO", payload["roles"])

        me = self.client.get("/api/v1/app/me/")
        self.assertEqual(me.status_code, 200, me.json())
        self.assertEqual(me.json()["pessoa"]["documento"], self.associado.cpf_cnpj)
        self.assertEqual(me.json()["resumo"]["parcelas_pagas"], 1)
        self.assertEqual(me.json()["cadastro"]["auxilio1_status"], "liberado")
        self.assertEqual(len(me.json()["issues"]), 1)

        cadastro = self.client.get("/api/v1/app/cadastro/")
        self.assertEqual(cadastro.status_code, 200, cadastro.json())
        self.assertTrue(cadastro.json()["permissions"]["auxilio1"])
        self.assertTrue(cadastro.json()["exists"])

        pendencias = self.client.get("/api/v1/app/pendencias/")
        self.assertEqual(pendencias.status_code, 200, pendencias.json())
        self.assertEqual(len(pendencias.json()["issues"]), 1)
        self.assertIn("doc_front", pendencias.json()["issues"][0]["required_docs"])

        mensalidades = self.client.get("/api/v1/app/mensalidades/")
        self.assertEqual(mensalidades.status_code, 200, mensalidades.json())
        self.assertEqual(len(mensalidades.json()["parcelas"]), 3)

        antecipacao = self.client.get("/api/v1/app/antecipacao/")
        self.assertEqual(antecipacao.status_code, 200, antecipacao.json())
        self.assertEqual(antecipacao.json()["historico"][0]["valor"], 500)

    def test_v1_issue_reupload_terms_contact_auxilio2_and_logout(self):
        _access, payload = self.login_v1(login=self.user.email, password="Senha@123")

        reupload = self.client.post(
            "/api/v1/app/pendencias/reuploads/",
            {
                "issue_id": self.issue.id,
                "notes": "Reenvio mobile v1",
                "cpf_frente": SimpleUploadedFile("cpf_frente_v1.jpg", b"123", content_type="image/jpeg"),
                "comp_endereco": SimpleUploadedFile("comp_v1.png", b"456", content_type="image/png"),
            },
            format="multipart",
        )
        self.assertEqual(reupload.status_code, 200, reupload.json())
        self.assertEqual(reupload.json()["saved_count"], 2)

        aceite = self.client.post("/api/v1/app/termos/aceite/")
        self.assertEqual(aceite.status_code, 200, aceite.json())

        contato = self.client.post("/api/v1/app/contato/")
        self.assertEqual(contato.status_code, 200, contato.json())

        aux_status = self.client.get("/api/v1/app/auxilio2/status/")
        self.assertEqual(aux_status.status_code, 200, aux_status.json())
        self.assertEqual(aux_status.json()["status"], "bloqueado")

        charge = self.client.post("/api/v1/app/auxilio2/charge/")
        self.assertEqual(charge.status_code, 200, charge.json())
        self.assertTrue(charge.json()["ok"])
        self.assertEqual(charge.json()["status"], "pendente")
        self.assertIsNotNone(charge.json()["chargeId"])

        aux_resumo = self.client.get("/api/v1/app/auxilio2/resumo/")
        self.assertEqual(aux_resumo.status_code, 200, aux_resumo.json())
        self.assertEqual(aux_resumo.json()["status"], "pendente")

        logout = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh": payload["refresh"]},
            format="json",
        )
        self.assertEqual(logout.status_code, 205)

    def test_v1_register_update_basico_document_upload_and_password_reset(self):
        register = self.client.post(
            "/api/v1/auth/register/",
            {
                "name": "Novo Cadastro V1",
                "email": "novo-v1@teste.local",
                "password": "Senha@123",
                "password_confirmation": "Senha@123",
                "terms": True,
                "terms_version": "1.0",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201, register.json())
        self.assertTrue(register.json()["ok"])
        self.assertIn("ASSOCIADODOIS", register.json()["roles"])
        self.assertIn("ASSOCIADO", register.json()["roles"])

        access = register.json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        bootstrap = self.client.get("/api/v1/app/me/")
        self.assertEqual(bootstrap.status_code, 200, bootstrap.json())
        self.assertFalse(bootstrap.json()["exists"])

        check_cpf = self.client.get("/api/v1/app/cadastro/check-cpf/", {"cpf": self.associado.cpf_cnpj})
        self.assertEqual(check_cpf.status_code, 200, check_cpf.json())
        self.assertTrue(check_cpf.json()["exists"])

        atualizar = self.client.post(
            "/api/v1/app/cadastro/",
            {
                "doc_type": "CPF",
                "cpf_cnpj": "98765432100",
                "full_name": "Novo Cadastro V1",
                "birth_date": "01/02/1990",
                "cep": "64000000",
                "address": "Rua Nova",
                "address_number": "100",
                "neighborhood": "Centro",
                "city": "Teresina",
                "uf": "PI",
                "cellphone": "86988887777",
                "orgao_publico": "SEDUC",
                "situacao_servidor": "Ativo",
                "matricula_servidor_publico": "778899",
                "email": "novo-v1@teste.local",
                "bank_name": "104",
                "bank_agency": "1111",
                "bank_account": "22222-3",
                "account_type": "corrente",
                "pix_key": "98765432100",
            },
            format="multipart",
        )
        self.assertEqual(atualizar.status_code, 200, atualizar.json())
        self.assertTrue(atualizar.json()["ok"])

        documento = self.client.post(
            "/api/v1/app/documentos/",
            {
                "tipo": Documento.Tipo.CONTRACHEQUE,
                "arquivo": SimpleUploadedFile("contracheque.pdf", b"pdf", content_type="application/pdf"),
                "observacao": "upload v1",
            },
            format="multipart",
        )
        self.assertEqual(documento.status_code, 201, documento.json())

        forgot = self.client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "novo-v1@teste.local"},
            format="json",
        )
        self.assertEqual(forgot.status_code, 200, forgot.json())

        reset_request = PasswordResetRequest.objects.get(email="novo-v1@teste.local")
        reset = self.client.post(
            "/api/v1/auth/reset-password/",
            {
                "token": reset_request.token,
                "password": "NovaSenha@123",
                "password_confirmation": "NovaSenha@123",
            },
            format="json",
        )
        self.assertEqual(reset.status_code, 200, reset.json())
        registered_user = User.objects.get(email="novo-v1@teste.local")
        self.assertTrue(registered_user.check_password("NovaSenha@123"))

    def test_v1_app_cadastro_accepts_mobile_new_payload_and_creates_associado(self):
        register = self.client.post(
            "/api/v1/auth/register/",
            {
                "name": "Cadastro Mobile Novo",
                "email": "mobile-new@teste.local",
                "password": "Senha@123",
                "password_confirmation": "Senha@123",
                "terms": True,
                "terms_version": "1.0",
            },
            format="json",
        )
        self.assertEqual(register.status_code, 201, register.json())
        access = register.json()["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(
            "/api/v1/app/cadastro/",
            {
                "doc_type": "CPF",
                "cpf_cnpj": "98765432100",
                "full_name": "Cadastro Mobile Novo",
                "birth_date": "01/02/1990",
                "rg": "112233",
                "orgao_expedidor": "SSPPI",
                "estado_civil": "CASADO",
                "profissao": "PROFESSOR",
                "cargo": "SERVIDOR",
                "cep": "64000000",
                "logradouro": "Rua Atualizada",
                "numero": "100",
                "complemento": "APTO 3",
                "bairro": "CENTRO",
                "cidade": "TERESINA",
                "uf": "PI",
                "cellphone": "86988887777",
                "orgao_publico": "SEDUC",
                "situacao_servidor": "Ativo",
                "matricula_orgao": "778899",
                "email": "mobile-new@teste.local",
                "banco": "104",
                "agencia": "1111",
                "conta": "22222-3",
                "tipo_conta": "corrente",
                "chave_pix": "98765432100",
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()["ok"])

        user = User.objects.get(email="mobile-new@teste.local")
        associado = Associado.objects.get(user=user)
        self.assertEqual(associado.cpf_cnpj, "98765432100")
        self.assertEqual(associado.nome_completo, "Cadastro Mobile Novo")
        self.assertEqual(associado.logradouro, "Rua Atualizada")
        self.assertEqual(associado.numero, "100")
        self.assertEqual(associado.bairro, "CENTRO")
        self.assertEqual(associado.cidade, "TERESINA")
        self.assertEqual(associado.matricula_orgao, "778899")
        self.assertEqual(associado.banco, "104")
        self.assertEqual(associado.agencia, "1111")
        self.assertEqual(associado.conta, "22222-3")
        self.assertEqual(associado.tipo_conta, "corrente")
        self.assertEqual(associado.chave_pix, "98765432100")
        self.assertEqual(associado.profissao, "PROFESSOR")
        self.assertEqual(associado.cargo, "SERVIDOR")
        self.assertEqual(associado.status, Associado.Status.EM_ANALISE)
        self.assertTrue(EsteiraItem.objects.filter(associado=associado).exists())
        self.assertEqual(
            Transicao.objects.filter(
                esteira_item__associado=associado,
                acao="criar_cadastro",
            ).count(),
            1,
        )

        upload_response = self.client.post(
            "/api/v1/app/pendencias/reuploads/",
            {
                "cpf_frente": SimpleUploadedFile(
                    "cpf-frente.jpg",
                    b"jpg-front",
                    content_type="image/jpeg",
                ),
                "comp_endereco": SimpleUploadedFile(
                    "comp-endereco.pdf",
                    b"pdf-endereco",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 200, upload_response.json())
        self.assertTrue(upload_response.json()["ok"])
        self.assertEqual(upload_response.json()["saved_count"], 2)
        self.assertEqual(
            Documento.objects.filter(
                associado=associado,
                tipo__in=[
                    Documento.Tipo.DOCUMENTO_FRENTE,
                    Documento.Tipo.COMPROVANTE_RESIDENCIA,
                ],
            ).count(),
            2,
        )

        status_response = self.client.get("/api/v1/app/cadastro/")
        self.assertEqual(status_response.status_code, 200, status_response.json())
        cadastro = status_response.json()["cadastro"]
        self.assertEqual(cadastro["logradouro"], "Rua Atualizada")
        self.assertEqual(cadastro["numero"], "100")
        self.assertEqual(cadastro["bairro"], "CENTRO")
        self.assertEqual(cadastro["cidade"], "TERESINA")
        self.assertEqual(cadastro["matricula_orgao"], "778899")
        self.assertEqual(cadastro["banco"], "104")
        self.assertEqual(cadastro["tipo_conta"], "corrente")
        self.assertEqual(cadastro["chave_pix"], "98765432100")
        self.assertEqual(cadastro["profissao"], "PROFESSOR")
        self.assertEqual(cadastro["cargo"], "SERVIDOR")

        analista_client = APIClient()
        analista_client.force_authenticate(self.analista)
        filas = analista_client.get(
            "/api/v1/analise/filas/",
            {"secao": "ver_todos", "search": "Cadastro Mobile Novo"},
        )
        self.assertEqual(filas.status_code, 200, filas.json())
        self.assertIn(
            associado.id,
            [item["associado"]["id"] for item in filas.json()["results"]],
        )

    def test_backfill_missing_mobile_esteira_creates_single_item_idempotently(self):
        user = User.objects.create_user(
            email="backfill.mobile@teste.local",
            password="Senha@123",
            first_name="Backfill",
            last_name="Mobile",
            is_active=True,
        )
        user.roles.add(self.role_associado, self.role_associadodois)
        associado = Associado.objects.create(
            user=user,
            nome_completo="Backfill Mobile",
            cpf_cnpj="99888777666",
            email=user.email,
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao="112233",
            status=Associado.Status.EM_ANALISE,
        )
        self.assertFalse(EsteiraItem.objects.filter(associado=associado).exists())

        with mock.patch(
            "apps.associados.management.commands.backfill_missing_mobile_esteira.select_restore_uploaded_by",
            return_value=self.analista,
        ):
            stdout = StringIO()
            call_command(
                "backfill_missing_mobile_esteira",
                "--cpf",
                associado.cpf_cnpj,
                "--execute",
                stdout=stdout,
            )

            second_stdout = StringIO()
            call_command(
                "backfill_missing_mobile_esteira",
                "--cpf",
                associado.cpf_cnpj,
                "--execute",
                stdout=second_stdout,
            )

        self.assertTrue(EsteiraItem.objects.filter(associado=associado).exists())
        self.assertEqual(
            Transicao.objects.filter(
                esteira_item__associado=associado,
                acao="criar_cadastro",
            ).count(),
            1,
        )
        self.assertIn("1 item(ns) de esteira criado(s)", stdout.getvalue())
        self.assertIn("Associados elegíveis: 0", second_stdout.getvalue())
