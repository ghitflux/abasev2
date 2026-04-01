from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato


class ConfiguracaoComissaoViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_coordenador = Role.objects.create(
            codigo="COORDENADOR",
            nome="Coordenador",
        )
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        cls.admin = cls._create_user("admin.comissao@teste.local", "Admin", cls.role_admin)
        cls.coordenador = cls._create_user(
            "coord.comissao@teste.local",
            "Coord",
            cls.role_coordenador,
        )
        cls.agente = cls._create_user("agente.comissao@teste.local", "Agente", cls.role_agente)
        cls.outro_agente = cls._create_user(
            "agente.override@teste.local",
            "Override",
            cls.role_agente,
        )

    @classmethod
    def _create_user(cls, email: str, first_name: str, role: Role) -> User:
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

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

        self.agente_client = APIClient()
        self.agente_client.force_authenticate(self.agente)

    def _cadastro_payload(
        self,
        *,
        cpf: str,
        agente_id: int,
        percentual_repasse: str | None = None,
    ) -> dict[str, object]:
        payload = {
            "tipo_documento": "CPF",
            "cpf_cnpj": cpf,
            "nome_completo": f"Associado {cpf[-4:]}",
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
                "email": f"{cpf}@teste.local",
                "orgao_publico": "SEFAZ",
                "situacao_servidor": "ativo",
                "matricula_servidor": f"MAT-{cpf[-4:]}",
            },
            "valor_bruto_total": "1500.00",
            "valor_liquido": "1200.00",
            "prazo_meses": 3,
            "taxa_antecipacao": "1.50",
            "mensalidade": "500.00",
            "margem_disponivel": "900.00",
            "agente_responsavel_id": agente_id,
        }
        if percentual_repasse is not None:
            payload["percentual_repasse"] = percentual_repasse
        return payload

    def test_agente_nao_tem_acesso_as_configuracoes_de_comissao(self):
        response = self.agente_client.get("/api/v1/configuracoes/comissoes/")
        self.assertEqual(response.status_code, 403)

    def test_admin_aplica_global_override_individual_e_remove_override(self):
        response = self.admin_client.post(
            "/api/v1/configuracoes/comissoes/global/",
            {"percentual": "11.50", "motivo": "Padrão operacional"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["global_config"]["percentual"], "11.50")

        response = self.coord_client.post(
            "/api/v1/configuracoes/comissoes/agentes/",
            {
                "agentes": [self.outro_agente.id],
                "percentual": "13.25",
                "motivo": "Campanha dedicada",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        agente_row = next(
            item
            for item in response.json()["agentes"]
            if item["agente_id"] == self.outro_agente.id
        )
        self.assertEqual(agente_row["percentual_efetivo"], "13.25")
        self.assertEqual(agente_row["percentual_override"], "13.25")
        self.assertTrue(agente_row["possui_override"])

        response = self.admin_client.post(
            f"/api/v1/configuracoes/comissoes/{self.outro_agente.id}/remover-override/",
            {"motivo": "Fim da campanha"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        agente_row = next(
            item
            for item in response.json()["agentes"]
            if item["agente_id"] == self.outro_agente.id
        )
        self.assertEqual(agente_row["percentual_efetivo"], "11.50")
        self.assertIsNone(agente_row["percentual_override"])
        self.assertFalse(agente_row["possui_override"])

    def test_cadastro_novo_usa_percentual_global_e_override_individual(self):
        response = self.admin_client.post(
            "/api/v1/configuracoes/comissoes/global/",
            {"percentual": "11.50", "motivo": "Padrão do mês"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        response = self.admin_client.post(
            "/api/v1/configuracoes/comissoes/agentes/",
            {
                "agentes": [self.outro_agente.id],
                "percentual": "12.50",
                "motivo": "Override dedicado",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        response = self.admin_client.post(
            "/api/v1/associados/",
            self._cadastro_payload(cpf="42345678901", agente_id=self.outro_agente.id),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="42345678901")
        contrato = Contrato.objects.filter(associado=associado).latest("created_at")
        self.assertEqual(associado.auxilio_taxa, Decimal("12.50"))
        self.assertEqual(contrato.comissao_agente, Decimal("131.25"))

        response = self.admin_client.post(
            "/api/v1/associados/",
            self._cadastro_payload(cpf="42345678902", agente_id=self.agente.id),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="42345678902")
        contrato = Contrato.objects.filter(associado=associado).latest("created_at")
        self.assertEqual(associado.auxilio_taxa, Decimal("11.50"))
        self.assertEqual(contrato.comissao_agente, Decimal("120.75"))

    def test_admin_pode_definir_percentual_manual_no_cadastro(self):
        response = self.admin_client.post(
            "/api/v1/associados/",
            self._cadastro_payload(
                cpf="42345678903",
                agente_id=self.outro_agente.id,
                percentual_repasse="14.75",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="42345678903")
        contrato = Contrato.objects.filter(associado=associado).latest("created_at")
        self.assertEqual(associado.auxilio_taxa, Decimal("14.75"))
        self.assertEqual(contrato.comissao_agente, Decimal("154.88"))
