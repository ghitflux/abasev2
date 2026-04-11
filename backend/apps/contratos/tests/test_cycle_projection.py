from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
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
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante, Refinanciamento
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

    def _create_small_value_return_item(
        self,
        contrato: Contrato,
        *,
        referencia: date,
        valor: str = "30.00",
        parcela: Parcela | None = None,
    ) -> ArquivoRetornoItem:
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome=f"retorno_{referencia.strftime('%Y_%m')}.txt",
            arquivo_url=f"retornos/{referencia.strftime('%Y-%m')}.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="SEFAZ",
            competencia=referencia,
            total_registros=1,
            processados=1,
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=self.agente,
        )
        return ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            matricula_servidor=contrato.associado.matricula_orgao or contrato.associado.matricula,
            nome_servidor=contrato.associado.nome_completo,
            competencia=referencia.strftime("%m/%Y"),
            valor_descontado=Decimal(valor),
            associado=contrato.associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
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
            "Concluído",
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

    def test_projection_moves_past_forecast_out_of_concluded_cycle(self):
        associado = self._create_associado("03877244311", "MARIA CICLO FORA")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=801,
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

        self.assertEqual(cycles[0]["status"], Ciclo.Status.PENDENCIA)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 12, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycles[0]["parcelas"]],
            [Parcela.Status.DESCONTADO],
        )
        self.assertEqual(
            cycles[0]["status_visual_label"],
            "Com Pendência",
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in sorted(
                    projection["unpaid_months"],
                    key=lambda item: item["referencia_mes"],
                )
            ],
            [
                (date(2025, 10, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2025, 11, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2026, 2, 1), Parcela.Status.NAO_DESCONTADO),
            ],
        )

    def test_small_value_imported_contract_stays_active_even_when_cycle_is_quitado(self):
        associado = self._create_associado("71000000991", "Associado 30 Ativo")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="30.00",
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("90.00"),
        )
        parcelas = [
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=index,
                referencia_mes=referencia,
                valor=Decimal("30.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )
            for index, referencia in enumerate(
                [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
                start=1,
            )
        ]
        self._create_small_value_return_item(
            contrato,
            referencia=date(2026, 1, 1),
            parcela=parcelas[0],
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(cycles[0]["status"], Ciclo.Status.ABERTO)
        self.assertEqual(projection["status_renovacao"], "")
        self.assertEqual(
            get_contract_visual_status_payload(contrato, projection=projection)[
                "status_visual_label"
            ],
            "Ativo",
        )

    def test_small_value_imported_contract_override_does_not_release_apto_anymore(self):
        associado = self._create_associado("71000000993", "Associado 30 Override Bloqueado")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="30.00",
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        contrato.admin_manual_layout_enabled = True
        contrato.allow_small_value_renewal = True
        contrato.save(
            update_fields=[
                "admin_manual_layout_enabled",
                "allow_small_value_renewal",
                "updated_at",
            ]
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("90.00"),
        )
        parcelas = [
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=index,
                referencia_mes=referencia,
                valor=Decimal("30.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )
            for index, referencia in enumerate(
                [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
                start=1,
            )
        ]
        self._create_small_value_return_item(
            contrato,
            referencia=date(2026, 1, 1),
            parcela=parcelas[0],
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(cycles[0]["status"], Ciclo.Status.ABERTO)
        self.assertEqual(projection["status_renovacao"], "")

    def test_small_value_imported_contract_with_unpaid_month_stays_in_pendencia(self):
        associado = self._create_associado("71000000992", "Associado 50 Pendente")
        contrato = self._create_contrato(
            associado=associado,
            valor_mensalidade="50.00",
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("150.00"),
        )
        parcelas = [
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=1,
                referencia_mes=date(2026, 1, 1),
                valor=Decimal("50.00"),
                data_vencimento=date(2026, 1, 1),
                status=Parcela.Status.DESCONTADO,
                data_pagamento=date(2026, 1, 1),
            ),
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=2,
                referencia_mes=date(2026, 2, 1),
                valor=Decimal("50.00"),
                data_vencimento=date(2026, 2, 1),
                status=Parcela.Status.DESCONTADO,
                data_pagamento=date(2026, 2, 1),
            ),
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=3,
                referencia_mes=date(2026, 3, 1),
                valor=Decimal("50.00"),
                data_vencimento=date(2026, 3, 1),
                status=Parcela.Status.NAO_DESCONTADO,
            ),
        ]
        self._create_small_value_return_item(
            contrato,
            referencia=date(2026, 1, 1),
            valor="50.00",
            parcela=parcelas[0],
        )

        projection = build_contract_cycle_projection(contrato)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertEqual(cycles[0]["status"], Ciclo.Status.PENDENCIA)
        self.assertEqual(projection["status_renovacao"], "")

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
            [date(2025, 10, 1), date(2025, 12, 1)],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in sorted(
                    projection["unpaid_months"],
                    key=lambda item: item["referencia_mes"],
                )
            ],
            [
                (date(2025, 11, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2026, 1, 1), Parcela.Status.NAO_DESCONTADO),
            ],
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
            [date(2025, 10, 1), date(2025, 12, 1)],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in sorted(
                    projection["unpaid_months"],
                    key=lambda item: item["referencia_mes"],
                )
            ],
            [
                (date(2025, 11, 1), "quitada"),
                (date(2026, 1, 1), Parcela.Status.NAO_DESCONTADO),
            ],
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
            [date(2025, 12, 1), date(2026, 1, 1)],
        )
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[1]["parcelas"]],
            [date(2026, 3, 1), date(2026, 4, 1)],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in sorted(
                    projection["unpaid_months"],
                    key=lambda item: item["referencia_mes"],
                )
            ],
            [
                (date(2025, 10, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2025, 11, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2026, 2, 1), Parcela.Status.NAO_DESCONTADO),
            ],
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
            [date(2025, 10, 1), date(2025, 12, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycle["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )
        self.assertEqual(
            [
                (item["referencia_mes"], item["status"])
                for item in projection["unpaid_months"]
            ],
            [
                (date(2026, 1, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2025, 11, 1), "quitada"),
            ],
        )
        self.assertTrue(projection["possui_meses_nao_descontados"])
        self.assertEqual(projection["meses_nao_descontados_count"], 1)
        self.assertEqual(projection["movimentos_financeiros_avulsos"], [])

    def test_canceled_payment_row_is_ignored_by_projection(self):
        associado = self._create_associado("11199922235", "Pagamento Cancelado")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2026, 2, 1),
        )
        self._create_financial_row(contrato, date(2026, 2, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 3, 1), status_code="1")
        self._create_financial_row(
            contrato,
            date(2026, 4, 1),
            status_code="1",
            manual_status=PagamentoMensalidade.ManualStatus.CANCELADO,
        )

        projection = build_contract_cycle_projection(contrato)
        cycle = sorted(projection["cycles"], key=lambda item: item["numero"])[0]

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycle["parcelas"]],
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in cycle["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.EM_PREVISAO,
            ],
        )
        self.assertFalse(projection["possui_meses_nao_descontados"])
        self.assertEqual(projection["meses_nao_descontados_count"], 0)

    def test_manual_layout_regularized_row_does_not_count_as_overdue(self):
        associado = self._create_associado("11199922234", "Manual Regularizado")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])

        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("600.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 1, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 1, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.EM_PREVISAO,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=3,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            layout_bucket=Parcela.LayoutBucket.UNPAID,
            data_pagamento=date(2026, 2, 5),
            observacao="Regularizada fora do ciclo manual.",
        )

        projection = build_contract_cycle_projection(contrato)

        self.assertEqual(len(projection["unpaid_months"]), 1)
        self.assertEqual(
            projection["unpaid_months"][0]["referencia_mes"],
            date(2026, 2, 1),
        )
        self.assertEqual(
            projection["unpaid_months"][0]["status"],
            Parcela.Status.DESCONTADO,
        )
        self.assertFalse(projection["possui_meses_nao_descontados"])
        self.assertEqual(projection["meses_nao_descontados_count"], 0)
        self.assertEqual(
            projection["cycles"][0]["situacao_financeira"],
            "ciclo_em_dia",
        )

    def test_manual_layout_closed_cycle_is_rendered_as_concluded(self):
        associado = self._create_associado("11199922235", "Manual Concluido")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2026, 1, 1),
        )
        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])

        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.FECHADO,
            valor_total=Decimal("900.00"),
        )
        for index, referencia in enumerate(
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=index,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )

        projection = build_contract_cycle_projection(contrato)
        cycle = projection["cycles"][0]

        self.assertEqual(cycle["status"], Ciclo.Status.FECHADO)
        self.assertEqual(cycle["status_visual_label"], "Concluído")
        self.assertEqual(cycle["fase_ciclo"], "ciclo_renovado")
        self.assertEqual(
            get_contract_visual_status_payload(contrato, projection=projection)[
                "status_visual_label"
            ],
            "Concluído",
        )

    def test_manual_projection_moves_non_counting_rows_outside_cycle_and_keeps_documents(self):
        associado = self._create_associado("11199922236", "Manual Docs Fora Do Ciclo")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
            valor_mensalidade="350.00",
        )
        contrato.admin_manual_layout_enabled = True
        contrato.save(update_fields=["admin_manual_layout_enabled", "updated_at"])

        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.CICLO_RENOVADO,
            valor_total=Decimal("1050.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 11, 1),
            status=Parcela.Status.NAO_DESCONTADO,
            observacao="Competência não quitada no retorno.",
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("350.00"),
            data_vencimento=date(2025, 12, 1),
            status="quitada",
            data_pagamento=date(2026, 1, 12),
            observacao="Competência quitada manualmente fora do ciclo.",
        )

        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("1050.00"),
        )
        for numero, referencia in enumerate(
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo_2,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("350.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )

        refinanciamento = Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2026-01|2026-02|2026-03",
            ref1=date(2026, 1, 1),
            ref2=date(2026, 2, 1),
            ref3=date(2026, 3, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=ciclo_2,
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.OPERACIONAL,
            arquivo=SimpleUploadedFile("termo.pdf", b"termo", content_type="application/pdf"),
            nome_original="termo.pdf",
            origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            enviado_por=self.agente,
        )
        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=ciclo_2,
            tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            papel=Comprovante.Papel.AGENTE,
            arquivo=SimpleUploadedFile(
                "comprovante-agente.pdf",
                b"comprovante",
                content_type="application/pdf",
            ),
            nome_original="comprovante-agente.pdf",
            origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
            enviado_por=self.agente,
        )

        projection = build_contract_cycle_projection(contrato, include_documents=True)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        unpaid_rows = sorted(
            projection["unpaid_months"],
            key=lambda item: item["referencia_mes"],
        )

        self.assertEqual(
            [parcela["referencia_mes"] for parcela in cycles[0]["parcelas"]],
            [date(2025, 10, 1)],
        )
        self.assertEqual(
            [(item["referencia_mes"], item["status"]) for item in unpaid_rows],
            [
                (date(2025, 11, 1), Parcela.Status.NAO_DESCONTADO),
                (date(2025, 12, 1), "quitada"),
            ],
        )
        self.assertTrue(projection["possui_meses_nao_descontados"])
        self.assertEqual(projection["meses_nao_descontados_count"], 1)
        self.assertEqual(
            [parcela["numero"] for parcela in cycles[1]["parcelas"]],
            [1, 2, 3],
        )
        self.assertEqual(len(cycles[1]["comprovantes_ciclo"]), 1)
        self.assertEqual(
            cycles[1]["comprovantes_ciclo"][0]["tipo"],
            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
        )
        self.assertIsNotNone(cycles[1]["termo_antecipacao"])

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

    def test_synthesized_current_term_payload_is_not_marked_as_legacy(self):
        associado = self._create_associado("10120230344", "TERMO CORRENTE")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.OPERACIONAL,
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
            termo_antecipacao_path="refinanciamentos/renovacoes/termo-corrente.pdf",
            termo_antecipacao_original_name="termo-corrente.pdf",
        )

        projection = build_contract_cycle_projection(contrato, include_documents=True)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])

        self.assertIsNotNone(cycles[1]["termo_antecipacao"])
        self.assertEqual(
            cycles[1]["termo_antecipacao"]["origem"],
            Comprovante.Origem.SOLICITACAO_RENOVACAO,
        )
        self.assertEqual(
            cycles[1]["termo_antecipacao"]["tipo_referencia"],
            "referencia_path",
        )

    def test_term_comprovante_falls_back_to_local_file_when_legacy_reference_is_stale(self):
        associado = self._create_associado("90120230344", "TERMO COM FALLBACK")
        contrato = self._create_contrato(
            associado=associado,
            data_primeira_mensalidade=date(2025, 10, 1),
        )
        self._create_financial_row(contrato, date(2025, 10, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 11, 1), status_code="1")
        self._create_financial_row(contrato, date(2025, 12, 1), status_code="1")
        self._create_financial_row(contrato, date(2026, 1, 1), status_code="1")

        refinanciamento = Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.OPERACIONAL,
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
        comprovante = Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=contrato.ciclos.order_by("numero").last(),
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.OPERACIONAL,
            arquivo=SimpleUploadedFile(
                "termo-fallback.pdf",
                b"termo-fallback",
                content_type="application/pdf",
            ),
            nome_original="termo-fallback.pdf",
            origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            enviado_por=self.agente,
        )
        comprovante.arquivo_referencia_path = "ANTECIPACAO-TERMO-FALLBACK.pdf"
        comprovante.save(update_fields=["arquivo_referencia_path"])

        projection = build_contract_cycle_projection(contrato, include_documents=True)
        cycles = sorted(projection["cycles"], key=lambda item: item["numero"])
        termo = cycles[1]["termo_antecipacao"]

        self.assertIsNotNone(termo)
        self.assertTrue(termo["arquivo_disponivel_localmente"])
        self.assertEqual(termo["tipo_referencia"], "local")
        self.assertIn("termo-fallback.pdf", termo["arquivo_referencia"])
