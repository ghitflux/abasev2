from __future__ import annotations

from datetime import date
from decimal import Decimal
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_associado_visual_status_payload,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import LiquidacaoContrato


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LiquidacaoContratoViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_tesoureiro = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")

        cls.admin = cls._create_user("admin.liquidacao@abase.local", cls.role_admin, "Admin")
        cls.tesoureiro = cls._create_user(
            "tes.liquidacao@abase.local",
            cls.role_tesoureiro,
            "Tesoureiro",
        )
        cls.agente = cls._create_user("agente.liquidacao@abase.local", cls.role_agente, "Agente")

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

    def _create_associado(
        self,
        cpf: str,
        *,
        status: str = Associado.Status.ATIVO,
    ) -> Associado:
        return Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=status,
            agente_responsavel=self.agente,
        )

    def _create_contract_fixture(
        self,
        *,
        cpf: str = "77852621368",
        with_other_active_contract: bool = False,
        associado_status: str = Associado.Status.ATIVO,
    ) -> tuple[Associado, Contrato]:
        associado = self._create_associado(cpf, status=associado_status)
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=f"CTR-{cpf[-6:]}",
            valor_bruto=Decimal("18000.00"),
            valor_liquido=Decimal("10000.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("630.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 3),
            data_aprovacao=date(2026, 1, 3),
            data_primeira_mensalidade=date(2026, 1, 1),
            mes_averbacao=date(2026, 1, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 5),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.NAO_DESCONTADO,
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.EM_PREVISAO,
                ),
            ]
        )
        if with_other_active_contract:
            Contrato.objects.create(
                associado=associado,
                agente=self.agente,
                codigo=f"CTR-ATIVO-{cpf[-4:]}",
                valor_bruto=Decimal("9000.00"),
                valor_liquido=Decimal("5000.00"),
                valor_mensalidade=Decimal("250.00"),
                prazo_meses=3,
                status=Contrato.Status.ATIVO,
                data_contrato=date(2026, 2, 3),
                data_aprovacao=date(2026, 2, 3),
                data_primeira_mensalidade=date(2026, 2, 1),
            )
        return associado, contrato

    def _liquidar_payload(self, **overrides):
        payload = {
            "origem_solicitacao": "agente",
            "data_liquidacao": "2026-03-21",
            "valor_total": "600.00",
            "observacao": "Liquidação final do contrato.",
            "comprovante": SimpleUploadedFile(
                "liquidacao.pdf",
                b"arquivo",
                content_type="application/pdf",
            ),
        }
        payload.update(overrides)
        if payload.get("comprovante") is None:
            payload.pop("comprovante", None)
        return payload

    def test_lista_contratos_elegiveis_para_liquidacao(self):
        associado, contrato = self._create_contract_fixture()
        associado_sem_elegiveis, contrato_sem_elegiveis = self._create_contract_fixture(
            cpf="77852621399",
        )
        Parcela.objects.filter(ciclo__contrato=contrato_sem_elegiveis).update(
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )

        response = self.tes_client.get("/api/v1/tesouraria/liquidacoes/", {"status": "elegivel"})

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        ids = {row["contrato_id"] for row in payload["results"]}
        self.assertIn(contrato.id, ids)
        self.assertIn(contrato_sem_elegiveis.id, ids)
        row = next(row for row in payload["results"] if row["contrato_id"] == contrato.id)
        row_sem_elegiveis = next(
            row
            for row in payload["results"]
            if row["contrato_id"] == contrato_sem_elegiveis.id
        )
        self.assertEqual(row["quantidade_parcelas"], 2)
        self.assertEqual(row["quantidade_parcelas_contrato"], 3)
        self.assertEqual(len(row["parcelas"]), 3)
        self.assertEqual(row["status_liquidacao"], "elegivel_agora")
        self.assertEqual(row["status_operacional"], "elegivel_agora")
        self.assertTrue(row["pode_liquidar_agora"])
        status_associado = get_associado_visual_status_payload(associado)
        status_associado_sem_elegiveis = get_associado_visual_status_payload(
            associado_sem_elegiveis
        )
        self.assertEqual(
            row["status_associado"],
            status_associado["status_visual_slug"],
        )
        self.assertEqual(
            row["status_associado_label"],
            status_associado["status_visual_label"],
        )
        self.assertEqual(row_sem_elegiveis["quantidade_parcelas"], 0)
        self.assertEqual(row_sem_elegiveis["quantidade_parcelas_contrato"], 3)
        self.assertEqual(len(row_sem_elegiveis["parcelas"]), 3)
        self.assertEqual(row_sem_elegiveis["status_operacional"], "elegivel_agora")
        self.assertTrue(row_sem_elegiveis["pode_liquidar_agora"])
        self.assertEqual(payload["kpis"]["total_contratos"], 2)
        self.assertEqual(payload["kpis"]["liquidaveis_agora"], 2)
        self.assertEqual(payload["kpis"]["sem_parcelas_elegiveis"], 0)
        self.assertEqual(
            payload["kpis"]["por_status_associado"][
                status_associado["status_visual_slug"]
            ],
            1,
        )
        self.assertEqual(
            payload["kpis"]["por_status_associado"][
                status_associado_sem_elegiveis["status_visual_slug"]
            ],
            1,
        )

    def test_lista_kpis_deduplica_associado_por_status(self):
        _associado, contrato = self._create_contract_fixture(
            cpf="77852621409",
            with_other_active_contract=True,
        )

        response = self.tes_client.get("/api/v1/tesouraria/liquidacoes/", {"status": "elegivel"})

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        contrato_rows = [
            row for row in payload["results"] if row["associado_id"] == contrato.associado_id
        ]
        self.assertEqual(len(contrato_rows), 1)
        self.assertEqual(contrato_rows[0]["contrato_id"], contrato.id)
        self.assertEqual(payload["kpis"]["associados_impactados"], 1)
        status_associado = get_associado_visual_status_payload(contrato.associado)
        self.assertEqual(
            payload["kpis"]["por_status_associado"][
                status_associado["status_visual_slug"]
            ],
            1,
        )

    def test_lista_fila_inclui_associado_sem_contrato_operacional_liquidavel(self):
        associado, contrato = self._create_contract_fixture(cpf="77852621410")
        contrato.status = Contrato.Status.ENCERRADO
        contrato.save(update_fields=["status", "updated_at"])

        response = self.tes_client.get("/api/v1/tesouraria/liquidacoes/", {"status": "elegivel"})

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        row = next(
            row for row in payload["results"] if row["associado_id"] == associado.id
        )
        self.assertEqual(row["contrato_id"], contrato.id)
        self.assertEqual(row["status_contrato"], Contrato.Status.ENCERRADO)
        self.assertEqual(row["status_operacional"], "sem_parcelas_elegiveis")
        self.assertFalse(row["pode_liquidar_agora"])
        self.assertEqual(row["quantidade_parcelas"], 0)
        self.assertEqual(row["quantidade_parcelas_contrato"], 3)
        self.assertEqual(len(row["parcelas"]), 3)

    def test_lista_filtra_por_agente_status_etapa_e_periodo(self):
        associado, contrato = self._create_contract_fixture(cpf="77852621411")
        EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.TESOURARIA,
            status=EsteiraItem.Situacao.EM_ANDAMENTO,
        )
        _outro_associado, outro_contrato = self._create_contract_fixture(cpf="77852621412")
        outro_contrato.agente = None
        outro_contrato.data_contrato = date(2026, 1, 15)
        outro_contrato.save(update_fields=["agente", "data_contrato", "updated_at"])

        response = self.tes_client.get(
            "/api/v1/tesouraria/liquidacoes/",
            {
                "status": "elegivel",
                "agente": self.agente.full_name,
                "status_associado": get_associado_visual_status_payload(associado)[
                    "status_visual_slug"
                ],
                "etapa_fluxo": EsteiraItem.Etapa.TESOURARIA,
                "data_inicio": "2026-01-01",
                "data_fim": "2026-01-10",
            },
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["contrato_id"], contrato.id)

    def test_lista_elegiveis_identifica_solicitacao_vinda_da_renovacao(self):
        associado, contrato = self._create_contract_fixture(cpf="77852621388")
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2026-01|2026-02|2026-03",
        )

        response = self.tes_client.get("/api/v1/tesouraria/liquidacoes/", {"status": "elegivel"})
        self.assertEqual(response.status_code, 200, response.json())
        row = next(row for row in response.json()["results"] if row["contrato_id"] == contrato.id)
        self.assertEqual(
            row["status_renovacao"],
            Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
        )
        self.assertEqual(row["origem_solicitacao"], "renovacao")

    def test_liquidacao_marca_parcelas_contrato_e_associado(self):
        associado, contrato = self._create_contract_fixture()

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(),
        )

        self.assertEqual(response.status_code, 201, response.json())
        contrato.refresh_from_db()
        associado.refresh_from_db()
        parcelas = list(
            Parcela.objects.filter(ciclo__contrato=contrato).order_by("numero")
        )
        self.assertEqual(contrato.status, Contrato.Status.ENCERRADO)
        self.assertEqual(associado.status, Associado.Status.INATIVO)
        self.assertEqual(parcelas[0].status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcelas[1].status, Parcela.Status.LIQUIDADA)
        self.assertEqual(parcelas[2].status, Parcela.Status.LIQUIDADA)
        liquidacao = LiquidacaoContrato.objects.get(contrato=contrato, revertida_em__isnull=True)
        self.assertEqual(liquidacao.itens.count(), 2)
        self.assertEqual(liquidacao.origem_solicitacao, LiquidacaoContrato.OrigemSolicitacao.AGENTE)

        projection = build_contract_cycle_projection(contrato)
        self.assertEqual(len(projection["cycles"]), 1)
        self.assertEqual(
            [parcela["status"] for parcela in projection["cycles"][0]["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.LIQUIDADA,
                Parcela.Status.LIQUIDADA,
            ],
        )

    def test_liquidacao_aceita_multiplos_comprovantes(self):
        _associado, contrato = self._create_contract_fixture(cpf="77852621367")

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(
                observacao="Liquidação com anexos múltiplos.",
                comprovante=None,
                comprovantes=[
                    SimpleUploadedFile(
                        "liquidacao-principal.pdf",
                        b"arquivo-1",
                        content_type="application/pdf",
                    ),
                    SimpleUploadedFile(
                        "liquidacao-complementar.pdf",
                        b"arquivo-2",
                        content_type="application/pdf",
                    ),
                ],
            ),
        )

        self.assertEqual(response.status_code, 201, response.json())
        liquidacao = LiquidacaoContrato.objects.get(contrato=contrato, revertida_em__isnull=True)
        self.assertEqual(liquidacao.nome_comprovante, "liquidacao-principal.pdf")
        self.assertEqual(liquidacao.anexos.count(), 1)

    def test_liquidacao_aceita_contrato_nao_ativo_com_parcelas_elegiveis(self):
        _associado, contrato = self._create_contract_fixture(cpf="77852621363")
        contrato.status = Contrato.Status.EM_ANALISE
        contrato.save(update_fields=["status", "updated_at"])

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(observacao="Liquidação administrativa fora do fluxo ativo."),
        )

        self.assertEqual(response.status_code, 201, response.json())
        contrato.refresh_from_db()
        self.assertEqual(contrato.status, Contrato.Status.ENCERRADO)

    def test_liquidacao_exige_origem_solicitacao(self):
        _associado, contrato = self._create_contract_fixture(cpf="77852621366")

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            {
                "data_liquidacao": "2026-03-21",
                "valor_total": "600.00",
                "observacao": "Liquidação sem origem.",
                "comprovante": SimpleUploadedFile(
                    "liquidacao.pdf",
                    b"arquivo",
                    content_type="application/pdf",
                ),
            },
        )

        self.assertEqual(response.status_code, 400, response.json())
        self.assertIn("origem_solicitacao", response.json())

    def test_liquidacao_permita_encerramento_direto_sem_parcelas_elegiveis(self):
        _associado, contrato = self._create_contract_fixture(cpf="77852621365")
        Parcela.objects.filter(ciclo__contrato=contrato).update(
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 3, 5),
        )

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(observacao="Liquidação indevida."),
        )

        self.assertEqual(response.status_code, 201, response.json())
        contrato.refresh_from_db()
        self.assertEqual(contrato.status, Contrato.Status.ENCERRADO)
        liquidacao = LiquidacaoContrato.objects.get(contrato=contrato, revertida_em__isnull=True)
        self.assertEqual(liquidacao.itens.count(), 0)

    def test_liquidacao_nao_inativa_associado_com_outro_contrato_ativo(self):
        associado, contrato = self._create_contract_fixture(
            cpf="77852621369",
            with_other_active_contract=True,
        )

        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(observacao="Liquidação parcial do histórico."),
        )

        self.assertEqual(response.status_code, 201, response.json())
        associado.refresh_from_db()
        self.assertEqual(associado.status, Associado.Status.ATIVO)

    def test_reversao_admin_only_restaura_snapshot(self):
        associado, contrato = self._create_contract_fixture(cpf="77852621370")
        liquidar_response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(observacao="Liquidação a ser revertida."),
        )
        self.assertEqual(liquidar_response.status_code, 201, liquidar_response.json())

        forbidden_response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/reverter/",
            {"motivo_reversao": "Teste"},
            format="json",
        )
        self.assertEqual(forbidden_response.status_code, 400, forbidden_response.json())

        response = self.admin_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/reverter/",
            {"motivo_reversao": "Revisão administrativa"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        contrato.refresh_from_db()
        associado.refresh_from_db()
        parcelas = list(
            Parcela.objects.filter(ciclo__contrato=contrato).order_by("numero")
        )
        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertNotIn(
            Parcela.Status.LIQUIDADA,
            [parcela.status for parcela in parcelas],
        )
        liquidacao = LiquidacaoContrato.objects.get(contrato=contrato)
        self.assertIsNotNone(liquidacao.revertida_em)

    def test_reversao_falha_quando_parcela_foi_alterada_apos_liquidacao(self):
        _associado, contrato = self._create_contract_fixture(cpf="77852621371")
        response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(observacao="Liquidação inconsistente."),
        )
        self.assertEqual(response.status_code, 201, response.json())

        parcela = Parcela.objects.filter(ciclo__contrato=contrato, numero=2).first()
        assert parcela is not None
        parcela.status = Parcela.Status.DESCONTADO
        parcela.save(update_fields=["status", "updated_at"])

        reverse_response = self.admin_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/reverter/",
            {"motivo_reversao": "Tentativa inválida"},
            format="json",
        )

        self.assertEqual(reverse_response.status_code, 400, reverse_response.json())
        self.assertIn("Não é possível reverter", str(reverse_response.json()))

    def test_admin_pode_excluir_liquidacao(self):
        associado, contrato = self._create_contract_fixture(cpf="77852621372")
        liquidar_response = self.tes_client.post(
            f"/api/v1/tesouraria/liquidacoes/{contrato.id}/liquidar/",
            self._liquidar_payload(
                observacao="Liquidação para exclusão.",
                comprovante=SimpleUploadedFile(
                    "liquidacao-excluir.pdf",
                    b"arquivo",
                    content_type="application/pdf",
                ),
            ),
        )
        self.assertEqual(liquidar_response.status_code, 201, liquidar_response.json())
        liquidacao_id = liquidar_response.json()["liquidacao_id"]

        response = self.admin_client.post(
            f"/api/v1/tesouraria/liquidacoes/{liquidacao_id}/excluir/",
            {"motivo_exclusao": "Registro duplicado."},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        contrato.refresh_from_db()
        associado.refresh_from_db()
        parcelas = list(Parcela.objects.filter(ciclo__contrato=contrato).order_by("numero"))
        liquidacao = LiquidacaoContrato.all_objects.get(pk=liquidacao_id)

        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertNotIn(
            Parcela.Status.LIQUIDADA,
            [parcela.status for parcela in parcelas],
        )
        self.assertFalse(LiquidacaoContrato.objects.filter(pk=liquidacao_id).exists())
        self.assertIsNotNone(liquidacao.revertida_em)
        self.assertIsNotNone(liquidacao.deleted_at)
        self.assertEqual(liquidacao.itens.filter(deleted_at__isnull=True).count(), 0)
