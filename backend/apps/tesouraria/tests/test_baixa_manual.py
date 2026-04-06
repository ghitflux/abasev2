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
from apps.tesouraria.models import BaixaManual


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class BaixaManualViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_tesoureiro = Role.objects.create(
            codigo="TESOUREIRO",
            nome="Tesoureiro",
        )
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        cls.tesoureiro = User.objects.create_user(
            email="tesouraria.baixa@abase.local",
            password="Senha@123",
            first_name="Tesouraria",
            last_name="ABASE",
            is_active=True,
        )
        cls.tesoureiro.roles.add(cls.role_tesoureiro)

        cls.agente_a = User.objects.create_user(
            email="agente.a@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Alpha",
            is_active=True,
        )
        cls.agente_a.roles.add(cls.role_agente)

        cls.agente_b = User.objects.create_user(
            email="agente.b@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Beta",
            is_active=True,
        )
        cls.agente_b.roles.add(cls.role_agente)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.tesoureiro)

    def _create_associado(
        self,
        *,
        cpf: str,
        nome: str,
        matricula: str,
        agente: User,
    ) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula=matricula,
            matricula_orgao=matricula,
            status=Associado.Status.ATIVO,
            agente_responsavel=agente,
        )

    def _create_parcela(
        self,
        *,
        associado: Associado,
        agente: User,
        referencia: date,
        vencimento: date,
        status: str,
        valor: str = "200.00",
        codigo: str,
    ) -> Parcela:
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
            codigo=codigo,
            valor_bruto=Decimal("600.00"),
            valor_liquido=Decimal("600.00"),
            valor_mensalidade=Decimal(valor),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=referencia,
            data_aprovacao=referencia,
            data_primeira_mensalidade=referencia,
            mes_averbacao=referencia,
            auxilio_liberado_em=referencia,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=referencia,
            data_fim=referencia,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal(valor),
        )
        return Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=referencia,
            valor=Decimal(valor),
            data_vencimento=vencimento,
            status=status,
        )

    def test_lista_pendentes_filtra_por_agente_data_e_search(self):
        parcela_match = self._create_parcela(
            associado=self._create_associado(
                cpf="11111111111",
                nome="Marcianita Michele Ramos Mendes",
                matricula="MAT-111",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.NAO_DESCONTADO,
            codigo="CTR-TESTE-111",
        )
        self._create_parcela(
            associado=self._create_associado(
                cpf="22222222222",
                nome="Outro Associado",
                matricula="MAT-222",
                agente=self.agente_b,
            ),
            agente=self.agente_b,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 15),
            status=Parcela.Status.EM_ABERTO,
            codigo="CTR-TESTE-222",
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {
                "agente": str(self.agente_a.id),
                "data_inicio": "2026-03-01",
                "data_fim": "2026-03-31",
                "search": "11111111111",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["parcela_id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["cpf_cnpj"], "11111111111")
        self.assertEqual(payload["kpis"]["total_pendentes"], 1)
        self.assertEqual(payload["kpis"]["nao_descontado"], 1)

    def test_lista_quitados_filtra_por_agente_data_e_search(self):
        parcela_match = self._create_parcela(
            associado=self._create_associado(
                cpf="33333333333",
                nome="Associado Quitado",
                matricula="MAT-333",
                agente=self.agente_a,
            ),
            agente=self.agente_a,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 10),
            status=Parcela.Status.DESCONTADO,
            codigo="CTR-QUIT-333",
        )
        baixa_match = BaixaManual.objects.create(
            parcela=parcela_match,
            realizado_por=self.tesoureiro,
            comprovante=SimpleUploadedFile(
                "comprovante.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            nome_comprovante="comprovante.pdf",
            observacao="Quitado manualmente",
            valor_pago=Decimal("200.00"),
            data_baixa=date(2026, 4, 2),
        )

        parcela_outro = self._create_parcela(
            associado=self._create_associado(
                cpf="44444444444",
                nome="Associado Fora do Filtro",
                matricula="MAT-444",
                agente=self.agente_b,
            ),
            agente=self.agente_b,
            referencia=date(2026, 3, 1),
            vencimento=date(2026, 3, 11),
            status=Parcela.Status.DESCONTADO,
            codigo="CTR-QUIT-444",
        )
        BaixaManual.objects.create(
            parcela=parcela_outro,
            realizado_por=self.tesoureiro,
            comprovante=SimpleUploadedFile(
                "comprovante-2.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
            nome_comprovante="comprovante-2.pdf",
            observacao="Baixa fora do agente",
            valor_pago=Decimal("200.00"),
            data_baixa=date(2026, 4, 5),
        )

        response = self.client.get(
            "/api/v1/tesouraria/baixa-manual/",
            {
                "listing": "quitados",
                "agente": str(self.agente_a.id),
                "data_inicio": "2026-04-01",
                "data_fim": "2026-04-30",
                "search": "MAT-333",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["id"], baixa_match.id)
        self.assertEqual(payload["results"][0]["parcela_id"], parcela_match.id)
        self.assertEqual(payload["results"][0]["data_baixa"], "2026-04-02")
        self.assertEqual(payload["results"][0]["valor_pago"], "200.00")
        self.assertEqual(payload["results"][0]["realizado_por_nome"], "Tesouraria ABASE")
        self.assertEqual(payload["kpis"]["total_quitados"], 1)
        self.assertEqual(payload["kpis"]["valor_total_quitado"], "200.00")
