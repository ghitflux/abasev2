from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import Pagamento


class RefinanciamentoPagamentosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")
        cls.role_analista = Role.objects.create(codigo="ANALISTA", nome="Analista")
        cls.role_tesoureiro = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")

        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.agente = cls._create_user("agente@abase.local", cls.role_agente, "Agente")
        cls.coordenador = cls._create_user(
            "coord@abase.local", cls.role_coord, "Coord"
        )
        cls.analista = cls._create_user(
            "analista@abase.local", cls.role_analista, "Analista"
        )
        cls.tesoureiro = cls._create_user(
            "tes@abase.local", cls.role_tesoureiro, "Tesoureiro"
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

        self.analyst_client = APIClient()
        self.analyst_client.force_authenticate(self.analista)

        self.tes_client = APIClient()
        self.tes_client.force_authenticate(self.tesoureiro)

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
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.admin,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=contrato.valor_liquido,
            contrato_margem_disponivel=Decimal("900.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=contrato.valor_liquido,
            paid_at=timezone.make_aware(
                datetime.combine(date(2025, 12, 20), datetime.min.time())
            ),
            forma_pagamento="pix",
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

    def test_solicitar_cria_fila_operacional_sem_ciclo_destino(self):
        contrato = self._create_contrato("22345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))

        response = self.admin_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(response.status_code, 201, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(refinanciamento.cycle_key, "2026-01|2026-02|2026-03")
        self.assertEqual(refinanciamento.ref1, date(2026, 1, 1))
        self.assertEqual(refinanciamento.ref2, date(2026, 2, 1))
        self.assertEqual(refinanciamento.ref3, date(2026, 3, 1))
        self.assertEqual(refinanciamento.competencia_solicitada, date(2026, 3, 1))
        self.assertEqual(refinanciamento.parcelas_ok, 2)
        self.assertEqual(refinanciamento.itens.count(), 2)
        self.assertEqual(
            list(
                refinanciamento.itens.order_by("referencia_month").values_list(
                    "referencia_month", flat=True
                )
            ),
            [date(2026, 1, 1), date(2026, 2, 1)],
        )
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertIsNone(refinanciamento.ciclo_destino)

    def test_contrato_lista_exibe_aptidao_no_status_renovacao(self):
        contrato = self._create_contrato("32345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))

        response = self.admin_client.get("/api/v1/contratos/")
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item for item in response.json()["results"] if item["id"] == contrato.id
        )
        self.assertEqual(row["mensalidades"]["pagas"], 2)
        self.assertEqual(row["mensalidades"]["total"], 3)
        self.assertTrue(row["mensalidades"]["apto_refinanciamento"])
        self.assertFalse(row["pode_solicitar_refinanciamento"])
        self.assertEqual(row["status_renovacao"], Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertIn("Parcelas quitadas no ciclo atual", row["mensalidades"]["descricao"])

    def test_nao_permite_solicitar_sem_atingir_o_limiar_do_ciclo(self):
        contrato = self._create_contrato("52345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))

        response = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("1/3 parcelas do ciclo atual foram quitadas", " ".join(response.json()))

    def test_fluxo_coord_analise_tesouraria_materializa_proximo_ciclo_so_na_efetivacao(self):
        contrato = self._create_contrato("62345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        request = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        approval = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/"
        )
        self.assertEqual(approval.status_code, 200, approval.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.EM_ANALISE_RENOVACAO)
        self.assertIsNone(refinanciamento.ciclo_destino)

        assumir = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.assertEqual(assumir.status_code, 200, assumir.json())

        aprovacao_analise = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {
                "termo_antecipacao": SimpleUploadedFile(
                    "termo.pdf",
                    b"arquivo termo",
                    content_type="application/pdf",
                ),
                "observacao": "Termo validado.",
            },
            format="multipart",
        )
        self.assertEqual(aprovacao_analise.status_code, 200, aprovacao_analise.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.APROVADO_PARA_RENOVACAO)
        self.assertIsNone(refinanciamento.ciclo_destino)

        efetivacao = self.tes_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado.pdf",
                    b"arquivo associado",
                    content_type="application/pdf",
                ),
                "comprovante_agente": SimpleUploadedFile(
                    "agente.pdf",
                    b"arquivo agente",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(efetivacao.status_code, 200, efetivacao.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.EFETIVADO)
        self.assertIsNotNone(refinanciamento.executado_em)
        self.assertIsNotNone(refinanciamento.ciclo_destino)
        self.assertEqual(refinanciamento.ciclo_destino.status, Ciclo.Status.ABERTO)
        self.assertEqual(
            refinanciamento.ciclo_destino.parcelas.filter(status=Parcela.Status.EM_ABERTO).count(),
            1,
        )

    def test_coordenacao_lista_retorna_motivo_apto_e_filtro_por_agente(self):
        contrato = self._create_contrato("72345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self.agent_client.post(f"/api/v1/refinanciamentos/{contrato.id}/solicitar/")

        response = self.coord_client.get(
            "/api/v1/coordenacao/refinanciamento/",
            {"agent": "Agente", "eligibility_band": "2_3"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["count"], 1)
        row = response.json()["results"][0]
        self.assertEqual(
            row["motivo_apto_renovacao"],
            "2/3 parcelas quitadas; última em previsão; ciclo 1 elegível",
        )

    def test_analise_lista_filtra_por_atribuicao(self):
        contrato = self._create_contrato("82345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        solicitar = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        refinanciamento_id = solicitar.json()["id"]
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")

        minhas = self.analyst_client.get(
            "/api/v1/analise/refinanciamentos/",
            {"assignment": "minhas"},
        )
        self.assertEqual(minhas.status_code, 200, minhas.json())
        self.assertEqual(minhas.json()["count"], 0)

        nao_assumidas = self.analyst_client.get(
            "/api/v1/analise/refinanciamentos/",
            {"assignment": "nao_assumidas"},
        )
        self.assertEqual(nao_assumidas.status_code, 200, nao_assumidas.json())
        self.assertEqual(nao_assumidas.json()["count"], 1)

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )

        minhas = self.analyst_client.get(
            "/api/v1/analise/refinanciamentos/",
            {"assignment": "minhas"},
        )
        self.assertEqual(minhas.status_code, 200, minhas.json())
        self.assertEqual(minhas.json()["count"], 1)

    def test_coordenacao_aprova_em_massa_com_confirmacao(self):
        primeiro = self._create_contrato("92345678901")
        segundo = self._create_contrato("93345678901")
        for contrato in [primeiro, segundo]:
            self._create_pagamento(contrato, date(2026, 1, 1))
            self._create_pagamento(contrato, date(2026, 2, 1))

        primeiro_id = self.agent_client.post(
            f"/api/v1/refinanciamentos/{primeiro.id}/solicitar/"
        ).json()["id"]
        segundo_id = self.agent_client.post(
            f"/api/v1/refinanciamentos/{segundo.id}/solicitar/"
        ).json()["id"]

        invalid = self.coord_client.post(
            "/api/v1/coordenacao/refinanciamento/aprovar_em_massa/",
            {"ids": [primeiro_id, segundo_id], "confirm_text": "ERRADO"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

        response = self.coord_client.post(
            "/api/v1/coordenacao/refinanciamento/aprovar_em_massa/",
            {"ids": [primeiro_id, segundo_id], "confirm_text": "CONFIRMAR"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["success_count"], 2)
        self.assertEqual(response.json()["failure_count"], 0)

        statuses = {
            refinanciamento.id: refinanciamento.status
            for refinanciamento in Refinanciamento.objects.filter(
                id__in=[primeiro_id, segundo_id]
            )
        }
        self.assertEqual(
            statuses,
            {
                primeiro_id: Refinanciamento.Status.EM_ANALISE_RENOVACAO,
                segundo_id: Refinanciamento.Status.EM_ANALISE_RENOVACAO,
            },
        )

    def test_refinanciamento_list_exibe_datas_de_solicitacao_e_ativacao(self):
        contrato = self._create_contrato("72345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        request = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/"
        )
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {
                "termo_antecipacao": SimpleUploadedFile(
                    "termo.pdf",
                    b"arquivo termo",
                    content_type="application/pdf",
                ),
                "observacao": "Termo ok",
            },
            format="multipart",
        )
        self.tes_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado.pdf",
                    b"arquivo associado",
                    content_type="application/pdf",
                ),
                "comprovante_agente": SimpleUploadedFile(
                    "agente.pdf",
                    b"arquivo agente",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )

        response = self.admin_client.get("/api/v1/refinanciamentos/")
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item for item in response.json()["results"] if item["id"] == refinanciamento_id
        )
        self.assertEqual(row["mensalidades_pagas"], 3)
        self.assertEqual(row["mensalidades_total"], 3)
        self.assertIsNotNone(row["data_solicitacao_renovacao"])
        self.assertIsNotNone(row["data_ativacao_ciclo"])
        self.assertFalse(row["ativacao_inferida"])

    def test_pagamento_manual_pago_conta_como_pagamento_livre(self):
        contrato = self._create_contrato("82345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1), status_code="2", manual_status="pago")
        self._create_pagamento(contrato, date(2026, 5, 1))

        response = self.admin_client.get("/api/v1/contratos/")
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item for item in response.json()["results"] if item["id"] == contrato.id
        )
        self.assertEqual(row["mensalidades"]["pagas"], 2)
        self.assertTrue(row["mensalidades"]["apto_refinanciamento"])
        self.assertFalse(row["pode_solicitar_refinanciamento"])
