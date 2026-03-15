from __future__ import annotations

from datetime import datetime

import bcrypt
from django.test import TestCase, override_settings

from apps.accounts.legacy_agent_repair import LegacyAssociadoAgentRepairService
from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato


@override_settings(
    PASSWORD_HASHERS=[
        "django.contrib.auth.hashers.MD5PasswordHasher",
        "apps.accounts.hashers.LegacyLaravelBcryptPasswordHasher",
    ]
)
class LegacyAgentRepairServiceTestCase(TestCase):
    @staticmethod
    def _legacy_hash(password: str) -> str:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
        return hashed.replace("$2b$", "$2y$", 1)

    def setUp(self):
        self.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        self.default_agent = User.objects.create_user(
            email="agente@abase.com",
            password="Senha@123",
            first_name="Agente",
            last_name="Padrão",
        )
        self.default_agent.roles.add(self.role_agente)

    def test_repair_updates_associado_and_contract_using_earliest_legacy_cadastro(self):
        associado = Associado.objects.create(
            nome_completo="Associado Teste",
            cpf_cnpj="12345678900",
            agente_responsavel=self.default_agent,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.default_agent,
            codigo="CTR-001",
            valor_bruto=100,
            valor_liquido=70,
            valor_mensalidade=30,
            prazo_meses=3,
        )
        sem_fonte = Associado.objects.create(
            nome_completo="Sem Fonte",
            cpf_cnpj="99999999999",
            agente_responsavel=self.default_agent,
        )

        service = LegacyAssociadoAgentRepairService()
        result = service.repair(
            legacy_agents=[
                {
                    "legacy_user_id": 4,
                    "email": "agente@abase.com",
                    "name": "Agente Padrão",
                    "password": "",
                    "must_set_password": False,
                    "profile_photo_path": "",
                },
                {
                    "legacy_user_id": 282,
                    "email": "operacional.peltson@gmail.com",
                    "name": "TIAGO GOMES DA SILVA",
                    "password": self._legacy_hash("SenhaLegada@123"),
                    "must_set_password": False,
                    "profile_photo_path": "avatars/tiago.png",
                },
            ],
            legacy_cadastros=[
                {
                    "id": 20,
                    "cpf_cnpj": "12345678900",
                    "agente_responsavel": "Agente Padrão",
                    "agente_filial": "Agente Padrão",
                    "created_at": datetime(2025, 10, 2, 8, 30, 0),
                },
                {
                    "id": 10,
                    "cpf_cnpj": "123.456.789-00",
                    "agente_responsavel": "TIAGO GOMES DA SILVA",
                    "agente_filial": "TIAGO GOMES DA SILVA",
                    "created_at": datetime(2025, 10, 1, 8, 30, 0),
                },
            ],
        )

        associado.refresh_from_db()
        contrato.refresh_from_db()
        sem_fonte.refresh_from_db()
        tiago = User.objects.get(email="operacional.peltson@gmail.com")

        self.assertEqual(tiago.full_name, "TIAGO GOMES DA SILVA")
        self.assertTrue(tiago.password.startswith("legacy_bcrypt$"))
        self.assertEqual(list(tiago.roles.values_list("codigo", flat=True)), ["AGENTE"])

        self.assertEqual(associado.agente_responsavel_id, tiago.pk)
        self.assertEqual(associado.agente_filial, "TIAGO GOMES DA SILVA")
        self.assertEqual(contrato.agente_id, tiago.pk)
        self.assertEqual(sem_fonte.agente_responsavel_id, self.default_agent.pk)

        self.assertEqual(result.agent_users_created, 1)
        self.assertEqual(result.agent_users_updated, 1)
        self.assertEqual(result.agent_roles_added, 1)
        self.assertEqual(result.matched_associados, 1)
        self.assertEqual(result.associados_updated, 1)
        self.assertEqual(result.contratos_updated, 1)
        self.assertEqual(result.associados_without_legacy_source, 1)
        self.assertEqual(result.associados_with_unresolved_agent, 0)
