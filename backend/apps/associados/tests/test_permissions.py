import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado, DadosBancarios, Documento, Endereco, ContatoHistorico


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class AssociadoPermissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        cls.admin = cls._create_user("admin@teste.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@teste.local", cls.role_agente, "Agente")
        cls.outro_agente = cls._create_user(
            "agente2@teste.local",
            cls.role_agente,
            "Outro Agente",
        )

        cls.associado = Associado.objects.create(
            nome_completo="Associado Restrito",
            cpf_cnpj="12345678901",
            email="associado@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            agente_responsavel=cls.agente,
        )
        Documento.objects.create(
            associado=cls.associado,
            tipo=Documento.Tipo.CPF,
            arquivo=SimpleUploadedFile(
                "documento.pdf",
                b"conteudo",
                content_type="application/pdf",
            ),
        )
        cls.associado_outro_agente = Associado.objects.create(
            nome_completo="Associado Outro Agente",
            cpf_cnpj="12345678902",
            email="outro@teste.local",
            telefone="86988888888",
            orgao_publico="SEFAZ",
            agente_responsavel=cls.outro_agente,
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
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente)

        self.other_agent_client = APIClient()
        self.other_agent_client.force_authenticate(self.outro_agente)

    def test_agente_nao_pode_listar_associados(self):
        response = self.agent_client.get("/api/v1/associados/")
        self.assertEqual(response.status_code, 403)

    def test_agente_pode_visualizar_proprio_associado(self):
        response = self.agent_client.get(f"/api/v1/associados/{self.associado.id}/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["id"], self.associado.id)
        self.assertEqual(len(response.json()["documentos"]), 1)

    def test_agente_pode_atualizar_proprio_associado(self):
        response = self.agent_client.patch(
            f"/api/v1/associados/{self.associado.id}/",
            {
                "nome_completo": "Associado Corrigido",
                "contato": {
                    "email": "corrigido@teste.local",
                    "celular": "86991111111",
                    "orgao_publico": "SEFAZ",
                    "situacao_servidor": "ativo",
                    "matricula_servidor": "MAT-123",
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.associado.refresh_from_db()
        self.assertEqual(self.associado.nome_completo, "Associado Corrigido")
        self.assertEqual(self.associado.email, "corrigido@teste.local")
        self.assertEqual(response.json()["contato"]["email"], "corrigido@teste.local")

    def test_agente_nao_pode_atualizar_associado_de_outro_agente(self):
        response = self.agent_client.patch(
            f"/api/v1/associados/{self.associado_outro_agente.id}/",
            {"nome_completo": "Nao Deve Atualizar"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_agente_nao_pode_visualizar_associado_de_outro_agente(self):
        response = self.agent_client.get(
            f"/api/v1/associados/{self.associado_outro_agente.id}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_agente_pode_criar_associado(self):
        response = self.agent_client.post(
            "/api/v1/associados/",
            {
                "tipo_documento": "CPF",
                "cpf_cnpj": "22345678901",
                "nome_completo": "Novo Associado",
                "endereco": {
                    "cep": "64000000",
                    "endereco": "Rua Teste",
                    "numero": "10",
                    "bairro": "Centro",
                    "cidade": "Teresina",
                    "uf": "PI",
                },
                "dados_bancarios": {
                    "banco": "Banco do Brasil",
                    "agencia": "1234",
                    "conta": "12345-6",
                    "tipo_conta": "corrente",
                },
                "contato": {
                    "celular": "86999999999",
                    "email": "novo@teste.local",
                    "orgao_publico": "SEFAZ",
                    "situacao_servidor": "ativo",
                    "matricula_servidor": "MAT-1",
                },
                "valor_bruto_total": "1500.00",
                "valor_liquido": "1200.00",
                "prazo_meses": 3,
                "taxa_antecipacao": "1.50",
                "mensalidade": "500.00",
                "margem_disponivel": "900.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        criado = Associado.objects.get(cpf_cnpj="22345678901")
        self.assertEqual(criado.agente_responsavel, self.agente)
        self.assertEqual(criado.cep, "64000000")
        self.assertEqual(criado.logradouro, "Rua Teste")
        self.assertEqual(criado.banco, "Banco do Brasil")
        self.assertEqual(criado.agencia, "1234")
        self.assertEqual(criado.situacao_servidor, "ativo")
        self.assertFalse(Endereco.objects.filter(associado=criado).exists())
        self.assertFalse(DadosBancarios.objects.filter(associado=criado).exists())
        self.assertFalse(ContatoHistorico.objects.filter(associado=criado).exists())

    def test_agente_pode_validar_documento_duplicado(self):
        response = self.agent_client.get(
            "/api/v1/associados/validar-documento/",
            {"cpf_cnpj": self.associado.cpf_cnpj},
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()["exists"])
        self.assertEqual(response.json()["agente_nome"], self.agente.full_name)
        self.assertIn(self.agente.full_name, response.json()["message"])

    def test_upload_do_mesmo_tipo_substitui_documento_existente(self):
        response = self.agent_client.post(
            f"/api/v1/associados/{self.associado.id}/documentos/",
            {
                "tipo": Documento.Tipo.CPF,
                "arquivo": SimpleUploadedFile(
                    "documento-atualizado.pdf",
                    b"novo-conteudo",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 201, response.json())
        documentos = Documento.objects.filter(associado=self.associado, tipo=Documento.Tipo.CPF)
        self.assertEqual(documentos.count(), 1)
        self.assertIn("documento-atualizado", documentos.get().arquivo.name)

    def test_create_duplicado_retorna_nome_do_agente_responsavel(self):
        response = self.agent_client.post(
            "/api/v1/associados/",
            {
                "tipo_documento": "CPF",
                "cpf_cnpj": self.associado.cpf_cnpj,
                "nome_completo": "Associado Duplicado",
                "endereco": {
                    "cep": "64000000",
                    "endereco": "Rua Teste",
                    "numero": "10",
                    "bairro": "Centro",
                    "cidade": "Teresina",
                    "uf": "PI",
                },
                "dados_bancarios": {
                    "banco": "Banco do Brasil",
                    "agencia": "1234",
                    "conta": "12345-6",
                    "tipo_conta": "corrente",
                },
                "contato": {
                    "celular": "86999999999",
                    "email": "duplicado@teste.local",
                    "orgao_publico": "SEFAZ",
                    "situacao_servidor": "ativo",
                    "matricula_servidor": "MAT-2",
                },
                "valor_bruto_total": "1500.00",
                "valor_liquido": "1200.00",
                "prazo_meses": 3,
                "taxa_antecipacao": "1.50",
                "mensalidade": "500.00",
                "margem_disponivel": "900.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn(self.agente.full_name, response.json()["cpf_cnpj"][0])

    def test_admin_pode_listar_associados(self):
        response = self.admin_client.get("/api/v1/associados/")
        self.assertEqual(response.status_code, 200, response.json())
