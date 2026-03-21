from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_associado_visual_status_payload,
    get_contract_visual_status_payload,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import Pagamento


class CycleProjectionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente.ciclos@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Ciclos",
            is_active=True,
        )
        cls.agente.roles.add(role)

    def _create_associado(self, cpf: str, nome: str) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )

    def setUp(self):
        super().setUp()
        self._localdate_patcher = mock.patch(
            "apps.contratos.cycle_projection.timezone.localdate",
            return_value=date(2026, 3, 21),
        )
        self._localdate_patcher.start()
        self.addCleanup(self._localdate_patcher.stop)

    def _create_contrato(
        self,
        *,
        associado: Associado,
        valor_mensalidade: str = "300.00",
        prazo_meses: int = 3,
        data_primeira_mensalidade: date = date(2025, 10, 1),
    ) -> Contrato:
        return Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1200.00"),
            valor_mensalidade=Decimal(valor_mensalidade),
            prazo_meses=prazo_meses,
            status=Contrato.Status.ATIVO,
            data_contrato=data_primeira_mensalidade,
            data_aprovacao=data_primeira_mensalidade,
            data_primeira_mensalidade=data_primeira_mensalidade,
        )

    def _create_financial_row(
        self,
        contrato: Contrato,
        referencia: date,
        *,
        status_code: str,
        manual_status: str | None = None,
        manual_paid_at: datetime | None = None,
        recebido_manual: Decimal | None = None,
    ) -> PagamentoMensalidade:
        return PagamentoMensalidade.objects.create(
            created_by=self.agente,
            import_uuid=f"{contrato.id}-{referencia.isoformat()}-{status_code}",
            referencia_month=referencia,
            status_code=status_code,
            matricula=contrato.associado.matricula_orgao or contrato.associado.matricula,
            orgao_pagto="SEFAZ",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=contrato.valor_mensalidade,
            manual_status=manual_status,
            manual_paid_at=manual_paid_at,
            recebido_manual=recebido_manual,
            source_file_path=f"retornos/{referencia.strftime('%Y-%m')}.txt",
        )

    def test_projection_builds_sequential_cycles_from_effective_renewal(self):
        associado = self._create_associado("22808922353", "JOAQUIM VIEIRA FILHO")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="2")
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=73,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        unpaid_months = sorted(
            projection["unpaid_months"],
            key=lambda item: item["referencia_mes"],
        )
        avulsos = sorted(
            projection["movimentos_financeiros_avulsos"],
            key=lambda item: item["referencia_mes"],
        )

        self.assertEqual(len(cycles), 2)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 2, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycles[0]["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )
        self.assertEqual(cycles[0]["status"], Ciclo.Status.CICLO_RENOVADO)
        self.assertEqual(
            cycles[0]["status_visual_label"],
            "Renovado",
        )
        self.assertEqual(
            cycles[0]["data_solicitacao_renovacao"].date(),
            date(2026, 1, 19),
        )
        self.assertEqual(cycles[1]["data_renovacao"].date(), date(2026, 1, 19))
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycles[1]["parcelas"]],
            [
                Parcela.Status.EM_PREVISAO,
                Parcela.Status.EM_PREVISAO,
                Parcela.Status.EM_PREVISAO,
            ],
        )

        self.assertEqual(
            [item["referencia_mes"] for item in unpaid_months],
            [date(2025, 11, 1), date(2026, 1, 1)],
        )
        self.assertEqual([item["referencia_mes"] for item in avulsos], [])
        self.assertEqual(projection["status_renovacao"], "")
        self.assertEqual(
            get_contract_visual_status_payload(contrato, projection=projection)[
                "status_visual_label"
            ],
            "Ativo",
        )
        self.assertEqual(
            get_associado_visual_status_payload(associado)["status_visual_label"],
            "Ativo",
        )

    def test_projection_infers_missing_overdue_month_without_explicit_return_row(self):
        associado = self._create_associado("22808922353", "JOAQUIM VIEIRA FILHO")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="2")
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=74,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        unpaid_months = sorted(
            projection["unpaid_months"],
            key=lambda item: item["referencia_mes"],
        )

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 2, 1)],
        )
        self.assertEqual(
            [item["referencia_mes"] for item in unpaid_months],
            [date(2025, 11, 1), date(2026, 1, 1)],
        )
        self.assertEqual(
            [item["source"] for item in unpaid_months],
            ["implicit_gap", "pagamento_mensalidade"],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )

    def test_projection_prefers_mes_averbacao_as_cycle_one_seed(self):
        associado = self._create_associado("71000000005", "Associado Averbação")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 11, 5),
        )
        contrato.mes_averbacao = date(2025, 10, 1)
        contrato.save(update_fields=["mes_averbacao"])

        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")

        projection = build_contract_cycle_projection(contrato)
        cycle = sorted(projection["cycles"], key=lambda item: item["numero"])[0]

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycle["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 1, 1)],
        )

    def test_projection_uses_earliest_financial_reference_when_it_precedes_mes_averbacao(self):
        associado = self._create_associado("71000000006", "Associado Seed Financeiro")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 12, 5),
        )
        contrato.mes_averbacao = date(2025, 11, 1)
        contrato.save(update_fields=["mes_averbacao"])

        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")

        projection = build_contract_cycle_projection(contrato)
        cycle = sorted(projection["cycles"], key=lambda item: item["numero"])[0]

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycle["parcelas"]],
            [date(2025, 10, 1), date(2025, 11, 1), date(2025, 12, 1)],
        )

    def test_projection_uses_first_legacy_renewal_origin_refs_to_seed_cycle_one(self):
        associado = self._create_associado("71000000007", "Associado Seed Refi")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 12, 5),
        )
        contrato.mes_averbacao = date(2025, 11, 1)
        contrato.auxilio_liberado_em = date(2025, 10, 6)
        contrato.save(update_fields=["mes_averbacao", "auxilio_liberado_em"])

        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=320,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2025, 12, 26, 18, 54, 32)
            ),
            executado_em=timezone.make_aware(
                datetime(2025, 12, 26, 18, 54, 32)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 1, 1)],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )

    def test_projection_ignores_orphan_legacy_renewal_incompatible_with_contract_start(self):
        associado = self._create_associado("53729226304", "FRANCISCO FERNANDES NETO")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="250.00",
            data_primeira_mensalidade=date(2026, 2, 6),
        )
        contrato.mes_averbacao = date(2026, 1, 1)
        contrato.auxilio_liberado_em = date(2026, 1, 5)
        contrato.status = Contrato.Status.EM_ANALISE
        contrato.save(
            update_fields=["mes_averbacao", "auxilio_liberado_em", "status"]
        )

        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1",)
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1",)
        PagamentoMensalidade.objects.create(
            created_by=self.agente,
            import_uuid=f"{contrato.id}-2026-03-01-M",
            referencia_month=date(2026, 3, 1),
            status_code="M",
            matricula=contrato.associado.matricula_orgao or contrato.associado.matricula,
            orgao_pagto="SEFAZ",
            nome_relatorio=contrato.associado.nome_completo,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            associado=contrato.associado,
            valor=Decimal("250.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime(2026, 3, 5, 0, 0, 0)),
            recebido_manual=Decimal("250.00"),
            source_file_path="retornos/2026-03-manual.pdf",
        )

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=350,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 3, 13, 12, 13, 29)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 3, 13, 12, 13, 29)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            contrato_codigo_origem="",
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(len(cycles), 1)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 4, 1)],
        )

    def test_projection_restores_treasury_backed_legacy_renewal_without_overlapping_cycle_one(self):
        associado = self._create_associado("49684639368", "ABNER OLIVEIRA NETO")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="200.00",
            data_primeira_mensalidade=date(2025, 12, 5),
        )
        contrato.mes_averbacao = date(2025, 11, 1)
        contrato.auxilio_liberado_em = date(2025, 11, 4)
        contrato.save(update_fields=["mes_averbacao", "auxilio_liberado_em"])

        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.agente,
            contrato_codigo="",
            contrato_margem_disponivel=Decimal("420.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("200.00"),
            paid_at=timezone.make_aware(datetime(2026, 2, 4, 11, 40, 27)),
            forma_pagamento="manual",
            legacy_tesouraria_pagamento_id=359,
            origem=Pagamento.Origem.LEGADO,
            notes="Registro manual (COORDENADOR) a partir do arquivo retorno",
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=233,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 2, 10, 10, 12, 55)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 2, 10, 10, 12, 55)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            contrato_codigo_origem="",
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(len(cycles), 2)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )
        self.assertEqual(cycles[0]["status"], Ciclo.Status.CICLO_RENOVADO)
        self.assertEqual(cycles[1]["parcelas"][0]["status"], Parcela.Status.EM_PREVISAO)

    def test_projection_clamps_renewed_cycle_start_after_previous_cycle_window(self):
        associado = self._create_associado("78268630310", "NUBIA MARIA BATISTA MARTINS")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="500.00",
            data_primeira_mensalidade=date(2025, 12, 5),
        )
        contrato.mes_averbacao = date(2025, 11, 1)
        contrato.auxilio_liberado_em = date(2025, 11, 3)
        contrato.save(update_fields=["mes_averbacao", "auxilio_liberado_em"])

        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")
        Pagamento.objects.create(
            cadastro=associado,
            created_by=self.agente,
            contrato_codigo="",
            contrato_margem_disponivel=Decimal("1050.00"),
            cpf_cnpj=associado.cpf_cnpj,
            full_name=associado.nome_completo,
            agente_responsavel=self.agente.full_name,
            status=Pagamento.Status.PAGO,
            valor_pago=Decimal("500.00"),
            paid_at=timezone.make_aware(datetime(2026, 1, 30, 11, 28, 57)),
            forma_pagamento="pix",
            legacy_tesouraria_pagamento_id=354,
            origem=Pagamento.Origem.LEGADO,
            notes="Registro manual (COORDENADOR) a partir do arquivo retorno",
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=124,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 30, 14, 2, 58)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 30, 14, 2, 58)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            contrato_codigo_origem="",
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )

    def test_projection_for_four_month_contract_keeps_last_slot_in_previsao(self):
        associado = self._create_associado("11122233344", "Associado Quatro Parcelas")
        contrato = self._create_contrato(
            associado=associado,
            prazo_meses=4,
            valor_mensalidade="400.00",
            data_primeira_mensalidade=date(2026, 2, 1),
        )
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 3, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 4, 1), status_code="1")

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(len(cycles), 1)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycles[0]["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.EM_PREVISAO,
            ],
        )
        self.assertEqual(cycles[0]["status"], Ciclo.Status.APTO_A_RENOVAR)
        self.assertEqual(projection["status_renovacao"], Refinanciamento.Status.APTO_A_RENOVAR)
        self.assertEqual(
            cycles[0]["status_visual_label"],
            "Apto para Renovação",
        )

    def test_associado_uses_worst_active_contract_visual_status(self):
        associado = self._create_associado("99988877766", "Associado Multi Contrato")
        contrato_renovado = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        contrato_aberto = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2026, 5, 1),
        )

        self._create_financial_row(contrato_renovado, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato_renovado, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato_renovado, date(2025, 12, 1), status_code="1")
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato_renovado,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=999,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato_renovado.codigo,
        )
        self._create_financial_row(contrato_aberto, date(2026, 5, 1), status_code="1")

        payload = get_associado_visual_status_payload(associado)
        self.assertEqual(
            payload["status_visual_label"],
            "Apto para Renovação",
        )

    def test_regularized_overdue_month_stays_outside_cycles(self):
        associado = self._create_associado("11199922233", "Regularizacao Fora Do Ciclo")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(
            contrato,
            date(2025, 11, 1),
            status_code="M",
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime(2025, 12, 18, 9, 0, 0)),
            recebido_manual=Decimal("300.00"),
        )

        projection = build_contract_cycle_projection(contrato)
        cycle = sorted(projection["cycles"], key=lambda item: item["numero"])[0]

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycle["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 1, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycle["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.EM_PREVISAO,
            ],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in projection["unpaid_months"]
            ],
            [(date(2025, 11, 1), "quitada")],
        )
        self.assertEqual(projection["movimentos_financeiros_avulsos"], [])

    def test_manual_settlement_after_renewal_never_reenters_previous_cycle(self):
        associado = self._create_associado("11199922244", "Manual Após Renovação")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="2")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")
        self._create_financial_row(
            contrato,
            date(2025, 11, 1),
            status_code="M",
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime(2026, 2, 7, 15, 30, 0)),
            recebido_manual=Decimal("300.00"),
        )

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=173,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 19, 16, 40, 21)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 10, 1), date(2025, 12, 1), date(2026, 2, 1)],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in sorted(
                    projection["unpaid_months"],
                    key=lambda item: item["referencia_mes"],
                )
            ],
            [(date(2025, 11, 1), "quitada"), (date(2026, 1, 1), "nao_descontado")],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)],
        )
