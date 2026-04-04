from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato


class AdminUserManagementTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_coordenador = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")
        cls.role_tesoureiro = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")
        cls.role_associado = Role.objects.create(codigo="ASSOCIADO", nome="Associado")

        cls.admin = cls._create_user("admin@teste.local", "Admin", cls.role_admin)
        cls.coordenador = cls._create_user(
            "coord@teste.local",
            "Coord",
            cls.role_coordenador,
        )
        cls.agente = cls._create_user("agente@teste.local", "Agente", cls.role_agente)
        cls.outro_agente = cls._create_user(
            "agente2@teste.local",
            "Agente Dois",
            cls.role_agente,
        )
        cls.analista = cls._create_user(
            "analista@teste.local",
            "Analista",
            cls.role_analista,
        )
        cls.tesoureiro = cls._create_user(
            "tes@teste.local",
            "Tesoureiro",
            cls.role_tesoureiro,
        )
        cls.associado = cls._create_user(
            "associado@teste.local",
            "Associado",
            cls.role_associado,
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

    def _create_associado_com_contrato(
        self,
        *,
        suffix: int,
        agente: User,
        status: str = Associado.Status.ATIVO,
        matricula_servidor: str | None = None,
    ) -> tuple[Associado, Contrato]:
        associado = Associado.objects.create(
            matricula=f"TST-{suffix:05d}",
            nome_completo=f"Associado {suffix}",
            cpf_cnpj=f"{suffix:011d}",
            matricula_orgao=matricula_servidor or f"SRV-{suffix:05d}",
            status=status,
            agente_responsavel=agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
            valor_bruto="1200.00",
            valor_liquido="900.00",
            valor_mensalidade="300.00",
            margem_disponivel="600.00",
            prazo_meses=3,
            taxa_antecipacao="10.00",
            data_contrato=date(2026, 4, 3),
        )
        return associado, contrato

    def test_admin_lista_apenas_usuarios_internos(self):
        response = self.admin_client.get("/api/v1/configuracoes/usuarios/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        emails = [item["email"] for item in payload["results"]]

        self.assertIn(self.admin.email, emails)
        self.assertIn(self.agente.email, emails)
        self.assertIn(self.coordenador.email, emails)
        self.assertNotIn(self.associado.email, emails)
        self.assertEqual(payload["meta"]["total"], 6)
        self.assertEqual(payload["meta"]["admins"], 1)
        self.assertEqual(payload["meta"]["ativos"], 6)

    def test_agente_nao_pode_listar_gerenciamento_de_usuarios(self):
        response = self.agente_client.get("/api/v1/configuracoes/usuarios/")
        self.assertEqual(response.status_code, 403)

    def test_coordenador_lista_apenas_usuarios_operacionais(self):
        response = self.coord_client.get("/api/v1/configuracoes/usuarios/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        emails = [item["email"] for item in payload["results"]]

        self.assertIn(self.agente.email, emails)
        self.assertIn(self.analista.email, emails)
        self.assertIn(self.tesoureiro.email, emails)
        self.assertNotIn(self.admin.email, emails)
        self.assertNotIn(self.coordenador.email, emails)
        self.assertEqual(payload["meta"]["admins"], 0)
        self.assertEqual(
            sorted(role["codigo"] for role in payload["meta"]["available_roles"]),
            ["AGENTE", "ANALISTA", "TESOUREIRO"],
        )

    def test_admin_pode_atualizar_papeis_e_status_do_usuario(self):
        response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.analista.id}/",
            {
                "roles": ["ANALISTA", "TESOUREIRO"],
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.analista.refresh_from_db()
        self.assertFalse(self.analista.is_active)
        self.assertEqual(
            set(self.analista.roles.values_list("codigo", flat=True)),
            {"ANALISTA", "TESOUREIRO"},
        )

    def test_admin_nao_pode_remover_proprio_admin_ou_desativar_a_si_mesmo(self):
        remove_admin = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.admin.id}/",
            {"roles": ["AGENTE"]},
            format="json",
        )
        deactivate_self = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.admin.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(remove_admin.status_code, 400, remove_admin.json())
        self.assertEqual(deactivate_self.status_code, 400, deactivate_self.json())

    def test_admin_pode_criar_usuario_interno(self):
        response = self.admin_client.post(
            "/api/v1/configuracoes/usuarios/",
            {
                "email": "novo.admin@teste.local",
                "first_name": "Novo",
                "last_name": "Admin",
                "roles": ["COORDENADOR"],
                "password": "SenhaTemp@123",
                "password_confirm": "SenhaTemp@123",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        novo = User.objects.get(email="novo.admin@teste.local")
        self.assertTrue(novo.must_set_password)
        self.assertEqual(
            list(novo.roles.values_list("codigo", flat=True)),
            ["COORDENADOR"],
        )

    def test_coordenador_pode_criar_usuario_operacional(self):
        response = self.coord_client.post(
            "/api/v1/configuracoes/usuarios/",
            {
                "email": "novo.agente@teste.local",
                "first_name": "Novo",
                "last_name": "Agente",
                "roles": ["AGENTE"],
                "password": "SenhaTemp@123",
                "password_confirm": "SenhaTemp@123",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        novo = User.objects.get(email="novo.agente@teste.local")
        self.assertEqual(list(novo.roles.values_list("codigo", flat=True)), ["AGENTE"])
        self.assertTrue(novo.must_set_password)

    def test_coordenador_nao_pode_criar_admin_ou_coordenador(self):
        for roles in (["ADMIN"], ["COORDENADOR"]):
            response = self.coord_client.post(
                "/api/v1/configuracoes/usuarios/",
                {
                    "email": f"bloqueado-{roles[0].lower()}@teste.local",
                    "first_name": "Bloqueado",
                    "last_name": "Teste",
                    "roles": roles,
                    "password": "SenhaTemp@123",
                    "password_confirm": "SenhaTemp@123",
                    "is_active": True,
                },
                format="json",
            )

            self.assertEqual(response.status_code, 403, response.json())

    def test_coordenador_pode_atualizar_usuario_operacional(self):
        response = self.coord_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.analista.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.analista.refresh_from_db()
        self.assertFalse(self.analista.is_active)
        self.assertEqual(list(self.analista.roles.values_list("codigo", flat=True)), ["ANALISTA"])

    def test_coordenador_nao_pode_editar_admin_ou_a_si_mesmo(self):
        admin_response = self.coord_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.admin.id}/",
            {"roles": ["AGENTE"]},
            format="json",
        )
        self_response = self.coord_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.coordenador.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(admin_response.status_code, 403, admin_response.json())
        self.assertEqual(self_response.status_code, 403, self_response.json())

    def test_admin_pode_definir_nova_senha_diretamente(self):
        self.agente.must_set_password = True
        self.agente.save(update_fields=["must_set_password", "updated_at"])

        response = self.admin_client.post(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/resetar-senha/",
            {
                "password": "NovaSenha@123",
                "password_confirm": "NovaSenha@123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.agente.refresh_from_db()
        self.assertEqual(response.json()["detail"], "Senha atualizada com sucesso.")
        self.assertFalse(self.agente.must_set_password)
        self.assertTrue(self.agente.check_password("NovaSenha@123"))

    def test_coordenador_pode_resetar_senha_de_usuario_operacional(self):
        response = self.coord_client.post(
            f"/api/v1/configuracoes/usuarios/{self.analista.id}/resetar-senha/",
            {
                "password": "NovaSenha@123",
                "password_confirm": "NovaSenha@123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.analista.refresh_from_db()
        self.assertTrue(self.analista.check_password("NovaSenha@123"))

    def test_coordenador_nao_pode_resetar_senha_de_admin(self):
        response = self.coord_client.post(
            f"/api/v1/configuracoes/usuarios/{self.admin.id}/resetar-senha/",
            {
                "password": "NovaSenha@123",
                "password_confirm": "NovaSenha@123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.json())

    def test_admin_nao_pode_definir_senha_com_confirmacao_diferente(self):
        response = self.admin_client.post(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/resetar-senha/",
            {
                "password": "NovaSenha@123",
                "password_confirm": "OutraSenha@123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.agente.refresh_from_db()
        self.assertFalse(self.agente.check_password("NovaSenha@123"))

    def test_preview_retorna_associados_impactados_e_agentes_elegiveis(self):
        self._create_associado_com_contrato(
            suffix=101,
            agente=self.agente,
            matricula_servidor="143545-X",
        )
        self._create_associado_com_contrato(
            suffix=102,
            agente=self.agente,
            status=Associado.Status.INADIMPLENTE,
            matricula_servidor="998877-A",
        )

        response = self.admin_client.get(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/redistribuicao-agente/"
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["impacted_count"], 2)
        self.assertEqual(payload["source_user"]["id"], self.agente.id)
        self.assertIn("143545-X", [item["matricula_servidor"] for item in payload["impacted_associados"]])
        self.assertIn(
            self.outro_agente.id,
            [item["id"] for item in payload["eligible_agents"]],
        )

    def test_preview_retorna_vazio_quando_agente_nao_possui_carteira(self):
        response = self.admin_client.get(
            f"/api/v1/configuracoes/usuarios/{self.outro_agente.id}/redistribuicao-agente/"
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["impacted_count"], 0)
        self.assertEqual(payload["impacted_associados"], [])

    def test_patch_desativando_agente_com_carteira_exige_redistribuicao(self):
        self._create_associado_com_contrato(suffix=103, agente=self.agente)

        response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["AGENTE"],
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("agent_reassignment", response.json())

    def test_patch_removendo_papel_agente_com_carteira_exige_redistribuicao(self):
        self._create_associado_com_contrato(suffix=104, agente=self.agente)

        response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("agent_reassignment", response.json())

    def test_patch_com_redistribuicao_valida_move_associados_e_contratos(self):
        associado_1, contrato_1 = self._create_associado_com_contrato(
            suffix=105,
            agente=self.agente,
            matricula_servidor="111111-A",
        )
        associado_2, contrato_2 = self._create_associado_com_contrato(
            suffix=106,
            agente=self.agente,
            matricula_servidor="222222-B",
        )

        response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": False,
                "agent_reassignment": {"new_agent_id": self.outro_agente.id},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.agente.refresh_from_db()
        associado_1.refresh_from_db()
        associado_2.refresh_from_db()
        contrato_1.refresh_from_db()
        contrato_2.refresh_from_db()

        self.assertFalse(self.agente.is_active)
        self.assertEqual(list(self.agente.roles.values_list("codigo", flat=True)), ["ANALISTA"])
        self.assertEqual(associado_1.agente_responsavel_id, self.outro_agente.id)
        self.assertEqual(associado_2.agente_responsavel_id, self.outro_agente.id)
        self.assertEqual(contrato_1.agente_id, self.outro_agente.id)
        self.assertEqual(contrato_2.agente_id, self.outro_agente.id)

    def test_patch_nao_permite_destino_igual_ao_agente_origem(self):
        self._create_associado_com_contrato(suffix=107, agente=self.agente)

        response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": True,
                "agent_reassignment": {"new_agent_id": self.agente.id},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("agent_reassignment", response.json())

    def test_patch_nao_permite_destino_inativo_ou_sem_papel_agente(self):
        self._create_associado_com_contrato(suffix=108, agente=self.agente)
        self.outro_agente.is_active = False
        self.outro_agente.save(update_fields=["is_active", "updated_at"])

        inactive_response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": True,
                "agent_reassignment": {"new_agent_id": self.outro_agente.id},
            },
            format="json",
        )
        self.assertEqual(inactive_response.status_code, 400, inactive_response.json())
        self.assertIn("agent_reassignment", inactive_response.json())

        role_response = self.admin_client.patch(
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": True,
                "agent_reassignment": {"new_agent_id": self.analista.id},
            },
            format="json",
        )
        self.assertEqual(role_response.status_code, 400, role_response.json())
        self.assertIn("agent_reassignment", role_response.json())
