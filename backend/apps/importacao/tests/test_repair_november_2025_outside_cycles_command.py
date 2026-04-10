from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade

from .base import ImportacaoBaseTestCase


class RepairNovember2025OutsideCyclesCommandTestCase(ImportacaoBaseTestCase):
    def _run_command(self, *args: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            call_command(
                "repair_november_2025_outside_cycles",
                *args,
                "--report-json",
                str(report_path),
            )
            return json.loads(report_path.read_text(encoding="utf-8"))

    def _create_contract(
        self,
        *,
        cpf: str,
        codigo: str,
        november_status: str,
    ) -> tuple[Associado, Contrato]:
        associado = Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=codigo,
            valor_bruto=Decimal("400.00"),
            valor_liquido=Decimal("300.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=4,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("400.00"),
            comissao_agente=Decimal("30.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 10, 1),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 5),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 11, 1),
            status=november_status,
            data_pagamento=date(2025, 11, 5) if november_status == Parcela.Status.DESCONTADO else None,
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2025, 12, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 12, 5),
        )
        return associado, contrato

    def _create_return_context(self, *associados: Associado) -> ArquivoRetorno:
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-novembro.txt",
            arquivo_url="retornos/retorno-novembro.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=date(2025, 11, 1),
            total_registros=len(associados),
            processados=len(associados),
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=self.admin,
            processado_em=timezone.now(),
            resultado_resumo={"financeiro": {"ok": 999, "recebido": "999.99"}},
        )
        for line, associado in enumerate(associados, start=1):
            ArquivoRetornoItem.objects.create(
                arquivo_retorno=arquivo,
                linha_numero=line,
                cpf_cnpj=associado.cpf_cnpj,
                matricula_servidor=associado.matricula_orgao,
                nome_servidor=associado.nome_completo,
                competencia="11/2025",
                valor_descontado=Decimal("300.00"),
                status_codigo="2",
                status_descricao="Não Lançado por Falta de Margem Temporariamente",
                associado=associado,
                resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
            )
        return arquivo

    def test_apply_clears_invalid_november_manual_mass_payment_and_rebuilds_cycles(self):
        associado_invalido, contrato_invalido = self._create_contract(
            cpf="70000000031",
            codigo="CTR-NOV-INVALIDO",
            november_status=Parcela.Status.DESCONTADO,
        )
        associado_valido, contrato_valido = self._create_contract(
            cpf="70000000032",
            codigo="CTR-NOV-VALIDO",
            november_status=Parcela.Status.DESCONTADO,
        )
        arquivo = self._create_return_context(associado_invalido, associado_valido)

        PagamentoMensalidade.objects.create(
            created_by=self.admin,
            import_uuid="nov-invalid",
            referencia_month=date(2025, 11, 1),
            status_code="2",
            matricula=associado_invalido.matricula_orgao,
            orgao_pagto="SEDUC",
            nome_relatorio=associado_invalido.nome_completo,
            cpf_cnpj=associado_invalido.cpf_cnpj,
            associado=associado_invalido,
            valor=Decimal("300.00"),
            recebido_manual=Decimal("300.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime.combine(date(2025, 11, 1), time(12, 0))),
            manual_forma_pagamento="conciliacao_maristela_fora_ciclo",
            manual_by=self.tesoureiro,
            source_file_path="planilhas/maristela.xlsx",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.admin,
            import_uuid="nov-valid",
            referencia_month=date(2025, 11, 1),
            status_code="2",
            matricula=associado_valido.matricula_orgao,
            orgao_pagto="SEDUC",
            nome_relatorio=associado_valido.nome_completo,
            cpf_cnpj=associado_valido.cpf_cnpj,
            associado=associado_valido,
            valor=Decimal("300.00"),
            recebido_manual=Decimal("300.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(datetime.combine(date(2025, 12, 18), time(12, 0))),
            manual_forma_pagamento="pix 18/12/2025",
            source_file_path="planilhas/baixas-pix.xlsx",
        )

        payload = self._run_command("--apply")

        invalid_payment = PagamentoMensalidade.objects.get(import_uuid="nov-invalid")
        valid_payment = PagamentoMensalidade.objects.get(import_uuid="nov-valid")
        projection_invalid = build_contract_cycle_projection(contrato_invalido)
        projection_valid = build_contract_cycle_projection(contrato_valido)
        arquivo.refresh_from_db()

        self.assertEqual(payload["pagamentos_invalidos_limpos"], 1)
        self.assertEqual(payload["pagamentos_validos_mantidos"], 1)
        self.assertEqual(payload["financeiro_ok_total"], 1)
        self.assertEqual(payload["financeiro_recebido_total"], "300.00")

        self.assertIsNone(invalid_payment.manual_status)
        self.assertIsNone(invalid_payment.recebido_manual)
        self.assertIsNone(invalid_payment.manual_paid_at)
        self.assertEqual(invalid_payment.manual_forma_pagamento, "")
        self.assertIsNone(invalid_payment.manual_by_id)

        self.assertEqual(valid_payment.manual_status, PagamentoMensalidade.ManualStatus.PAGO)
        self.assertEqual(valid_payment.recebido_manual, Decimal("300.00"))

        self.assertFalse(
            any(
                parcela["referencia_mes"] == date(2025, 11, 1)
                for ciclo in projection_invalid["cycles"]
                for parcela in ciclo["parcelas"]
            )
        )
        self.assertTrue(
            any(
                row["referencia_mes"] == date(2025, 11, 1)
                and row["status"] == Parcela.Status.NAO_DESCONTADO
                for row in projection_invalid["unpaid_months"]
            )
        )
        self.assertFalse(
            any(
                parcela["referencia_mes"] == date(2025, 11, 1)
                for ciclo in projection_valid["cycles"]
                for parcela in ciclo["parcelas"]
            )
        )
        self.assertTrue(
            any(
                row["referencia_mes"] == date(2025, 11, 1)
                and row["status"] == "quitada"
                for row in projection_valid["unpaid_months"]
            )
        )
        self.assertEqual(arquivo.resultado_resumo["financeiro"]["ok"], 1)
        self.assertEqual(arquivo.resultado_resumo["financeiro"]["recebido"], "300.00")
