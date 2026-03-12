from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado


class AssociadoContractScheduleTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente.schedule@teste.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Schedule",
            is_active=True,
        )
        cls.agente.roles.add(cls.role_agente)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.agente)

    def _payload(self):
        return {
            "tipo_documento": "CPF",
            "cpf_cnpj": "22345678901",
            "nome_completo": "Novo Associado Schedule",
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
                "email": "schedule@teste.local",
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
        }

    def test_create_calcula_primeira_mensalidade_e_mes_averbacao_apos_corte(self):
        response = self.client.post(
            "/api/v1/associados/",
            {
                **self._payload(),
                "cpf_cnpj": "32345678901",
                "contato": {
                    **self._payload()["contato"],
                    "email": "schedule-data@teste.local",
                },
                "data_aprovacao": "2026-03-11",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="32345678901")
        contrato = associado.contratos.get()
        ciclo = contrato.ciclos.get(numero=1)
        primeira_parcela = ciclo.parcelas.get(numero=1)
        ultima_parcela = ciclo.parcelas.get(numero=3)

        self.assertEqual(contrato.data_aprovacao, date(2026, 3, 11))
        self.assertEqual(contrato.data_primeira_mensalidade, date(2026, 5, 5))
        self.assertEqual(contrato.mes_averbacao, date(2026, 4, 1))
        self.assertEqual(contrato.doacao_associado, Decimal("450.00"))
        self.assertEqual(contrato.taxa_antecipacao, Decimal("30.00"))
        self.assertEqual(primeira_parcela.referencia_mes, date(2026, 5, 1))
        self.assertEqual(primeira_parcela.data_vencimento, date(2026, 5, 5))
        self.assertEqual(ultima_parcela.referencia_mes, date(2026, 7, 1))
        self.assertEqual(ultima_parcela.data_vencimento, date(2026, 7, 5))

    def test_create_considera_mes_atual_quando_aprovado_ate_dia_cinco(self):
        response = self.client.post(
            "/api/v1/associados/",
            {
                **self._payload(),
                "cpf_cnpj": "52345678901",
                "contato": {
                    **self._payload()["contato"],
                    "email": "schedule-dia-cinco@teste.local",
                },
                "data_aprovacao": "2026-03-05",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="52345678901")
        contrato = associado.contratos.get()
        primeira_parcela = contrato.ciclos.get(numero=1).parcelas.get(numero=1)

        self.assertEqual(contrato.data_aprovacao, date(2026, 3, 5))
        self.assertEqual(contrato.mes_averbacao, date(2026, 3, 1))
        self.assertEqual(contrato.data_primeira_mensalidade, date(2026, 4, 5))
        self.assertEqual(primeira_parcela.referencia_mes, date(2026, 4, 1))
        self.assertEqual(primeira_parcela.data_vencimento, date(2026, 4, 5))

    def test_create_sem_data_aprovacao_usa_data_atual(self):
        with patch("apps.associados.services.timezone.localdate", return_value=date(2026, 3, 11)):
            response = self.client.post(
                "/api/v1/associados/",
                {
                    **self._payload(),
                    "cpf_cnpj": "42345678901",
                    "contato": {
                        **self._payload()["contato"],
                        "email": "schedule-hoje@teste.local",
                    },
                },
                format="json",
            )

        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="42345678901")
        contrato = associado.contratos.get()

        self.assertEqual(contrato.data_aprovacao, date(2026, 3, 11))
        self.assertEqual(contrato.data_primeira_mensalidade, date(2026, 5, 5))
        self.assertEqual(contrato.mes_averbacao, date(2026, 4, 1))

    def test_create_calcula_disponivel_a_partir_da_mensalidade(self):
        payload = self._payload()
        payload.pop("margem_disponivel")

        response = self.client.post(
            "/api/v1/associados/",
            {
                **payload,
                "cpf_cnpj": "62345678901",
                "contato": {
                    **payload["contato"],
                    "email": "schedule-disponivel@teste.local",
                },
                "data_aprovacao": "2026-03-11",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())

        associado = Associado.objects.get(cpf_cnpj="62345678901")
        contrato = associado.contratos.get()

        self.assertEqual(contrato.valor_total_antecipacao, Decimal("1500.00"))
        self.assertEqual(contrato.margem_disponivel, Decimal("1050.00"))
        self.assertEqual(contrato.doacao_associado, Decimal("450.00"))
        self.assertEqual(contrato.taxa_antecipacao, Decimal("30.00"))
