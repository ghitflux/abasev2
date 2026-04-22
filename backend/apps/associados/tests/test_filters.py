from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela


class AssociadoFiltersTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.admin = cls._create_user("admin-filtros@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente-filtros@abase.local", cls.role_agente, "Agente")

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
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _create_associado_com_contrato(
        self,
        *,
        nome: str,
        cpf: str,
        mensalidade: Decimal,
        parcelas_pagas: int,
    ) -> Associado:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_mensalidade=mensalidade,
            status=Contrato.Status.ATIVO,
        )
        ciclo = contrato.ciclos.create(
            numero=1,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 1),
            status="aberto",
            valor_total=mensalidade * Decimal("3"),
        )
        for numero in range(1, max(parcelas_pagas, 1) + 1):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=numero,
                referencia_mes=date(2026, min(numero, 12), 1),
                valor=mensalidade,
                data_vencimento=date(2026, min(numero, 12), 5),
                status=(
                    Parcela.Status.DESCONTADO
                    if numero <= parcelas_pagas
                    else Parcela.Status.EM_PREVISAO
                ),
                data_pagamento=date(2026, min(numero, 12), 5) if numero <= parcelas_pagas else None,
            )
        return associado

    def test_listagem_filtra_por_faixa_mensalidade_com_multiplos_valores(self):
        alvo_medio = self._create_associado_com_contrato(
            nome="Associado Medio",
            cpf="10000000001",
            mensalidade=Decimal("250.00"),
            parcelas_pagas=1,
        )
        alvo_alto = self._create_associado_com_contrato(
            nome="Associado Alto",
            cpf="10000000002",
            mensalidade=Decimal("650.00"),
            parcelas_pagas=3,
        )
        self._create_associado_com_contrato(
            nome="Associado Fora da Faixa",
            cpf="10000000003",
            mensalidade=Decimal("120.00"),
            parcelas_pagas=1,
        )

        response = self.client.get(
            "/api/v1/associados/?faixa_mensalidade=200_300&faixa_mensalidade=acima_500"
        )
        self.assertEqual(response.status_code, 200, response.json())
        nomes = [item["nome_completo"] for item in response.json()["results"]]

        self.assertEqual(
            sorted(nomes),
            sorted([alvo_medio.nome_completo, alvo_alto.nome_completo]),
        )

    def test_listagem_filtra_por_faixa_de_parcelas_pagas(self):
        self._create_associado_com_contrato(
            nome="Associado Uma Parcela",
            cpf="10000000011",
            mensalidade=Decimal("250.00"),
            parcelas_pagas=1,
        )
        alvo = self._create_associado_com_contrato(
            nome="Associado Tres Parcelas",
            cpf="10000000012",
            mensalidade=Decimal("350.00"),
            parcelas_pagas=3,
        )

        response = self.client.get(
            "/api/v1/associados/?faixa_parcelas=3_parcelas_pagas"
        )
        self.assertEqual(response.status_code, 200, response.json())
        nomes = [item["nome_completo"] for item in response.json()["results"]]

        self.assertEqual(nomes, [alvo.nome_completo])
