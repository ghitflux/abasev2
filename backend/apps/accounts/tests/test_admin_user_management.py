from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


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

    def test_admin_lista_apenas_usuarios_internos(self):
        response = self.admin_client.get("/api/v1/configuracoes/usuarios/")

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        emails = [item["email"] for item in payload["results"]]

        self.assertIn(self.admin.email, emails)
        self.assertIn(self.agente.email, emails)
        self.assertIn(self.coordenador.email, emails)
        self.assertNotIn(self.associado.email, emails)
        self.assertEqual(payload["meta"]["total"], 5)
        self.assertEqual(payload["meta"]["admins"], 1)
        self.assertEqual(payload["meta"]["ativos"], 5)

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
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA", "TESOUREIRO"],
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.agente.refresh_from_db()
        self.assertFalse(self.agente.is_active)
        self.assertEqual(
            set(self.agente.roles.values_list("codigo", flat=True)),
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
            f"/api/v1/configuracoes/usuarios/{self.agente.id}/",
            {
                "roles": ["ANALISTA"],
                "is_active": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.agente.refresh_from_db()
        self.assertFalse(self.agente.is_active)
        self.assertEqual(list(self.agente.roles.values_list("codigo", flat=True)), ["ANALISTA"])

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
