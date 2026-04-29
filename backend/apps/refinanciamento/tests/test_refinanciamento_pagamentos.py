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
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.refinanciamento.treasury_value_repair import (
    repair_treasury_refinanciamento_values,
)
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
        cls.outro_agente = cls._create_user(
            "outro-agente@abase.local", cls.role_agente, "Outro"
        )
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

    def _create_contrato(
        self,
        cpf: str = "12345678901",
        *,
        agente: User | None = None,
        admin_manual_layout_enabled: bool = False,
    ) -> Contrato:
        agente_responsavel = agente or self.agente
        associado = Associado.objects.create(
            nome_completo="Associado Refinanciamento",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=agente_responsavel,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente_responsavel,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            margem_disponivel=Decimal("900.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 12, 15),
            data_aprovacao=date(2025, 12, 20),
            data_primeira_mensalidade=date(2026, 1, 1),
            admin_manual_layout_enabled=admin_manual_layout_enabled,
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

    def _create_manual_cycle_quitado(self, contrato: Contrato) -> Ciclo:
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
                    associado=contrato.associado,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 1, 10),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 2, 10),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 3, 10),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 3, 15),
                ),
            ]
        )
        return ciclo

    def _termo_file(self, name: str = "termo.pdf") -> SimpleUploadedFile:
        return SimpleUploadedFile(name, b"arquivo termo", content_type="application/pdf")

    def _solicitar_refinanciamento(
        self,
        contrato: Contrato,
        *,
        client: APIClient | None = None,
    ):
        target_client = client or self.agent_client
        return target_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/",
            {"termo_antecipacao": self._termo_file()},
            format="multipart",
        )

    def test_solicitar_cria_fila_operacional_sem_ciclo_destino(self):
        contrato = self._create_contrato("22345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))

        response = self._solicitar_refinanciamento(contrato, client=self.admin_client)
        self.assertEqual(response.status_code, 201, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(refinanciamento.cycle_key, "2026-01|2026-02|2026-05")
        self.assertEqual(refinanciamento.ref1, date(2026, 1, 1))
        self.assertEqual(refinanciamento.ref2, date(2026, 2, 1))
        self.assertEqual(refinanciamento.ref3, date(2026, 5, 1))
        self.assertEqual(refinanciamento.competencia_solicitada, date(2026, 5, 1))
        self.assertEqual(refinanciamento.parcelas_ok, 3)
        self.assertEqual(refinanciamento.itens.count(), 3)
        self.assertEqual(
            list(
                refinanciamento.itens.order_by("referencia_month").values_list(
                    "referencia_month", flat=True
                )
            ),
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 5, 1)],
        )
        self.assertEqual(
            refinanciamento.status, Refinanciamento.Status.EM_ANALISE_RENOVACAO
        )
        self.assertIsNone(refinanciamento.ciclo_destino)
        self.assertEqual(
            refinanciamento.comprovantes.filter(
                papel=Comprovante.Papel.AGENTE,
                origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            ).count(),
            1,
        )

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
        self.assertGreaterEqual(row["mensalidades"]["pagas"], 2)
        self.assertEqual(row["mensalidades"]["total"], 3)
        self.assertTrue(row["mensalidades"]["apto_refinanciamento"])
        self.assertFalse(row["pode_solicitar_refinanciamento"])
        self.assertEqual(row["status_renovacao"], Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertEqual(row["valor_auxilio_liberado"], "0.00")
        self.assertEqual(row["percentual_repasse"], "10.00")
        self.assertEqual(row["ciclo_apto"]["numero"], 1)
        self.assertEqual(row["ciclo_apto"]["status"], Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertEqual(row["ciclo_apto"]["parcelas_pagas"], row["mensalidades"]["pagas"])
        self.assertEqual(row["ciclo_apto"]["parcelas_total"], 3)
        self.assertIn("parcelas quitadas no ciclo atual", row["mensalidades"]["descricao"].lower())

    def test_solicitar_reaproveita_refinanciamento_apto_materializado(self):
        contrato = self._create_contrato("32345678902")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 5, 1),
            status=Refinanciamento.Status.APTO_A_RENOVAR,
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2026-01|2026-02|2026-05",
        )

        response = self._solicitar_refinanciamento(contrato)
        self.assertEqual(response.status_code, 201, response.json())
        refinanciamento.refresh_from_db()
        self.assertEqual(refinanciamento.id, response.json()["id"])
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.EM_ANALISE_RENOVACAO,
        )

    def test_agente_pode_solicitar_liquidacao_partindo_dos_aptos(self):
        contrato = self._create_contrato("32345678903")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))

        response = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar-liquidacao/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
        )

        projection_row = self.agent_client.get(
            "/api/v1/contratos/",
            {"status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR},
        )
        self.assertEqual(projection_row.status_code, 200, projection_row.json())
        ids = {item["id"] for item in projection_row.json()["results"]}
        self.assertNotIn(contrato.id, ids)

        historico = self.agent_client.get(
            "/api/v1/refinanciamentos/",
            {"status": Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO},
        )
        self.assertEqual(historico.status_code, 200, historico.json())
        historico_ids = {item["id"] for item in historico.json()["results"]}
        self.assertIn(refinanciamento.id, historico_ids)

    def test_nao_permite_solicitar_sem_atingir_o_limiar_do_ciclo(self):
        contrato = self._create_contrato("52345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))

        response = self._solicitar_refinanciamento(contrato)
        self.assertEqual(response.status_code, 400)
        self.assertIn("1/3 parcelas do ciclo atual foram quitadas", " ".join(response.json()))

    def test_permita_solicitar_quando_ciclo_tem_liquidada_e_descontado(self):
        contrato = self._create_contrato(
            "52345678902",
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("1500.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=1,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 2, 10),
                    status=Parcela.Status.LIQUIDADA,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=2,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 3, 10),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 3, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=3,
                    referencia_mes=date(2026, 4, 1),
                    valor=Decimal("500.00"),
                    data_vencimento=date(2026, 4, 10),
                    status=Parcela.Status.EM_PREVISAO,
                ),
            ]
        )

        response = self._solicitar_refinanciamento(contrato)

        self.assertEqual(response.status_code, 201, response.json())

    def test_solicitar_exige_termo_de_antecipacao(self):
        contrato = self._create_contrato("53345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))

        response = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/",
            {},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("termo_antecipacao", response.json())

    def test_desativar_refinanciamento_orienta_para_liquidacao(self):
        contrato = self._create_contrato("54345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        refinanciamento_id = self._solicitar_refinanciamento(contrato).json()["id"]

        response = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/desativar/",
            {"motivo": "Não seguirá com a renovação."},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Use a liquidação do contrato", " ".join(response.json()))

    def test_fluxo_coord_analise_tesouraria_materializa_proximo_ciclo_so_na_efetivacao(self):
        contrato = self._create_contrato("62345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(
            refinanciamento.status, Refinanciamento.Status.EM_ANALISE_RENOVACAO
        )
        self.assertIsNone(refinanciamento.ciclo_destino)

        assumir = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.assertEqual(assumir.status_code, 200, assumir.json())

        aprovacao_analise = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {
                "observacao": "Termo validado.",
            },
            format="json",
        )
        self.assertEqual(aprovacao_analise.status_code, 200, aprovacao_analise.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
        )
        self.assertIsNone(refinanciamento.ciclo_destino)

        approval = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/"
        )
        self.assertEqual(approval.status_code, 200, approval.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(
            refinanciamento.status, Refinanciamento.Status.APROVADO_PARA_RENOVACAO
        )

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
        self.assertEqual(refinanciamento.ciclo_destino.parcelas.count(), 3)
        self.assertEqual(
            refinanciamento.ciclo_destino.parcelas.filter(
                status=Parcela.Status.EM_PREVISAO
            ).count(),
            3,
        )

    def test_tesouraria_efetiva_refinanciamento_sem_comprovante_do_agente(self):
        contrato = self._create_contrato("62345678941")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))
        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Termo ok"},
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")

        efetivacao = self.tes_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado.pdf",
                    b"arquivo associado",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(efetivacao.status_code, 400, efetivacao.json())
        self.assertEqual(
            efetivacao.json()["comprovante_agente"][0],
            "O comprovante do agente é obrigatório para efetivar a renovação.",
        )

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertNotEqual(refinanciamento.status, Refinanciamento.Status.EFETIVADO)
        tipos = {
            comprovante.tipo
            for comprovante in refinanciamento.comprovantes.filter(
                deleted_at__isnull=True
            )
        }
        self.assertNotIn(Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO, tipos)
        self.assertNotIn(Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE, tipos)

    def test_substituir_comprovante_nao_efetiva_refinanciamento(self):
        contrato = self._create_contrato("62345678942")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))
        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Termo ok"},
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")

        response = self.tes_client.post(
            f"/api/v1/tesouraria/refinanciamentos/{refinanciamento_id}/substituir-comprovante/",
            {
                "papel": Comprovante.Papel.ASSOCIADO,
                "arquivo": SimpleUploadedFile(
                    "associado.pdf",
                    b"arquivo associado",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
        )
        self.assertIsNone(refinanciamento.executado_em)

    def test_coordenacao_pode_substituir_termo_agente_na_tesouraria(self):
        contrato = self._create_contrato("62345678942")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))
        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Termo ok"},
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")

        response = self.coord_client.post(
            f"/api/v1/tesouraria/refinanciamentos/{refinanciamento_id}/substituir-termo-agente/",
            {
                "arquivo": SimpleUploadedFile(
                    "termo-ajustado.pdf",
                    b"novo termo",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        termos = refinanciamento.comprovantes.filter(
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            deleted_at__isnull=True,
        )
        termo = termos.order_by("-created_at", "-id").first()
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
        )
        self.assertEqual(termos.count(), 2)
        self.assertEqual(termo.nome_original, "termo-ajustado.pdf")
        self.assertEqual(termo.origem, Comprovante.Origem.TESOURARIA_RENOVACAO)
        self.assertEqual(termo.enviado_por, self.coordenador)
        self.assertEqual(refinanciamento.termo_antecipacao_original_name, "termo-ajustado.pdf")
        self.assertTrue(refinanciamento.termo_antecipacao_path.endswith("termo-ajustado.pdf"))
        self.assertIsNotNone(refinanciamento.termo_antecipacao_uploaded_at)
        self.assertFalse(
            refinanciamento.comprovantes.filter(
                tipo__in=[
                    Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                    Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
                ],
                deleted_at__isnull=True,
            ).exists()
        )

    def test_tesouraria_efetiva_refinanciamento_com_comprovantes_ja_anexados(self):
        contrato = self._create_contrato("62345678943")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))
        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Termo ok"},
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")

        for papel in [Comprovante.Papel.ASSOCIADO, Comprovante.Papel.AGENTE]:
            response = self.tes_client.post(
                f"/api/v1/tesouraria/refinanciamentos/{refinanciamento_id}/substituir-comprovante/",
                {
                    "papel": papel,
                    "arquivo": SimpleUploadedFile(
                        f"{papel}.pdf",
                        b"arquivo",
                        content_type="application/pdf",
                    ),
                },
                format="multipart",
            )
            self.assertEqual(response.status_code, 200, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
        )

        efetivacao = self.tes_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/efetivar/",
            {},
            format="json",
        )
        self.assertEqual(efetivacao.status_code, 200, efetivacao.json())

    def test_tesouraria_efetiva_renovacao_com_associado_inadimplente_retorna_para_ativo_e_gera_ciclo_destino(self):
        contrato = self._create_contrato("62345678942")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        request = self._solicitar_refinanciamento(contrato, client=self.admin_client)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento = Refinanciamento.objects.get(pk=request.json()["id"])
        refinanciamento.status = Refinanciamento.Status.APROVADO_PARA_RENOVACAO
        refinanciamento.save(update_fields=["status", "updated_at"])
        refinanciamento_id = refinanciamento.id
        contrato.associado.status = Associado.Status.INADIMPLENTE
        contrato.associado.save(update_fields=["status", "updated_at"])

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
        contrato.associado.refresh_from_db()
        self.assertEqual(contrato.associado.status, Associado.Status.ATIVO)
        self.assertIsNotNone(refinanciamento.ciclo_destino)
        self.assertEqual(refinanciamento.ciclo_destino.numero, 2)
        self.assertEqual(refinanciamento.ciclo_destino.status, Ciclo.Status.ABERTO)
        self.assertEqual(refinanciamento.ciclo_destino.parcelas.count(), 3)
        self.assertEqual(
            refinanciamento.ciclo_destino.parcelas.filter(status=Parcela.Status.EM_PREVISAO).count(),
            3,
        )

        refinanciamento.refresh_from_db()
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.EFETIVADO)
        self.assertIsNotNone(refinanciamento.executado_em)

    def test_coordenador_pode_remover_renovacao_da_fila_tesouraria(self):
        contrato = self._create_contrato("62345678944")
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 30),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            ciclo_origem=ciclo,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-04|2026-05|2026-06",
        )

        response = self.coord_client.post(
            f"/api/v1/tesouraria/refinanciamentos/{refinanciamento.id}/excluir/",
            {"motivo": "Linha operacional incorreta"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        refinanciamento.refresh_from_db()
        self.assertIsNotNone(refinanciamento.deleted_at)
        self.assertEqual(refinanciamento.observacao, "Linha operacional incorreta")

    def test_tesouraria_lista_filtra_por_ciclo_e_numero_ciclos(self):
        contrato_primeiro = self._create_contrato("62345678945")
        ciclo_primeiro = Ciclo.objects.create(
            contrato=contrato_primeiro,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 31),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1500.00"),
        )
        primeiro = Refinanciamento.objects.create(
            associado=contrato_primeiro.associado,
            contrato_origem=contrato_primeiro,
            ciclo_origem=ciclo_primeiro,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-01|2026-02|2026-03",
        )

        contrato_segundo = self._create_contrato("62345678946")
        ciclo_segundo = Ciclo.objects.create(
            contrato=contrato_segundo,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 30),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        segundo = Refinanciamento.objects.create(
            associado=contrato_segundo.associado,
            contrato_origem=contrato_segundo,
            ciclo_origem=ciclo_segundo,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 7, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-04|2026-05|2026-06",
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {
                "status": "aprovado_para_renovacao",
                "cycle_key": "2026-04",
                "numero_ciclos": "2",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertEqual(ids, [segundo.id])
        self.assertNotIn(primeiro.id, ids)

    def test_tesouraria_lista_filtra_por_multiplos_meses_do_ciclo(self):
        contrato_primeiro = self._create_contrato("62345678947")
        ciclo_primeiro = Ciclo.objects.create(
            contrato=contrato_primeiro,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 31),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1500.00"),
        )
        primeiro = Refinanciamento.objects.create(
            associado=contrato_primeiro.associado,
            contrato_origem=contrato_primeiro,
            ciclo_origem=ciclo_primeiro,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-01|2026-02|2026-03",
        )

        contrato_segundo = self._create_contrato("62345678948")
        ciclo_segundo = Ciclo.objects.create(
            contrato=contrato_segundo,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 30),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        segundo = Refinanciamento.objects.create(
            associado=contrato_segundo.associado,
            contrato_origem=contrato_segundo,
            ciclo_origem=ciclo_segundo,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 7, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-04|2026-05|2026-06",
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {
                "status": "aprovado_para_renovacao",
                "cycle_key": "2026-04,2026-06",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertEqual(ids, [segundo.id])
        self.assertNotIn(primeiro.id, ids)

    def test_tesouraria_pode_retornar_efetivado_para_pendente_pagamento(self):
        contrato = self._create_contrato("62345678949")
        ciclo_origem = self._create_manual_cycle_quitado(contrato)
        ciclo_destino = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 30),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            ciclo_origem=ciclo_origem,
            ciclo_destino=ciclo_destino,
            solicitado_por=self.agente,
            efetivado_por=self.tesoureiro,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            cycle_key="2026-01|2026-02|2026-03",
            executado_em=timezone.now(),
            data_ativacao_ciclo=timezone.now(),
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=ciclo_destino,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            arquivo=SimpleUploadedFile("assoc.pdf", b"assoc", content_type="application/pdf"),
            enviado_por=self.tesoureiro,
            data_pagamento=timezone.now(),
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=ciclo_destino,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            arquivo=SimpleUploadedFile("agente.pdf", b"agente", content_type="application/pdf"),
            enviado_por=self.tesoureiro,
            data_pagamento=timezone.now(),
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
        )
        pagamento = Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=self.tesoureiro,
            contrato_codigo=contrato.codigo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=contrato.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("900.00"),
            paid_at=timezone.now(),
            forma_pagamento="pix",
            referencias_externas={
                "payment_kind": "renovacao",
                "contrato_id": contrato.id,
                "refinanciamento_id": refinanciamento.id,
            },
        )

        response = self.tes_client.post(
            f"/api/v1/tesouraria/refinanciamentos/{refinanciamento.id}/retornar-pendente/"
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento.refresh_from_db()
        pagamento.refresh_from_db()
        self.assertEqual(refinanciamento.status, Refinanciamento.Status.APROVADO_PARA_RENOVACAO)
        self.assertIsNone(refinanciamento.executado_em)
        self.assertIsNone(refinanciamento.data_ativacao_ciclo)
        self.assertIsNone(refinanciamento.ciclo_destino_id)
        self.assertEqual(pagamento.status, Pagamento.Status.PENDENTE)
        self.assertIsNone(pagamento.paid_at)
        self.assertFalse(
            refinanciamento.comprovantes.filter(data_pagamento__isnull=False).exists()
        )

    def test_coordenacao_pode_limpar_linha_operacional_incorreta(self):
        contrato = self._create_contrato("62345678950")
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.DESATIVADO,
            cycle_key="2026-02|2026-03|2026-04",
        )

        response = self.coord_client.post(
            f"/api/v1/tesouraria/refinanciamentos/{refinanciamento.id}/limpar-linha/",
            {"motivo": "Linha incorreta na esteira"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento.refresh_from_db()
        self.assertIsNotNone(refinanciamento.deleted_at)
        self.assertFalse(
            Refinanciamento.objects.filter(pk=refinanciamento.id).exists()
        )

    def test_novo_ciclo_cria_nova_renovacao_sem_sobrescrever_historico_anterior(self):
        contrato = self._create_contrato("62345678951")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        primeiro_request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(primeiro_request.status_code, 201, primeiro_request.json())
        primeiro_id = primeiro_request.json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{primeiro_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{primeiro_id}/aprovar_analise/",
            {"observacao": "Primeiro ciclo validado."},
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{primeiro_id}/aprovar/")
        efetivacao = self.tes_client.post(
            f"/api/v1/refinanciamentos/{primeiro_id}/efetivar/",
            {
                "comprovante_associado": SimpleUploadedFile(
                    "associado-primeiro.pdf",
                    b"arquivo associado",
                    content_type="application/pdf",
                ),
                "comprovante_agente": SimpleUploadedFile(
                    "agente-primeiro.pdf",
                    b"arquivo agente",
                    content_type="application/pdf",
                ),
            },
            format="multipart",
        )
        self.assertEqual(efetivacao.status_code, 200, efetivacao.json())

        primeiro = Refinanciamento.objects.get(pk=primeiro_id)
        primeiro.status = Refinanciamento.Status.CONCLUIDO
        primeiro.save(update_fields=["status", "updated_at"])

        self._create_pagamento(contrato, date(2026, 4, 1))
        self._create_pagamento(contrato, date(2026, 5, 1))

        segundo_request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(segundo_request.status_code, 201, segundo_request.json())
        segundo_id = segundo_request.json()["id"]
        self.assertNotEqual(segundo_id, primeiro_id)

        primeiro.refresh_from_db()
        segundo = Refinanciamento.objects.get(pk=segundo_id)

        self.assertEqual(primeiro.status, Refinanciamento.Status.EFETIVADO)
        self.assertEqual(primeiro.cycle_key, "2026-01|2026-02|2026-03")
        self.assertEqual(segundo.status, Refinanciamento.Status.EM_ANALISE_RENOVACAO)
        self.assertEqual(segundo.cycle_key, "2026-04|2026-05|2026-06")
        self.assertEqual(
            Refinanciamento.objects.filter(
                contrato_origem=contrato,
                deleted_at__isnull=True,
            ).count(),
            2,
        )

    def test_coordenacao_lista_retorna_motivo_apto_e_filtro_por_agente(self):
        contrato = self._create_contrato("72345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        solicitar = self._solicitar_refinanciamento(contrato)
        refinanciamento_id = solicitar.json()["id"]
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Analise concluida"},
            format="json",
        )

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
        self.assertEqual(row["numero_ciclos"], 1)
        self.assertEqual(len(row["comprovantes"]), 1)
        self.assertEqual(row["comprovantes"][0]["tipo"], Comprovante.Tipo.TERMO_ANTECIPACAO)

    def test_coordenacao_pode_encaminhar_renovacao_para_liquidacao(self):
        contrato = self._create_contrato("73345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))

        solicitar = self._solicitar_refinanciamento(contrato)
        refinanciamento_id = solicitar.json()["id"]
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Analise concluida"},
            format="json",
        )

        response = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/encaminhar-liquidacao/",
            {"observacao": "Encaminhado para liquidacao"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
        )

    def test_fluxo_devolucao_de_termo_reaproveita_mesmo_refinanciamento(self):
        contrato = self._create_contrato("73345678902")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))

        solicitar = self._solicitar_refinanciamento(contrato)
        self.assertEqual(solicitar.status_code, 201, solicitar.json())
        refinanciamento_id = solicitar.json()["id"]

        assumir = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.assertEqual(assumir.status_code, 200, assumir.json())

        aprovacao_analise = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {"observacao": "Termo inicial aprovado."},
            format="json",
        )
        self.assertEqual(aprovacao_analise.status_code, 200, aprovacao_analise.json())

        devolucao_analise = self.coord_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/devolver-analise/",
            {"observacao": "Revisar assinatura do termo."},
            format="json",
        )
        self.assertEqual(devolucao_analise.status_code, 200, devolucao_analise.json())

        refinanciamento = Refinanciamento.objects.get(pk=refinanciamento_id)
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.PENDENTE_TERMO_ANALISTA,
        )
        self.assertEqual(refinanciamento.coordenador_note, "Revisar assinatura do termo.")

        devolucao_agente = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/devolver-agente/",
            {"observacao": "Assinatura ilegível, reenviar termo."},
            format="json",
        )
        self.assertEqual(devolucao_agente.status_code, 200, devolucao_agente.json())

        refinanciamento.refresh_from_db()
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.PENDENTE_TERMO_AGENTE,
        )
        self.assertEqual(
            refinanciamento.analista_note,
            "Assinatura ilegível, reenviar termo.",
        )

        reenvio = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar/",
            {"termo_antecipacao": self._termo_file("termo-reenviado.pdf")},
            format="multipart",
        )
        self.assertEqual(reenvio.status_code, 201, reenvio.json())
        self.assertEqual(reenvio.json()["id"], refinanciamento_id)

        refinanciamento.refresh_from_db()
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.EM_ANALISE_RENOVACAO,
        )
        self.assertEqual(
            refinanciamento.observacao,
            "Agente reenviou o termo de antecipação para nova análise.",
        )
        self.assertEqual(
            refinanciamento.comprovantes.filter(
                tipo=Comprovante.Tipo.TERMO_ANTECIPACAO
            ).count(),
            2,
        )
        self.assertEqual(refinanciamento.coordenador_note, "Revisar assinatura do termo.")

        fila_coord = self.coord_client.get("/api/v1/coordenacao/refinanciamento/")
        self.assertEqual(fila_coord.status_code, 200, fila_coord.json())
        self.assertEqual(fila_coord.json()["count"], 0)

        fila_liquidacao = self.coord_client.get(
            "/api/v1/coordenacao/refinanciados/",
            {"status": "solicitado_para_liquidacao"},
        )
        self.assertEqual(fila_liquidacao.status_code, 200, fila_liquidacao.json())
        self.assertEqual(fila_liquidacao.json()["count"], 0)

    def test_analise_lista_filtra_por_atribuicao(self):
        contrato = self._create_contrato("82345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        solicitar = self._solicitar_refinanciamento(contrato)
        refinanciamento_id = solicitar.json()["id"]

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

        assumidas = self.analyst_client.get(
            "/api/v1/analise/refinanciamentos/",
            {"assignment": "assumidas"},
        )
        self.assertEqual(assumidas.status_code, 200, assumidas.json())
        self.assertEqual(assumidas.json()["count"], 1)

    def test_analise_resumo_refinanciamentos_retorna_cards_operacionais(self):
        contrato_liberado = self._create_contrato("83345678901")
        contrato_assumido = self._create_contrato("84345678901")
        contrato_aprovado = self._create_contrato("85345678901")
        for contrato in [contrato_liberado, contrato_assumido, contrato_aprovado]:
            self._create_pagamento(contrato, date(2026, 1, 1))
            self._create_pagamento(contrato, date(2026, 2, 1))

        liberado_id = self._solicitar_refinanciamento(contrato_liberado).json()["id"]
        assumido_id = self._solicitar_refinanciamento(contrato_assumido).json()["id"]
        aprovado_id = self._solicitar_refinanciamento(contrato_aprovado).json()["id"]

        assumir = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{assumido_id}/assumir_analise/"
        )
        self.assertEqual(assumir.status_code, 200, assumir.json())

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{aprovado_id}/assumir_analise/"
        )
        aprovar = self.analyst_client.post(
            f"/api/v1/refinanciamentos/{aprovado_id}/aprovar_analise/",
            {
                "observacao": "Termo ok",
            },
            format="json",
        )
        self.assertEqual(aprovar.status_code, 200, aprovar.json())

        response = self.analyst_client.get("/api/v1/analise/refinanciamentos/resumo/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["total"], 3)
        self.assertEqual(response.json()["em_analise"], 2)
        self.assertEqual(response.json()["assumidos"], 1)
        self.assertEqual(response.json()["aprovados"], 1)

        filtered = self.analyst_client.get(
            "/api/v1/analise/refinanciamentos/resumo/",
            {"assignment": "assumidas"},
        )
        self.assertEqual(filtered.status_code, 200, filtered.json())
        self.assertEqual(filtered.json()["total"], 1)
        self.assertEqual(filtered.json()["em_analise"], 1)
        self.assertEqual(filtered.json()["assumidos"], 1)
        self.assertEqual(filtered.json()["aprovados"], 0)

    def test_coordenacao_aprova_em_massa_com_confirmacao(self):
        primeiro = self._create_contrato("92345678901")
        segundo = self._create_contrato("93345678901")
        for contrato in [primeiro, segundo]:
            self._create_pagamento(contrato, date(2026, 1, 1))
            self._create_pagamento(contrato, date(2026, 2, 1))

        primeiro_id = self._solicitar_refinanciamento(primeiro).json()["id"]
        segundo_id = self._solicitar_refinanciamento(segundo).json()["id"]

        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{primeiro_id}/aprovar_analise/",
            {"observacao": "Primeiro liberado"},
            format="json",
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{segundo_id}/aprovar_analise/",
            {"observacao": "Segundo liberado"},
            format="json",
        )

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
                primeiro_id: Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                segundo_id: Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            },
        )

    def test_refinanciamento_list_exibe_datas_de_solicitacao_e_ativacao(self):
        contrato = self._create_contrato("72345678901")
        self._create_pagamento(contrato, date(2026, 1, 1))
        self._create_pagamento(contrato, date(2026, 2, 1))
        self._create_pagamento(contrato, date(2026, 3, 1))

        request = self._solicitar_refinanciamento(contrato)
        self.assertEqual(request.status_code, 201, request.json())
        refinanciamento_id = request.json()["id"]
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/assumir_analise/"
        )
        self.analyst_client.post(
            f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar_analise/",
            {
                "observacao": "Termo ok",
            },
            format="json",
        )
        self.coord_client.post(f"/api/v1/refinanciamentos/{refinanciamento_id}/aprovar/")
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

    def test_tesouraria_lista_apenas_aprovados_para_renovacao_por_updated_at(self):
        contrato_primeiro = self._create_contrato("72345678911")
        primeiro = Refinanciamento.objects.create(
            associado=contrato_primeiro.associado,
            contrato_origem=contrato_primeiro,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-02|2026-03|2026-04",
        )
        Refinanciamento.objects.filter(pk=primeiro.pk).update(
            created_at=timezone.make_aware(datetime(2026, 1, 12, 9, 0)),
            updated_at=timezone.make_aware(datetime(2026, 4, 10, 10, 0)),
        )

        contrato_segundo = self._create_contrato("72345678912")
        segundo = Refinanciamento.objects.create(
            associado=contrato_segundo.associado,
            contrato_origem=contrato_segundo,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 5, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-03|2026-04|2026-05",
        )
        Refinanciamento.objects.filter(pk=segundo.pk).update(
            created_at=timezone.make_aware(datetime(2026, 2, 5, 11, 0)),
            updated_at=timezone.make_aware(datetime(2026, 4, 18, 8, 30)),
        )

        contrato_fora_recorte = self._create_contrato("72345678913")
        fora_recorte = Refinanciamento.objects.create(
            associado=contrato_fora_recorte.associado,
            contrato_origem=contrato_fora_recorte,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-01|2026-02|2026-04",
        )
        Refinanciamento.objects.filter(pk=fora_recorte.pk).update(
            created_at=timezone.make_aware(datetime(2026, 4, 12, 9, 0)),
            updated_at=timezone.make_aware(datetime(2026, 3, 28, 15, 0)),
        )

        contrato_efetivado = self._create_contrato("72345678914")
        efetivado = Refinanciamento.objects.create(
            associado=contrato_efetivado.associado,
            contrato_origem=contrato_efetivado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            cycle_key="2026-02|2026-03|2026-04",
        )
        Refinanciamento.objects.filter(pk=efetivado.pk).update(
            updated_at=timezone.make_aware(datetime(2026, 4, 20, 9, 0)),
            executado_em=timezone.make_aware(datetime(2026, 4, 20, 9, 0)),
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {
                "status": "aprovado_para_renovacao",
                "data_inicio": "2026-04-01",
                "data_fim": "2026-04-30",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertEqual(ids, [segundo.id, primeiro.id])
        self.assertNotIn(fora_recorte.id, ids)
        self.assertNotIn(efetivado.id, ids)

    def test_tesouraria_lista_exibe_valor_liberado_do_associado(self):
        contrato = self._create_contrato("72345678921")
        contrato.margem_disponivel = Decimal("735.00")
        contrato.save(update_fields=["margem_disponivel", "updated_at"])

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            valor_refinanciamento=Decimal("1881.03"),
            repasse_agente=Decimal("73.50"),
            cycle_key="2026-02|2026-03|2026-04",
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=None,
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.AGENTE,
            origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            arquivo=self._termo_file("termo-justino.pdf"),
            nome_original="ANTECIPACAO - JUSTINO.pdf",
            enviado_por=self.agente,
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "aprovado_para_renovacao"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            item
            for item in response.json()["results"]
            if item["id"] == refinanciamento.id
        )
        self.assertEqual(row["valor_refinanciamento"], "1881.03")
        self.assertEqual(row["valor_liberado_associado"], "735.00")
        self.assertEqual(row["repasse_agente"], "73.50")
        self.assertIn(
            Comprovante.Tipo.TERMO_ANTECIPACAO,
            [item["tipo"] for item in row["comprovantes"]],
        )

    def test_tesouraria_ignora_efetivado_fantasma_sem_materializacao(self):
        contrato_real = self._create_contrato("72345678931")
        real = Refinanciamento.objects.create(
            associado=contrato_real.associado,
            contrato_origem=contrato_real,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("900.00"),
            repasse_agente=Decimal("90.00"),
            cycle_key="2026-02|2026-03|2026-04",
            executado_em=timezone.make_aware(datetime(2026, 4, 20, 9, 0)),
            data_ativacao_ciclo=timezone.make_aware(datetime(2026, 4, 20, 9, 0)),
        )
        ghost_contract = self._create_contrato("72345678932")
        ghost = Refinanciamento.objects.create(
            associado=ghost_contract.associado,
            contrato_origem=ghost_contract,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("945.00"),
            repasse_agente=Decimal("94.50"),
            cycle_key="2026-03|2026-04",
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "efetivado"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(real.id, ids)
        self.assertNotIn(ghost.id, ids)

        resumo = self.tes_client.get("/api/v1/tesouraria/refinanciamentos/resumo/")
        self.assertEqual(resumo.status_code, 200, resumo.json())
        self.assertEqual(resumo.json()["efetivados"], 1)

    def test_tesouraria_lista_efetivados_inclui_materializacao_por_comprovantes(self):
        contrato = self._create_contrato("72345678933")
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            valor_refinanciamento=Decimal("945.00"),
            repasse_agente=Decimal("94.50"),
            cycle_key="2026-02|2026-03|2026-04",
        )
        paid_at = timezone.make_aware(datetime(2026, 4, 20, 9, 0))
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=None,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
            arquivo=self._termo_file("assoc.pdf"),
            nome_original="assoc.pdf",
            enviado_por=self.admin,
            data_pagamento=paid_at,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=None,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
            arquivo=self._termo_file("agente.pdf"),
            nome_original="agente.pdf",
            enviado_por=self.admin,
            data_pagamento=paid_at,
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "efetivado"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(refinanciamento.id, ids)

        resumo = self.tes_client.get("/api/v1/tesouraria/refinanciamentos/resumo/")
        self.assertEqual(resumo.status_code, 200, resumo.json())
        self.assertEqual(resumo.json()["efetivados"], 1)

    def test_tesouraria_filtra_efetivados_pelo_ano_operacional(self):
        contrato = self._create_contrato("72345678934")
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2025, 12, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("945.00"),
            repasse_agente=Decimal("94.50"),
            cycle_key="2025-10|2025-11|2025-12",
            executado_em=timezone.make_aware(datetime(2026, 1, 5, 9, 0)),
            data_ativacao_ciclo=timezone.make_aware(datetime(2026, 1, 5, 9, 0)),
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "efetivado", "year": "2026"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(refinanciamento.id, ids)

    def test_tesouraria_lista_faz_fallback_do_repasse_quando_refinanciamento_zerado(self):
        contrato = self._create_contrato("72345678922")
        contrato.margem_disponivel = Decimal("630.00")
        contrato.comissao_agente = Decimal("63.00")
        contrato.save(
            update_fields=["margem_disponivel", "comissao_agente", "updated_at"]
        )

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("0.00"),
            repasse_agente=Decimal("0.00"),
            cycle_key="2026-02|2026-03|2026-04",
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "efetivado"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            item
            for item in response.json()["results"]
            if item["id"] == refinanciamento.id
        )
        self.assertEqual(row["valor_liberado_associado"], "630.00")
        self.assertEqual(row["repasse_agente"], "63.00")

    def test_tesouraria_lista_resolve_contrato_por_associado_quando_legado_esta_sem_vinculo(self):
        contrato = self._create_contrato("72345678923")
        contrato.margem_disponivel = Decimal("630.00")
        contrato.comissao_agente = Decimal("63.00")
        contrato.save(
            update_fields=["margem_disponivel", "comissao_agente", "updated_at"]
        )

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("0.00"),
            repasse_agente=Decimal("0.00"),
            cycle_key="2025-10|2025-11|2025-12",
            contrato_codigo_origem="",
        )

        response = self.tes_client.get(
            "/api/v1/tesouraria/refinanciamentos/",
            {"status": "efetivado"},
        )
        self.assertEqual(response.status_code, 200, response.json())

        row = next(
            item
            for item in response.json()["results"]
            if item["id"] == refinanciamento.id
        )
        self.assertEqual(row["valor_liberado_associado"], "630.00")
        self.assertEqual(row["repasse_agente"], "63.00")

    def test_repair_tesouraria_refinanciamento_religa_contrato_por_associado(self):
        contrato = self._create_contrato("72345678924")
        contrato.margem_disponivel = Decimal("525.00")
        contrato.comissao_agente = Decimal("52.50")
        contrato.save(
            update_fields=["margem_disponivel", "comissao_agente", "updated_at"]
        )

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            valor_refinanciamento=Decimal("0.00"),
            repasse_agente=Decimal("0.00"),
            cycle_key="2025-10|2025-11|2025-12",
            contrato_codigo_origem="",
        )

        report = repair_treasury_refinanciamento_values(apply=True)
        refinanciamento.refresh_from_db()

        self.assertGreaterEqual(report["updated_rows"], 1)
        self.assertEqual(refinanciamento.contrato_origem_id, contrato.id)
        self.assertEqual(refinanciamento.contrato_codigo_origem, contrato.codigo)
        self.assertEqual(refinanciamento.valor_refinanciamento, Decimal("525.00"))
        self.assertEqual(refinanciamento.repasse_agente, Decimal("52.50"))

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

    def test_agente_resumo_refinanciamentos_respeita_filtros(self):
        contrato_finalizado = self._create_contrato("84345678901")
        contrato_bloqueado = self._create_contrato("85345678901")
        contrato_revertido = self._create_contrato("86345678901")
        contrato_em_fluxo = self._create_contrato("87345678901")
        contrato_outro_agente = self._create_contrato(
            "88345678901", agente=self.outro_agente
        )

        Refinanciamento.objects.create(
            associado=contrato_finalizado.associado,
            contrato_origem=contrato_finalizado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.EFETIVADO,
            cycle_key="2026-01|2026-02|2026-03",
        )
        Refinanciamento.objects.create(
            associado=contrato_bloqueado.associado,
            contrato_origem=contrato_bloqueado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.BLOQUEADO,
            cycle_key="2026-02|2026-03|2026-04",
        )
        Refinanciamento.objects.create(
            associado=contrato_revertido.associado,
            contrato_origem=contrato_revertido,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 5, 1),
            status=Refinanciamento.Status.REVERTIDO,
            cycle_key="2026-03|2026-04|2026-05",
        )
        Refinanciamento.objects.create(
            associado=contrato_em_fluxo.associado,
            contrato_origem=contrato_em_fluxo,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 6, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            cycle_key="2026-04|2026-05|2026-06",
        )
        Refinanciamento.objects.create(
            associado=contrato_outro_agente.associado,
            contrato_origem=contrato_outro_agente,
            solicitado_por=self.outro_agente,
            competencia_solicitada=date(2026, 7, 1),
            status=Refinanciamento.Status.EFETIVADO,
            cycle_key="2026-05|2026-06|2026-07",
        )

        response = self.agent_client.get("/api/v1/refinanciamentos/resumo/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["total"], 4)
        self.assertEqual(response.json()["concluidos"], 1)
        self.assertEqual(response.json()["bloqueados"], 1)
        self.assertEqual(response.json()["revertidos"], 1)
        self.assertEqual(response.json()["em_fluxo"], 1)

        filtered = self.agent_client.get(
            "/api/v1/refinanciamentos/resumo/",
            {"cycle_key": "2026-04", "search": "85345678901"},
        )
        self.assertEqual(filtered.status_code, 200, filtered.json())
        self.assertEqual(filtered.json()["total"], 1)
        self.assertEqual(filtered.json()["bloqueados"], 1)
        self.assertEqual(filtered.json()["concluidos"], 0)

    def test_lista_refinanciamentos_do_agente_retorna_matricula_e_so_anexo_do_agente(self):
        contrato = self._create_contrato("89345678901")
        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 8, 1),
            status=Refinanciamento.Status.EFETIVADO,
            cycle_key="2026-06|2026-07|2026-08",
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            papel=Comprovante.Papel.ASSOCIADO,
            arquivo=SimpleUploadedFile(
                "associado.pdf",
                b"arquivo associado",
                content_type="application/pdf",
            ),
            enviado_por=self.admin,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            arquivo=SimpleUploadedFile(
                "agente.pdf",
                b"arquivo agente",
                content_type="application/pdf",
            ),
            enviado_por=self.agente,
        )

        response = self.agent_client.get(
            "/api/v1/refinanciamentos/",
            {"status": "efetivado"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item
            for item in response.json()["results"]
            if item["id"] == refinanciamento.id
        )
        self.assertEqual(row["matricula"], contrato.associado.matricula)
        self.assertEqual(row["matricula_display"], contrato.associado.matricula_display)
        self.assertEqual(len(row["comprovantes"]), 1)
        self.assertEqual(row["comprovantes"][0]["papel"], Comprovante.Papel.AGENTE)

    def test_contratos_podem_ser_filtrados_por_status_renovacao_apto(self):
        contrato_apto = self._create_contrato("90345678901")
        self._create_pagamento(contrato_apto, date(2026, 1, 1))
        self._create_pagamento(contrato_apto, date(2026, 2, 1))
        self._create_pagamento(contrato_apto, date(2026, 5, 1))

        contrato_sem_apto = self._create_contrato("91345678901")
        self._create_pagamento(contrato_sem_apto, date(2026, 1, 1))

        response = self.agent_client.get(
            "/api/v1/contratos/",
            {"status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR},
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(contrato_apto.id, ids)
        self.assertNotIn(contrato_sem_apto.id, ids)

    def test_admin_coordenador_e_analista_veem_todos_os_aptos(self):
        contrato_agente = self._create_contrato("90345678911", agente=self.agente)
        self._create_pagamento(contrato_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_agente, date(2026, 5, 1))

        contrato_outro_agente = self._create_contrato(
            "90345678912",
            agente=self.outro_agente,
        )
        self._create_pagamento(contrato_outro_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 5, 1))

        expected_ids = {contrato_agente.id, contrato_outro_agente.id}
        for client in (self.admin_client, self.coord_client, self.analyst_client):
            response = client.get(
                "/api/v1/contratos/",
                {"status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR},
            )
            self.assertEqual(response.status_code, 200, response.json())
            ids = {item["id"] for item in response.json()["results"]}
            self.assertTrue(expected_ids.issubset(ids))

    def test_agente_continua_vendo_apenas_os_proprios_aptos_mesmo_com_filtro_de_agente(self):
        contrato_agente = self._create_contrato("90345678921", agente=self.agente)
        self._create_pagamento(contrato_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_agente, date(2026, 5, 1))

        contrato_outro_agente = self._create_contrato(
            "90345678922",
            agente=self.outro_agente,
        )
        self._create_pagamento(contrato_outro_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 5, 1))

        response = self.agent_client.get(
            "/api/v1/contratos/",
            {
                "status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR,
                "agente": str(self.outro_agente.id),
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        ids = {item["id"] for item in response.json()["results"]}
        self.assertIn(contrato_agente.id, ids)
        self.assertNotIn(contrato_outro_agente.id, ids)

    def test_coordenador_e_analista_podem_filtrar_aptos_por_agente(self):
        contrato_agente = self._create_contrato("90345678931", agente=self.agente)
        self._create_pagamento(contrato_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_agente, date(2026, 5, 1))

        contrato_outro_agente = self._create_contrato(
            "90345678932",
            agente=self.outro_agente,
        )
        self._create_pagamento(contrato_outro_agente, date(2026, 1, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 2, 1))
        self._create_pagamento(contrato_outro_agente, date(2026, 5, 1))

        for client in (self.coord_client, self.analyst_client):
            response = client.get(
                "/api/v1/contratos/",
                {
                    "status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR,
                    "agente": str(self.outro_agente.id),
                },
            )
            self.assertEqual(response.status_code, 200, response.json())
            ids = {item["id"] for item in response.json()["results"]}
            self.assertIn(contrato_outro_agente.id, ids)
            self.assertNotIn(contrato_agente.id, ids)

    def test_coordenador_e_analista_podem_solicitar_renovacao_pela_tab_de_aptos(self):
        for cpf, client in (
            ("90345678941", self.coord_client),
            ("90345678942", self.analyst_client),
        ):
            contrato = self._create_contrato(cpf)
            self._create_pagamento(contrato, date(2026, 1, 1))
            self._create_pagamento(contrato, date(2026, 2, 1))
            self._create_pagamento(contrato, date(2026, 5, 1))

            response = self._solicitar_refinanciamento(contrato, client=client)
            self.assertEqual(response.status_code, 201, response.json())

    def test_contrato_manual_totalmente_quitado_aparece_na_tab_de_aptos(self):
        contrato = self._create_contrato(
            "92345678901",
            admin_manual_layout_enabled=True,
        )
        self._create_manual_cycle_quitado(contrato)

        response = self.agent_client.get(
            "/api/v1/contratos/",
            {"status_renovacao": Refinanciamento.Status.APTO_A_RENOVAR},
        )

        self.assertEqual(response.status_code, 200, response.json())
        row = next(
            item for item in response.json()["results"] if item["id"] == contrato.id
        )
        self.assertEqual(row["status_renovacao"], Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertEqual(row["ciclo_apto"]["numero"], 1)
        self.assertEqual(row["ciclo_apto"]["status"], Ciclo.Status.APTO_A_RENOVAR)

    def test_fluxo_manual_permite_solicitar_liquidacao_quando_ciclo_esta_quitado(self):
        contrato = self._create_contrato(
            "93345678901",
            admin_manual_layout_enabled=True,
        )
        self._create_manual_cycle_quitado(contrato)

        response = self.agent_client.post(
            f"/api/v1/refinanciamentos/{contrato.id}/solicitar-liquidacao/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.json())
        refinanciamento = Refinanciamento.objects.get(pk=response.json()["id"])
        self.assertEqual(
            refinanciamento.status,
            Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
        )
