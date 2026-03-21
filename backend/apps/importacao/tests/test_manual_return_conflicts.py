from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela

from .base import ImportacaoBaseTestCase
from ..models import ArquivoRetornoItem, PagamentoMensalidade


class RepairManualReturnConflictsCommandTestCase(ImportacaoBaseTestCase):
    def _build_conflict_case(self, *, status_codigo: str = "1") -> tuple[Associado, Contrato]:
        associado = Associado.objects.create(
            nome_completo="ACACIO LUSTOSA DANTAS",
            cpf_cnpj="77852621368",
            email="acacio@teste.local",
            telefone="86999999999",
            orgao_publico="SECRETARIA DA EDUCACAO",
            matricula_orgao="362602-4",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            codigo="CTR-TESTE-ACACIO",
            valor_bruto=Decimal("300.00"),
            valor_liquido=Decimal("210.00"),
            valor_mensalidade=Decimal("100.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("210.00"),
            valor_total_antecipacao=Decimal("300.00"),
            comissao_agente=Decimal("21.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 11, 25),
            data_aprovacao=date(2025, 11, 25),
            data_primeira_mensalidade=date(2026, 1, 7),
            mes_averbacao=date(2025, 12, 1),
            auxilio_liberado_em=date(2025, 11, 25),
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-dez",
            referencia_month=date(2025, 12, 1),
            status_code="1",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/dezembro.txt",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="import-jan",
            referencia_month=date(2026, 1, 1),
            status_code="1",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/janeiro.txt",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="manual-fev",
            referencia_month=date(2026, 2, 1),
            status_code="M",
            matricula="362602-4",
            orgao_pagto="918",
            nome_relatorio="ACACIO LUSTOSA DANTAS",
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime(2026, 2, 5, 0, 0, 0)),
            recebido_manual=Decimal("100.00"),
            source_file_path="legacy/pagamentos_mensalidades",
        )
        with patch("apps.contratos.cycle_projection.timezone.localdate", return_value=date(2026, 3, 21)):
            rebuild_contract_cycle_state(contrato, execute=True)

        arquivo = self.create_arquivo_retorno(nome="retorno_fev_acacio.txt")
        arquivo.competencia = date(2026, 2, 1)
        arquivo.resultado_resumo = {"competencia": "02/2026"}
        arquivo.save(update_fields=["competencia", "resultado_resumo", "updated_at"])
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=710,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="362602-4",
            nome_servidor="ACACIO LUSTOSA DANTAS",
            cargo="-SEM PLANO",
            competencia="02/2026",
            valor_descontado=Decimal("100.00"),
            status_codigo=status_codigo,
            status_desconto=(
                ArquivoRetornoItem.StatusDesconto.EFETIVADO
                if status_codigo == "1"
                else ArquivoRetornoItem.StatusDesconto.REJEITADO
            ),
            status_descricao="Lançado e Efetivado" if status_codigo == "1" else "Não lançado",
            motivo_rejeicao=None if status_codigo == "1" else "Não lançado",
            orgao_codigo="6580",
            orgao_pagto_codigo="918",
            orgao_pagto_nome="SECRETARIA DA EDUCACAO",
            associado=associado,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.CICLO_ABERTO,
            observacao="Nenhuma parcela elegível foi encontrada para a competência.",
        )
        return associado, contrato

    def test_command_repairs_effective_conflict_and_reprocesses_item(self):
        associado, contrato = self._build_conflict_case(status_codigo="1")
        stdout = StringIO()

        with (
            patch("apps.contratos.cycle_projection.timezone.localdate", return_value=date(2026, 3, 21)),
            patch("apps.importacao.reconciliacao.timezone.localdate", return_value=date(2026, 3, 21)),
        ):
            call_command(
                "repair_manual_return_conflicts",
                "--competencia",
                "2026-02",
                "--execute",
                stdout=stdout,
            )

        pagamento = PagamentoMensalidade.objects.get(
            cpf_cnpj=associado.cpf_cnpj,
            referencia_month=date(2026, 2, 1),
        )
        item = ArquivoRetornoItem.objects.get(cpf_cnpj=associado.cpf_cnpj, competencia="02/2026")
        contrato.refresh_from_db()

        self.assertEqual(pagamento.status_code, "1")
        self.assertIsNone(pagamento.manual_status)
        self.assertIsNone(pagamento.manual_paid_at)
        self.assertEqual(
            item.resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )
        self.assertIsNotNone(item.parcela_id)
        self.assertEqual(item.parcela.referencia_mes, date(2026, 2, 1))
        self.assertEqual(contrato.ciclos.count(), 1)
        self.assertEqual(
            list(
                Parcela.objects.filter(ciclo__contrato=contrato)
                .order_by("ciclo__numero", "numero")
                .values_list("referencia_mes", flat=True)
            ),
            [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)],
        )
        self.assertIn("convertidos: 1", stdout.getvalue())

    def test_command_keeps_manual_conflict_when_return_is_rejected(self):
        associado, _ = self._build_conflict_case(status_codigo="2")

        with patch("apps.contratos.cycle_projection.timezone.localdate", return_value=date(2026, 3, 21)):
            call_command(
                "repair_manual_return_conflicts",
                "--competencia",
                "2026-02",
                "--execute",
                stdout=StringIO(),
            )

        pagamento = PagamentoMensalidade.objects.get(
            cpf_cnpj=associado.cpf_cnpj,
            referencia_month=date(2026, 2, 1),
        )
        item = ArquivoRetornoItem.objects.get(cpf_cnpj=associado.cpf_cnpj, competencia="02/2026")

        self.assertEqual(pagamento.status_code, "M")
        self.assertEqual(pagamento.manual_status, PagamentoMensalidade.ManualStatus.PAGO)
        self.assertEqual(
            item.resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.CICLO_ABERTO,
        )
