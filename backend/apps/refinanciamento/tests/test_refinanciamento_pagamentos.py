from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Item, Refinanciamento


class RefinanciamentoPagamentosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.coordenador = cls._create_user(
            "coord@abase.local", cls.role_coord, "Coord"
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

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

    def _create_contrato(self, cpf: str = "12345678901") -> Contrato:
        associado = Associado.objects.create(
            nome_completo="Associado Refinanciamento",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 12, 15),
            data_aprovacao=date(2025, 12, 20),
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 3, 15),
                ),
            ]
        )
        return contrato

    def _create_pagamento(
        self,
        contrato: Contrato,
        referencia: date,
        *,
        status_code: str = "1",
        manual_status: str | None = None,
    ) -> PagamentoMensalidade:
        return PagamentoMensalidade.objects.create(
            created_by=self.admin,
            import_uuid=f"uuid-{contrato.id}-{referencia.isoformat()}",
            referencia_month=referencia,
            status_code=status_code,
            matricula=contrato.associado.matricula_orgao or contrato.associado.matricula,
            orgao_pagto="SEFAZ",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=contrato.valor_mensalidade,
            manual_status=manual_status,
            source_file_path=f"retornos/{referencia.strftime('%Y-%m')}.txt",
        )

    def test_solicitar_usa_tres_pagamentos_nao_sequenciais_e_cria_linkagem_legado(self):
        contrato = self._create_contrato("22345678901")
        pagamentos = [
            self._create_pagamento(contrato, date(2026, 1, 1)),
            self._create_pagamento(contrato, date(2026, 2, 1)),
            self._create_pagamento(contrato, date(2026, 4, 1)),
        ]

        response = self.admin_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(response.status_code, 201, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(refinanciamento.mode, "admin_auto")
        self.assertEqual(refinanciamento.cycle_key, "2026-01|2026-02|2026-04")
        self.assertEqual(refinanciamento.ref1, date(2026, 1, 1))
        self.assertEqual(refinanciamento.ref2, date(2026, 2, 1))
        self.assertEqual(refinanciamento.ref3, date(2026, 4, 1))
        self.assertEqual(refinanciamento.competencia_solicitada, date(2026, 5, 1))
        self.assertEqual(refinanciamento.ciclo_destino.data_inicio, date(2026, 5, 1))
        self.assertEqual(refinanciamento.itens.count(), 3)
        self.assertEqual(
            list(
                refinanciamento.itens.order_by("referencia_month").values_list(
                    "pagamento_mensalidade_id", flat=True
                )
            ),
            [pagamento.id for pagamento in pagamentos],
        )
        self.assertEqual(
            refinanciamento.parcelas_json,
            [
                {
                    "pagamento_mensalidade_id": pagamentos[0].id,
                    "referencia_month": "2026-01-01",
                    "status_code": "1",
                    "valor": "500.00",
                    "import_uuid": pagamentos[0].import_uuid,
                    "source_file_path": pagamentos[0].source_file_path,
                },
                {
                    "pagamento_mensalidade_id": pagamentos[1].id,
                    "referencia_month": "2026-02-01",
                    "status_code": "1",
                    "valor": "500.00",
                    "import_uuid": pagamentos[1].import_uuid,
                    "source_file_path": pagamentos[1].source_file_path,
                },
                {
                    "pagamento_mensalidade_id": pagamentos[2].id,
                    "referencia_month": "2026-04-01",
                    "status_code": "1",
                    "valor": "500.00",
                    "import_uuid": pagamentos[2].import_uuid,
                    "source_file_path": pagamentos[2].source_file_path,
                },
            ],
        )
        self.assertEqual(Item.objects.count(), 3)
        self.assertEqual(
            PagamentoMensalidade.objects.filter(
                id__in=[pagamento.id for pagamento in pagamentos],
                agente_refi_solicitado=True,
            ).count(),
            3,
        )

    def test_solicitar_permite_competencia_futura_duplicada_no_mesmo_associado(self):
        contrato = self._create_contrato("22345678902")
        pagamentos = [
            self._create_pagamento(contrato, date(2026, 1, 1)),
            self._create_pagamento(contrato, date(2026, 2, 1)),
            self._create_pagamento(contrato, date(2026, 4, 1)),
        ]
        self.assertEqual(len(pagamentos), 3)

        contrato_conflitante = Contrato.objects.create(
            associado=contrato.associado,
            agente=self.agente,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 4, 15),
            data_aprovacao=date(2026, 4, 20),
            data_primeira_mensalidade=date(2026, 5, 1),
        )
        ciclo_conflitante = Ciclo.objects.create(
            contrato=contrato_conflitante,
            numero=1,
            data_inicio=date(2026, 5, 1),
            data_fim=date(2026, 7, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=1,
                    referencia_mes=date(2026, 5, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 5, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=2,
                    referencia_mes=date(2026, 6, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 6, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=3,
                    referencia_mes=date(2026, 7, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 7, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        response = self.admin_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(response.status_code, 201, response.json())
        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(refinanciamento.ciclo_destino.data_inicio, date(2026, 5, 1))
        self.assertEqual(
            Parcela.objects.filter(
                ciclo__contrato__associado=contrato.associado,
                referencia_mes=date(2026, 5, 1),
            ).count(),
            2,
        )
        contrato_conflitante.refresh_from_db()
        self.assertEqual(contrato_conflitante.status, Contrato.Status.ATIVO)

    def test_contrato_lista_exibe_aptidao_com_base_em_pagamentos_livres(self):
        contrato = self._create_contrato("32345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 4, 1))

        response = self.admin_client.get("/api/v1/contratos/")
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item for item in response.json()["results"] if item["id"] == contrato.id
        )
        self.assertEqual(row["mensalidades"]["pagas"], 3)
        self.assertEqual(row["mensalidades"]["total"], 3)
        self.assertTrue(row["mensalidades"]["apto_refinanciamento"])
        self.assertTrue(row["pode_solicitar_refinanciamento"])

    def test_pagamentos_consumidos_nao_sao_reutilizados_em_novo_refinanciamento(self):
        contrato = self._create_contrato("42345678901")
        referencias = [
            date(2026, 1, 1),
            date(2026, 2, 1),
            date(2026, 4, 1),
            date(2026, 5, 1),
            date(2026, 7, 1),
            date(2026, 8, 1),
        ]
        for referencia in referencias:
            self._create_pagamento(contrato, referencia)

        primeira = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(primeira.status_code, 201, primeira.json())
        refinanciamento_1 = Refinanciamento.objects.get(pk=primeira.json()["id"])
        bloqueio = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_1.id}/bloquear/",
            {"motivo": "Teste de novo ciclo"},
            format="json",
        )
        self.assertEqual(bloqueio.status_code, 200, bloqueio.json())

        segunda = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(segunda.status_code, 201, segunda.json())
        refinanciamento_2 = Refinanciamento.objects.get(pk=segunda.json()["id"])

        self.assertEqual(refinanciamento_1.cycle_key, "2026-01|2026-02|2026-04")
        self.assertEqual(refinanciamento_2.cycle_key, "2026-05|2026-07|2026-08")
        self.assertEqual(
            list(
                refinanciamento_1.itens.order_by("referencia_month").values_list(
                    "referencia_month", flat=True
                )
            ),
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 4, 1)],
        )
        self.assertEqual(
            list(
                refinanciamento_2.itens.order_by("referencia_month").values_list(
                    "referencia_month", flat=True
                )
            ),
            [date(2026, 5, 1), date(2026, 7, 1), date(2026, 8, 1)],
        )

    def test_nao_permite_solicitar_com_apenas_dois_pagamentos(self):
        contrato = self._create_contrato("52345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 4, 1))

        response = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("2/3 pagamentos elegíveis", " ".join(response.json()))
