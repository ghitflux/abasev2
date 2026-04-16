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
from apps.esteira.models import EsteiraItem
from apps.financeiro.models import Despesa
from apps.importacao.models import PagamentoMensalidade
from apps.tesouraria.models import DevolucaoAssociado, LiquidacaoContrato, Pagamento


class AdminDashboardViewSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.role_admin = Role.objects.create(codigo="ADMIN", nome="Administrador")
        cls.role_coord = Role.objects.create(codigo="COORDENADOR", nome="Coordenador")
        cls.role_agente = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.admin = cls._create_user("admin@abase.local", cls.role_admin, "Admin")
        cls.coordenador = cls._create_user("coord@abase.local", cls.role_coord, "Coord")
        cls.agente_a = cls._create_user("agente.a@abase.local", cls.role_agente, "Alice")
        cls.agente_b = cls._create_user("agente.b@abase.local", cls.role_agente, "Bruno")

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

        self.agent_client = APIClient()
        self.agent_client.force_authenticate(self.agente_a)

        self.coord_client = APIClient()
        self.coord_client.force_authenticate(self.coordenador)

        self._seed_dashboard_data()

    def _set_created_at(self, instance, value: datetime):
        instance.__class__.all_objects.filter(pk=instance.pk).update(created_at=value, updated_at=value)

    def _aware_datetime(self, year: int, month: int, day: int, hour: int = 9, minute: int = 0):
        return timezone.make_aware(datetime(year, month, day, hour, minute, 0))

    def _create_associado(
        self,
        *,
        nome: str,
        cpf: str,
        status: str,
        agente: User,
        created_at: datetime,
        data_nascimento: date | None = None,
    ) -> Associado:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            status=status,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            agente_responsavel=agente,
            data_nascimento=data_nascimento,
        )
        self._set_created_at(associado, created_at)
        return associado

    def _create_contract_with_cycle(
        self,
        *,
        associado: Associado,
        agente: User | None,
        codigo: str,
        data_contrato: date,
        auxilio_liberado_em: date | None,
        contract_status: str = Contrato.Status.ATIVO,
        cycle_status: str = Ciclo.Status.ABERTO,
        march_status: str = Parcela.Status.EM_ABERTO,
        monthly_value: Decimal = Decimal("30.00"),
    ) -> Contrato:
        contrato = Contrato.objects.create(
            associado=associado,
            agente=agente,
            codigo=codigo,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            margem_disponivel=monthly_value,
            valor_mensalidade=monthly_value,
            prazo_meses=3,
            status=contract_status,
            data_contrato=data_contrato,
            data_aprovacao=data_contrato,
            data_primeira_mensalidade=date(2026, 3, 1),
            auxilio_liberado_em=auxilio_liberado_em,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 3, 1),
            data_fim=date(2026, 5, 1),
            status=cycle_status,
            valor_total=monthly_value * 3,
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2026, 3, 1),
                    valor=monthly_value,
                    data_vencimento=date(2026, 3, 5),
                    status=march_status,
                    data_pagamento=date(2026, 3, 10)
                    if march_status == Parcela.Status.DESCONTADO
                    else None,
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2026, 4, 1),
                    valor=monthly_value,
                    data_vencimento=date(2026, 4, 5),
                    status=Parcela.Status.FUTURO,
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=date(2026, 5, 1),
                    valor=monthly_value,
                    data_vencimento=date(2026, 5, 5),
                    status=Parcela.Status.FUTURO,
                ),
            ]
        )
        return contrato

    def _seed_dashboard_data(self):
        self.active_effective = self._create_associado(
            nome="Maria Ativa",
            cpf="11111111111",
            status=Associado.Status.ATIVO,
            agente=self.agente_a,
            created_at=self._aware_datetime(2026, 3, 1),
            data_nascimento=date(1990, 3, 10),
        )
        self.analysis = self._create_associado(
            nome="Ana Analise",
            cpf="22222222222",
            status=Associado.Status.EM_ANALISE,
            agente=self.agente_a,
            created_at=self._aware_datetime(2026, 3, 2),
        )
        self.pending = self._create_associado(
            nome="Paulo Pendente",
            cpf="33333333333",
            status=Associado.Status.PENDENTE,
            agente=self.agente_b,
            created_at=self._aware_datetime(2026, 3, 3),
        )
        self.inadimplent = self._create_associado(
            nome="Ines Inadimplente",
            cpf="44444444444",
            status=Associado.Status.INADIMPLENTE,
            agente=self.agente_b,
            created_at=self._aware_datetime(2026, 3, 4),
        )
        self.renewed = self._create_associado(
            nome="Rita Renovada",
            cpf="55555555555",
            status=Associado.Status.ATIVO,
            agente=self.agente_a,
            created_at=self._aware_datetime(2026, 2, 15),
        )
        self.apt = self._create_associado(
            nome="Afonso Apto",
            cpf="66666666666",
            status=Associado.Status.ATIVO,
            agente=self.agente_b,
            created_at=self._aware_datetime(2026, 2, 18),
        )

        self.active_effective_contract = self._create_contract_with_cycle(
            associado=self.active_effective,
            agente=self.agente_a,
            codigo="CTR-A1",
            data_contrato=date(2026, 3, 1),
            auxilio_liberado_em=date(2026, 3, 5),
            cycle_status=Ciclo.Status.ABERTO,
            march_status=Parcela.Status.DESCONTADO,
        )
        self._create_contract_with_cycle(
            associado=self.analysis,
            agente=self.agente_a,
            codigo="CTR-A2",
            data_contrato=date(2026, 3, 2),
            auxilio_liberado_em=None,
            cycle_status=Ciclo.Status.ABERTO,
            march_status=Parcela.Status.EM_ABERTO,
        )
        self._create_contract_with_cycle(
            associado=self.pending,
            agente=self.agente_b,
            codigo="CTR-B1",
            data_contrato=date(2026, 3, 3),
            auxilio_liberado_em=None,
            cycle_status=Ciclo.Status.ABERTO,
            march_status=Parcela.Status.EM_ABERTO,
        )
        self.inadimplent_contract = self._create_contract_with_cycle(
            associado=self.inadimplent,
            agente=self.agente_b,
            codigo="CTR-B2",
            data_contrato=date(2026, 3, 4),
            auxilio_liberado_em=date(2026, 3, 7),
            cycle_status=Ciclo.Status.ABERTO,
            march_status=Parcela.Status.DESCONTADO,
            monthly_value=Decimal("45.00"),
        )
        self.renewed_contract = self._create_contract_with_cycle(
            associado=self.renewed,
            agente=self.agente_a,
            codigo="CTR-A3",
            data_contrato=date(2026, 2, 20),
            auxilio_liberado_em=date(2026, 3, 8),
            cycle_status=Ciclo.Status.CICLO_RENOVADO,
            march_status=Parcela.Status.DESCONTADO,
        )
        self.apt_contract = self._create_contract_with_cycle(
            associado=self.apt,
            agente=self.agente_b,
            codigo="CTR-B3",
            data_contrato=date(2026, 2, 22),
            auxilio_liberado_em=None,
            cycle_status=Ciclo.Status.ABERTO,
            march_status=Parcela.Status.EM_ABERTO,
        )
        apt_cycle = self.apt_contract.ciclos.get(numero=1)
        apt_cycle.parcelas.filter(numero=1).update(status=Parcela.Status.EM_ABERTO)
        apt_cycle.parcelas.filter(numero=2).update(status=Parcela.Status.DESCONTADO, data_pagamento=date(2026, 4, 10))
        apt_cycle.parcelas.filter(numero=3).update(status=Parcela.Status.DESCONTADO, data_pagamento=date(2026, 5, 10))

        EsteiraItem.objects.create(
            associado=self.analysis,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        EsteiraItem.objects.create(
            associado=self.pending,
            etapa_atual=EsteiraItem.Etapa.TESOURARIA,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )

        PagamentoMensalidade.objects.create(
            import_uuid="pm-1",
            referencia_month=date(2026, 3, 1),
            status_code="1",
            matricula=self.active_effective.matricula_orgao,
            cpf_cnpj=self.active_effective.cpf_cnpj,
            nome_relatorio=self.active_effective.nome_completo,
            associado=self.active_effective,
            valor=Decimal("30.00"),
        )
        PagamentoMensalidade.objects.create(
            import_uuid="pm-2",
            referencia_month=date(2026, 3, 1),
            status_code="4",
            matricula=self.renewed.matricula_orgao,
            cpf_cnpj=self.renewed.cpf_cnpj,
            nome_relatorio=self.renewed.nome_completo,
            associado=self.renewed,
            valor=Decimal("30.00"),
        )
        PagamentoMensalidade.objects.create(
            import_uuid="pm-3",
            referencia_month=date(2026, 3, 1),
            status_code="",
            matricula=self.inadimplent.matricula_orgao,
            cpf_cnpj=self.inadimplent.cpf_cnpj,
            nome_relatorio=self.inadimplent.nome_completo,
            associado=self.inadimplent,
            valor=Decimal("45.00"),
            recebido_manual=Decimal("45.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=self._aware_datetime(2026, 3, 11, 12, 0),
        )

        Pagamento.objects.create(
            cadastro=self.active_effective,
            created_by=self.admin,
            contrato_codigo=self.active_effective_contract.codigo,
            cpf_cnpj=self.active_effective.cpf_cnpj,
            full_name=self.active_effective.nome_completo,
            agente_responsavel=self.agente_a.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("25.00"),
            paid_at=self._aware_datetime(2026, 3, 12, 10, 30),
            forma_pagamento="pix",
        )

        DevolucaoAssociado.objects.create(
            contrato=self.inadimplent_contract,
            associado=self.inadimplent,
            tipo=DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO,
            data_devolucao=date(2026, 3, 12),
            quantidade_parcelas=1,
            valor=Decimal("15.00"),
            motivo="Ajuste de desconto indevido",
            comprovante=SimpleUploadedFile(
                "devolucao.pdf",
                b"pdf",
                content_type="application/pdf",
            ),
            nome_comprovante="devolucao.pdf",
            competencia_referencia=date(2026, 3, 1),
            nome_snapshot=self.inadimplent.nome_completo,
            cpf_cnpj_snapshot=self.inadimplent.cpf_cnpj,
            matricula_snapshot=self.inadimplent.matricula_orgao,
            agente_snapshot=self.agente_b.full_name,
            contrato_codigo_snapshot=self.inadimplent_contract.codigo,
            realizado_por=self.admin,
        )

        Despesa.objects.create(
            categoria="Operacional",
            descricao="Servidor cloud",
            valor=Decimal("12.50"),
            data_despesa=date(2026, 3, 10),
            data_pagamento=date(2026, 3, 12),
            status=Despesa.Status.PAGO,
            user=self.admin,
        )

    def test_endpoints_permitem_coordenador_e_negam_agente(self):
        urls = [
            "/api/v1/dashboard/admin/resumo-geral/",
            "/api/v1/dashboard/admin/tesouraria/",
            "/api/v1/dashboard/admin/resumo-mensal-associacao/",
            "/api/v1/dashboard/admin/novos-associados/",
            "/api/v1/dashboard/admin/agentes/",
            "/api/v1/dashboard/admin/detalhes/?section=summary&metric=associados_ativos",
        ]

        for url in urls:
            with self.subTest(url=url):
                coord_response = self.coord_client.get(url)
                self.assertEqual(coord_response.status_code, 200)
                response = self.agent_client.get(url)
                self.assertEqual(response.status_code, 403)

    def test_resumo_geral_agrega_kpis_e_series(self):
        response = self.client.get("/api/v1/dashboard/admin/resumo-geral/", {"competencia": "2026-03"})
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()

        kpis = {item["key"]: item for item in payload["kpis"]}
        self.assertEqual(kpis["associados_cadastrados"]["numeric_value"], 6.0)
        self.assertEqual(kpis["associados_ativos"]["numeric_value"], 3.0)
        self.assertEqual(kpis["em_processo_efetivacao"]["numeric_value"], 2.0)
        self.assertEqual(kpis["inadimplentes"]["numeric_value"], 1.0)
        self.assertEqual(kpis["renovacoes_ciclo"]["numeric_value"], 1.0)
        self.assertEqual(kpis["aptos_renovacao"]["numeric_value"], 1.0)
        self.assertEqual(kpis["cadastros_pendentes"]["numeric_value"], 2.0)
        self.assertTrue(any(item["bucket"] == "2026-03" for item in payload["trend_lines"]))

    def test_resumo_e_detalhes_respeitam_filtro_status(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/resumo-geral/",
            {"competencia": "2026-03", "status": Associado.Status.ATIVO},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        kpis = {item["key"]: item for item in payload["kpis"]}
        self.assertEqual(kpis["associados_cadastrados"]["numeric_value"], 3.0)

        flow = {item["key"]: item for item in payload["flow_bars"]}
        self.assertEqual(flow["efetivados"]["value"], 2)

        summary_detail = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "summary",
                "metric": "associados_cadastrados",
                "competencia": "2026-03",
                "status": Associado.Status.ATIVO,
                "page_size": "all",
            },
        )
        self.assertEqual(summary_detail.status_code, 200, summary_detail.json())
        self.assertEqual(summary_detail.json()["count"], 3)

        novos_detail = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "new-associados",
                "metric": "novos_cadastrados",
                "date_start": "2026-03-01",
                "date_end": "2026-03-31",
                "status": Associado.Status.ATIVO,
                "page_size": "all",
            },
        )
        self.assertEqual(novos_detail.status_code, 200, novos_detail.json())
        self.assertEqual(novos_detail.json()["count"], 1)

    def test_tesouraria_retorna_cards_projecao_e_composicao(self):
        response = self.client.get("/api/v1/dashboard/admin/tesouraria/", {"competencia": "2026-03"})
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        cards = {item["key"]: item for item in payload["cards"]}

        self.assertEqual(cards["valores_recebidos"]["value"], "105.00")
        self.assertEqual(cards["baixas_importacao"]["numeric_value"], 2.0)
        self.assertEqual(cards["baixas_manuais"]["numeric_value"], 1.0)
        self.assertEqual(cards["inadimplentes_quitados"]["numeric_value"], 1.0)
        self.assertEqual(cards["contratos_novos"]["numeric_value"], 4.0)
        self.assertEqual(cards["saidas_agentes_associados"]["value"], "33.00")
        self.assertEqual(cards["despesas"]["value"], "12.50")
        self.assertEqual(cards["receita_liquida_associacao"]["value"], "59.50")
        self.assertEqual(len(payload["projection_area"]), 3)
        self.assertGreater(cards["projecao_total"]["numeric_value"], 0)

    def test_tesouraria_respeita_day_e_valida_conflito_com_competencia(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/tesouraria/",
            {"competencia": "2026-03", "day": "2026-03-12"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        cards = {item["key"]: item for item in response.json()["cards"]}
        self.assertEqual(cards["valores_recebidos"]["value"], "0.00")
        self.assertEqual(cards["saidas_agentes_associados"]["value"], "33.00")
        self.assertEqual(cards["despesas"]["value"], "12.50")

        invalid = self.client.get(
            "/api/v1/dashboard/admin/tesouraria/",
            {"competencia": "2026-03", "day": "2026-04-12"},
        )
        self.assertEqual(invalid.status_code, 400)

    def test_resumo_mensal_associacao_retorna_12_meses_e_metricas_consolidadas(self):
        Despesa.objects.create(
            categoria="Complementos",
            descricao="Compensação no caixa",
            valor=Decimal("80.00"),
            data_despesa=date(2026, 3, 15),
            data_pagamento=date(2026, 3, 15),
            status=Despesa.Status.PAGO,
            natureza=Despesa.Natureza.COMPLEMENTO_RECEITA,
            user=self.admin,
        )
        LiquidacaoContrato.objects.create(
            contrato=self.active_effective_contract,
            realizado_por=self.admin,
            data_liquidacao=date(2026, 3, 20),
            valor_total=Decimal("30.00"),
            comprovante=SimpleUploadedFile(
                "liquidacao.pdf",
                b"pdf",
                content_type="application/pdf",
            ),
            nome_comprovante="liquidacao.pdf",
            origem_solicitacao=LiquidacaoContrato.OrigemSolicitacao.ADMINISTRACAO,
            observacao="Liquidação administrativa",
        )
        analysis_contract = Contrato.objects.get(codigo="CTR-A2")
        Contrato.objects.filter(pk=analysis_contract.pk).update(
            status=Contrato.Status.ENCERRADO,
            updated_at=self._aware_datetime(2026, 3, 25),
        )

        response = self.client.get(
            "/api/v1/dashboard/admin/resumo-mensal-associacao/",
            {"competencia": "2026-03"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()

        self.assertEqual(payload["competencia"], "2026-03")
        self.assertEqual(len(payload["rows"]), 12)
        march = next(row for row in payload["rows"] if row["mes"] == "2026-03-01")
        self.assertEqual(march["complementos_receita"], "80.00")
        self.assertEqual(march["saldo_positivo"], "67.50")
        self.assertEqual(march["novos_associados"], 3)
        self.assertEqual(march["desvinculados"], 2)
        self.assertEqual(march["renovacoes_associado"], 1)

    def test_resumo_mensal_associacao_alinha_renovacoes_com_detalhamento_filtrado(self):
        summary = self.client.get(
            "/api/v1/dashboard/admin/resumo-mensal-associacao/",
            {
                "competencia": "2026-03",
                "agent_id": self.agente_a.id,
                "status": Associado.Status.ATIVO,
            },
        )
        self.assertEqual(summary.status_code, 200, summary.json())
        march = next(row for row in summary.json()["rows"] if row["mes"] == "2026-03-01")

        detail = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "summary",
                "metric": "trend:renovacoes:2026-03",
                "agent_id": self.agente_a.id,
                "status": Associado.Status.ATIVO,
                "page_size": "all",
            },
        )
        self.assertEqual(detail.status_code, 200, detail.json())
        self.assertEqual(march["renovacoes_associado"], detail.json()["count"])
        row = detail.json()["results"][0]
        self.assertEqual(row["data_entrada_associacao"], "2026-03-08")
        self.assertEqual(row["parcelas_descontadas"], 1)
        self.assertEqual(row["status_resumo_mensal"], "ativo")

    def test_resumo_mensal_associacao_detalhes_de_novos_associados_expoem_campos_normalizados(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "summary",
                "metric": "trend:efetivados:2026-03",
                "page_size": "all",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        maria = next(
            row for row in payload["results"] if row["associado_nome"] == "Maria Ativa"
        )
        self.assertEqual(maria["data_nascimento"], "1990-03-10")
        self.assertEqual(maria["data_entrada_associacao"], "2026-03-05")
        self.assertEqual(maria["parcelas_descontadas"], 1)
        self.assertEqual(maria["status_resumo_mensal"], "ativo")
        self.assertEqual(maria["valor"], "30.00")

    def test_tesouraria_considera_liquidacoes_nos_valores_recebidos(self):
        LiquidacaoContrato.objects.create(
            contrato=self.active_effective_contract,
            realizado_por=self.admin,
            data_liquidacao=date(2026, 3, 20),
            valor_total=Decimal("30.00"),
            comprovante=SimpleUploadedFile(
                "liquidacao-dashboard.pdf",
                b"pdf",
                content_type="application/pdf",
            ),
            nome_comprovante="liquidacao-dashboard.pdf",
            origem_solicitacao=LiquidacaoContrato.OrigemSolicitacao.ADMINISTRACAO,
            observacao="Liquidação para composição do dashboard",
        )

        response = self.client.get(
            "/api/v1/dashboard/admin/tesouraria/",
            {"competencia": "2026-03"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        cards = {item["key"]: item for item in response.json()["cards"]}
        self.assertEqual(cards["valores_recebidos"]["value"], "135.00")

        detail = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "treasury",
                "metric": "valores_recebidos",
                "competencia": "2026-03",
                "page_size": "all",
            },
        )
        self.assertEqual(detail.status_code, 200, detail.json())
        payload = detail.json()
        self.assertEqual(payload["count"], 4)
        self.assertTrue(
            any(row["origem"] == "Liquidacao de contrato" for row in payload["results"])
        )

    def test_novos_associados_retorna_cards_e_distribuicao(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/novos-associados/",
            {"date_start": "2026-03-01", "date_end": "2026-03-31"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        cards = {item["key"]: item for item in payload["cards"]}

        self.assertEqual(cards["novos_cadastrados"]["numeric_value"], 4.0)
        self.assertEqual(cards["novos_ativos"]["numeric_value"], 1.0)
        self.assertEqual(cards["novos_em_processo"]["numeric_value"], 2.0)
        self.assertEqual(cards["novos_inadimplentes"]["numeric_value"], 1.0)
        self.assertEqual(payload["status_pie"][0]["detail_metric"].startswith("status:"), True)

    def test_agentes_retorna_ranking_por_volume_e_novas_metricas(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/agentes/",
            {
                "competencia": "2026-03",
                "date_start": "2026-03-01",
                "date_end": "2026-03-31",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()

        cards = {item["key"]: item for item in payload["cards"]}
        self.assertEqual(cards["volume_total"]["value"], "105.00")
        self.assertEqual(cards["com_devolucao"]["numeric_value"], 1.0)
        self.assertEqual(cards["renovados"]["numeric_value"], 1.0)
        self.assertEqual(cards["aptos_renovar"]["numeric_value"], 1.0)
        self.assertEqual(payload["ranking"][0]["agent_name"], self.agente_a.full_name)
        self.assertEqual(payload["ranking"][0]["volume_financeiro"], 60.0)
        self.assertEqual(payload["ranking"][0]["efetivados"], 2)
        self.assertEqual(payload["ranking"][1]["agent_name"], self.agente_b.full_name)
        self.assertEqual(payload["ranking"][1]["volume_financeiro"], 45.0)
        self.assertEqual(payload["ranking"][1]["efetivados"], 1)

    def test_detalhes_respeita_metricas_paginacao_e_page_size_all(self):
        paginated = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "summary",
                "metric": "associados_ativos",
                "page_size": 1,
            },
        )
        self.assertEqual(paginated.status_code, 200, paginated.json())
        paginated_payload = paginated.json()
        self.assertEqual(paginated_payload["count"], 3)
        self.assertEqual(len(paginated_payload["results"]), 1)

        expanded = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "summary",
                "metric": "renovacoes_ciclo",
                "competencia": "2026-03",
                "page_size": "all",
            },
        )
        self.assertEqual(expanded.status_code, 200, expanded.json())
        expanded_payload = expanded.json()
        self.assertEqual(expanded_payload["count"], 1)
        self.assertEqual(expanded_payload["results"][0]["associado_nome"], "Rita Renovada")

    def test_detalhes_tesouraria_e_agentes_retorna_rows_especificos(self):
        treasury_response = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "treasury",
                "metric": "baixas_manuais",
                "competencia": "2026-03",
                "page_size": "all",
            },
        )
        self.assertEqual(treasury_response.status_code, 200, treasury_response.json())
        treasury_payload = treasury_response.json()
        self.assertEqual(treasury_payload["count"], 1)
        self.assertEqual(treasury_payload["results"][0]["associado_nome"], "Ines Inadimplente")

        agent_response = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "agentes",
                "metric": f"agente:{self.agente_a.id}:volume",
                "competencia": "2026-03",
                "date_start": "2026-03-01",
                "date_end": "2026-03-31",
                "page_size": "all",
            },
        )
        self.assertEqual(agent_response.status_code, 200, agent_response.json())
        agent_payload = agent_response.json()
        self.assertEqual(agent_payload["count"], 2)
        self.assertEqual(
            {row["contrato_codigo"] for row in agent_payload["results"]},
            {"CTR-A1", "CTR-A3"},
        )
        self.assertEqual(
            {row["valor"] for row in agent_payload["results"]},
            {"30.00"},
        )

        treasury_saida_response = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "treasury",
                "metric": "saidas_agentes_associados",
                "competencia": "2026-03",
                "page_size": "all",
            },
        )
        self.assertEqual(
            treasury_saida_response.status_code,
            200,
            treasury_saida_response.json(),
        )
        treasury_saida_payload = treasury_saida_response.json()
        self.assertEqual(treasury_saida_payload["count"], 1)
        self.assertEqual(treasury_saida_payload["results"][0]["valor"], "30.00")
        self.assertEqual(
            treasury_saida_payload["results"][0]["valor_associado"],
            "30.00",
        )
        self.assertEqual(
            treasury_saida_payload["results"][0]["valor_agente"],
            "3.00",
        )
        self.assertEqual(
            treasury_saida_payload["results"][0]["valor_total"],
            "33.00",
        )

    def test_detalhes_novos_associados_do_mes_retorna_data_nascimento(self):
        response = self.client.get(
            "/api/v1/dashboard/admin/detalhes/",
            {
                "section": "new-associados",
                "metric": "cadastros:2026-03",
                "date_start": "2026-03-01",
                "date_end": "2026-03-31",
                "page_size": "all",
            },
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 4)
        maria = next(
            row for row in payload["results"] if row["associado_nome"] == "Maria Ativa"
        )
        self.assertEqual(maria["cpf_cnpj"], "11111111111")
        self.assertEqual(maria["matricula"], "MAT-1111")
        self.assertEqual(maria["data_nascimento"], "1990-03-10")
        self.assertEqual(maria["agente_nome"], self.agente_a.full_name)
