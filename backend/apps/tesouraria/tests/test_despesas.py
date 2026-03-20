from __future__ import annotations

import tempfile
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.financeiro.models import Despesa


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DespesaViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_tesoureiro = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.tesoureiro = cls._create_user(
            "tesouraria@abase.local",
            cls.role_tesoureiro,
            "Tesouraria",
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
        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

        self.agente_client = APIClient()
        self.agente_client.force_authenticate(self.agente)

    def _payload(self, **overrides):
        payload = {
            "categoria": "Operacional",
            "descricao": "Hospedagem principal",
            "valor": "199.90",
            "data_despesa": "2026-03-10",
            "status": Despesa.Status.PENDENTE,
            "tipo": Despesa.Tipo.FIXA,
            "recorrencia": Despesa.Recorrencia.MENSAL,
            "recorrencia_ativa": "true",
            "observacoes": "Despesa do sistema",
        }
        payload.update(overrides)
        return payload

    def test_cria_despesa_sem_anexo_com_status_anexo_pendente(self):
        response = self.tes_client.post(
            "/api/v1/tesouraria/despesas/",
            self._payload(),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        self.assertEqual(payload["status"], Despesa.Status.PENDENTE)
        self.assertEqual(payload["status_anexo"], Despesa.StatusAnexo.PENDENTE)
        self.assertIsNone(payload["anexo"])
        self.assertEqual(payload["lancado_por"]["id"], self.tesoureiro.id)

    def test_cria_despesa_com_anexo_define_status_anexo_anexado(self):
        response = self.tes_client.post(
            "/api/v1/tesouraria/despesas/",
            self._payload(
                anexo=SimpleUploadedFile(
                    "nota.pdf",
                    b"arquivo-nota",
                    content_type="application/pdf",
                )
            ),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())
        payload = response.json()

        self.assertEqual(payload["status_anexo"], Despesa.StatusAnexo.ANEXADO)
        self.assertEqual(payload["anexo"]["nome"], "nota.pdf")
        self.assertTrue(payload["anexo"]["arquivo_disponivel_localmente"])

    def test_exige_data_pagamento_quando_status_pago(self):
        response = self.tes_client.post(
            "/api/v1/tesouraria/despesas/",
            self._payload(status=Despesa.Status.PAGO),
            format="multipart",
        )
        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("data_pagamento", response.json())

    def test_limpa_data_pagamento_quando_status_pendente(self):
        response = self.tes_client.post(
            "/api/v1/tesouraria/despesas/",
            self._payload(
                status=Despesa.Status.PENDENTE,
                data_pagamento="2026-03-12",
            ),
            format="multipart",
        )
        self.assertEqual(response.status_code, 201, response.json())

        despesa = Despesa.objects.get()
        self.assertIsNone(despesa.data_pagamento)

    def test_anexa_arquivo_depois_do_cadastro(self):
        despesa = Despesa.objects.create(
            user=self.tesoureiro,
            categoria="Operacional",
            descricao="Internet",
            valor=Decimal("149.90"),
            data_despesa=date(2026, 3, 5),
            status=Despesa.Status.PENDENTE,
            status_anexo=Despesa.StatusAnexo.PENDENTE,
        )

        response = self.tes_client.post(
            f"/api/v1/tesouraria/despesas/{despesa.id}/anexar/",
            {
                "anexo": SimpleUploadedFile(
                    "internet.pdf",
                    b"comprovante-internet",
                    content_type="application/pdf",
                )
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

        despesa.refresh_from_db()
        self.assertEqual(despesa.status_anexo, Despesa.StatusAnexo.ANEXADO)
        self.assertEqual(despesa.nome_anexo, "internet.pdf")

    def test_lista_filtra_e_retorna_kpis(self):
        Despesa.objects.create(
            user=self.tesoureiro,
            categoria="Infra",
            descricao="Servidor",
            valor=Decimal("300.00"),
            data_despesa=date(2026, 3, 1),
            data_pagamento=date(2026, 3, 2),
            status=Despesa.Status.PAGO,
            tipo=Despesa.Tipo.FIXA,
            status_anexo=Despesa.StatusAnexo.ANEXADO,
        )
        Despesa.objects.create(
            user=self.tesoureiro,
            categoria="Operacional",
            descricao="Taxi",
            valor=Decimal("80.00"),
            data_despesa=date(2026, 3, 10),
            status=Despesa.Status.PENDENTE,
            tipo=Despesa.Tipo.VARIAVEL,
            status_anexo=Despesa.StatusAnexo.PENDENTE,
        )
        Despesa.objects.create(
            user=self.tesoureiro,
            categoria="Operacional",
            descricao="Almoço",
            valor=Decimal("50.00"),
            data_despesa=date(2026, 2, 10),
            status=Despesa.Status.PENDENTE,
            tipo=Despesa.Tipo.VARIAVEL,
            status_anexo=Despesa.StatusAnexo.PENDENTE,
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/despesas/",
            {
                "competencia": "2026-03",
                "search": "tax",
                "status_anexo": Despesa.StatusAnexo.PENDENTE,
                "page_size": 10,
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()

        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["descricao"], "Taxi")
        self.assertEqual(payload["kpis"]["total_despesas"], 1)
        self.assertEqual(payload["kpis"]["valor_total"], "80.00")
        self.assertEqual(payload["kpis"]["valor_pago"], "0.00")
        self.assertEqual(payload["kpis"]["valor_pendente"], "80.00")
        self.assertEqual(payload["kpis"]["pendentes_anexo"], 1)

    def test_delete_faz_soft_delete_e_remove_da_listagem(self):
        despesa = Despesa.objects.create(
            user=self.tesoureiro,
            categoria="Operacional",
            descricao="Soft delete",
            valor=Decimal("20.00"),
            data_despesa=date(2026, 3, 12),
            status=Despesa.Status.PENDENTE,
            status_anexo=Despesa.StatusAnexo.PENDENTE,
        )

        response = self.tes_client.delete(f"/api/v1/tesouraria/despesas/{despesa.id}/")
        self.assertEqual(response.status_code, 204)

        self.assertFalse(Despesa.objects.filter(pk=despesa.pk).exists())
        self.assertIsNotNone(Despesa.all_objects.get(pk=despesa.pk).deleted_at)

    def test_restringe_a_tesoureiro_ou_admin(self):
        response_agente = self.agente_client.get("/api/v1/tesouraria/despesas/")
        self.assertEqual(response_agente.status_code, 403)

        response_admin = self.admin_client.get("/api/v1/tesouraria/despesas/")
        self.assertEqual(response_admin.status_code, 200, response_admin.json())
