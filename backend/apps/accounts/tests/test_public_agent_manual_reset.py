from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "agent-manual-reset-tests",
        }
    }
)
class PublicAgentManualResetViewTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")

        cls.agente = User.objects.create_user(
            email="agente@teste.local",
            password="SenhaAtual@2026",
            first_name="Agente",
            last_name="Teste",
            is_active=True,
            must_set_password=True,
        )
        cls.agente.roles.add(cls.role_agente)

        cls.admin = User.objects.create_user(
            email="admin@teste.local",
            password="SenhaAtual@2026",
            first_name="Admin",
            last_name="Teste",
            is_active=True,
            must_set_password=True,
        )
        cls.admin.roles.add(cls.role_admin)

        cls.agente_inativo = User.objects.create_user(
            email="agente-inativo@teste.local",
            password="SenhaAtual@2026",
            first_name="Agente",
            last_name="Inativo",
            is_active=False,
            must_set_password=True,
        )
        cls.agente_inativo.roles.add(cls.role_agente)

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def post_reset(self, **overrides):
        payload = {
            "email": "agente@teste.local",
            "password": "SenhaNova@2026",
            "password_confirmation": "SenhaNova@2026",
        }
        payload.update(overrides)
        return self.client.post(
            "/api/v1/auth/agent-manual-reset/",
            payload,
            format="json",
            HTTP_USER_AGENT="pytest-agent-manual-reset",
            REMOTE_ADDR="127.0.0.1",
        )

    def test_agent_ativo_pode_redefinir_senha_sem_token_externo(self):
        response = self.post_reset()

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(
            response.json()["message"],
            "Se o e-mail for elegível, a senha foi atualizada.",
        )

        self.agente.refresh_from_db()
        self.assertFalse(self.agente.must_set_password)
        self.assertTrue(self.agente.check_password("SenhaNova@2026"))

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {
                "email": "agente@teste.local",
                "password": "SenhaNova@2026",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200, login_response.json())

    def test_usuario_que_nao_e_agente_recebe_resposta_generica_sem_alterar_senha(self):
        response = self.post_reset(email="admin@teste.local")

        self.assertEqual(response.status_code, 200, response.json())
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.must_set_password)
        self.assertTrue(self.admin.check_password("SenhaAtual@2026"))
        self.assertFalse(self.admin.check_password("SenhaNova@2026"))

    def test_agente_inativo_recebe_resposta_generica_sem_alterar_senha(self):
        response = self.post_reset(email="agente-inativo@teste.local")

        self.assertEqual(response.status_code, 200, response.json())
        self.agente_inativo.refresh_from_db()
        self.assertTrue(self.agente_inativo.must_set_password)
        self.assertTrue(self.agente_inativo.check_password("SenhaAtual@2026"))

    def test_confirmacao_invalida_retorna_erro_de_validacao(self):
        response = self.post_reset(password_confirmation="OutraSenha@2026")

        self.assertEqual(response.status_code, 400, response.json())
        self.agente.refresh_from_db()
        self.assertTrue(self.agente.must_set_password)
        self.assertTrue(self.agente.check_password("SenhaAtual@2026"))

    def test_endpoint_publico_respeita_throttle(self):
        for index in range(3):
            response = self.post_reset(email=f"inexistente-{index}@teste.local")
            self.assertEqual(response.status_code, 200, response.json())

        throttled = self.post_reset(email="inexistente-4@teste.local")
        self.assertEqual(throttled.status_code, 429, throttled.json())
