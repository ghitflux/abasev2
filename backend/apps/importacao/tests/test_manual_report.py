from __future__ import annotations

import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.audit import build_return_consistency_report
from apps.importacao.manual_report import ManualReturnReport, ManualReturnRow, parse_manual_report_text
from apps.importacao.manual_return_service import ManualReturnReportService
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade

from .base import ImportacaoBaseTestCase


def _build_legacy_dump(path: Path, *, competencia: date, cpf: str, manual_paid_at: str) -> None:
    path.write_text(
        f"""
        INSERT INTO `pagamentos_mensalidades`
        (`id`, `referencia_month`, `cpf_cnpj`, `esperado_manual`, `recebido_manual`,
         `manual_status`, `status_code`, `agente_refi_solicitado`, `manual_paid_at`,
         `manual_forma_pagamento`, `manual_comprovante_path`, `created_at`, `updated_at`)
        VALUES
        (1, '{competencia.isoformat()}', '{cpf}', 300.00, 300.00, 'pago', 'M', 0,
         '{manual_paid_at}', 'pix', NULL, '{manual_paid_at}', '{manual_paid_at}');
        """,
        encoding="utf-8",
    )


class ManualReturnReportTestCase(ImportacaoBaseTestCase):
    def test_parse_manual_report_text(self):
        report = parse_manual_report_text(
            """
            Baixa do Mês março de 2026
            Gerado em: 16/03/2026 10:12
            ID Nome CPF Esperado Recebido Situação Status Data
            0001 JOSE DA SILVA 12345678901 R$ 300,00 R$ 300,00 PAGO O 2026-03-15 12:40:00
            Totais: Esperado: R$ 300,00 | Recebido: R$ 300,00 | OK: 1 | Total: 1
            """
        )

        self.assertEqual(report.competencia, date(2026, 3, 1))
        self.assertEqual(report.generated_at, datetime(2026, 3, 16, 10, 12))
        self.assertEqual(report.esperado_total, Decimal("300.00"))
        self.assertEqual(report.recebido_total, Decimal("300.00"))
        self.assertEqual(report.ok_total, 1)
        self.assertEqual(report.total, 1)
        self.assertEqual(report.rows[0].cpf_cnpj, "12345678901")

    def test_audit_return_consistency_classifies_timezone_only_manual_paid_at(self):
        competencia = date(2026, 3, 1)
        pagamento = PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="test-import",
            referencia_month=competencia,
            status_code="M",
            matricula="M-100",
            orgao_pagto="ORG",
            nome_relatorio="JOSE DA SILVA",
            cpf_cnpj="12345678901",
            valor=Decimal("300.00"),
            esperado_manual=Decimal("300.00"),
            recebido_manual=Decimal("300.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(
                datetime(2026, 3, 15, 12, 40),
                timezone.get_current_timezone(),
            ),
            manual_forma_pagamento="pix",
        )
        pagamento.refresh_from_db()

        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = Path(temp_dir) / "legacy.sql"
            _build_legacy_dump(
                dump_path,
                competencia=competencia,
                cpf="12345678901",
                manual_paid_at="2026-03-15 12:40:00",
            )
            report = build_return_consistency_report(
                dump_path=dump_path,
                competencia=competencia,
                cpf="12345678901",
            )

        self.assertEqual(report["summary"]["timezone_only_paid_at_total"], 1)
        self.assertEqual(report["summary"]["real_mismatch_total"], 0)
        self.assertEqual(report["summary"]["status"], "ok")

    def test_audit_return_consistency_treats_manual_promoted_to_return_as_reconciled(self):
        competencia = date(2026, 3, 1)
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="test-import",
            referencia_month=competencia,
            status_code="1",
            matricula="M-100",
            orgao_pagto="ORG",
            nome_relatorio="JOSE DA SILVA",
            cpf_cnpj="12345678901",
            valor=Decimal("300.00"),
            source_file_path="arquivos_retorno/retorno-marco.txt",
        )
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno-marco.txt",
            arquivo_url="arquivos_retorno/retorno-marco.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI",
            competencia=competencia,
            uploaded_by=self.tesoureiro,
            status=ArquivoRetorno.Status.CONCLUIDO,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj="12345678901",
            matricula_servidor="M-100",
            nome_servidor="JOSE DA SILVA",
            cargo="-SEM PLANO",
            competencia="03/2026",
            valor_descontado=Decimal("300.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="1",
            orgao_pagto_codigo="1",
            orgao_pagto_nome="ORG",
            processado=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            dump_path = Path(temp_dir) / "legacy.sql"
            _build_legacy_dump(
                dump_path,
                competencia=competencia,
                cpf="12345678901",
                manual_paid_at="2026-03-15 12:40:00",
            )
            report = build_return_consistency_report(
                dump_path=dump_path,
                competencia=competencia,
                cpf="12345678901",
            )

        self.assertEqual(report["summary"]["manual_promoted_to_return_total"], 1)
        self.assertEqual(report["summary"]["real_mismatch_total"], 0)
        self.assertEqual(report["summary"]["status"], "ok")

    @patch("apps.importacao.manual_return_service.parse_manual_report_pdf")
    def test_manual_return_service_creates_synthetic_manual_file(self, parse_report_mock):
        competencia = date(2026, 3, 1)
        associado = Associado.objects.create(
            nome_completo="JOSE DA SILVA",
            cpf_cnpj="12345678901",
            email="12345678901@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-123",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 10),
            data_aprovacao=date(2026, 1, 10),
            data_primeira_mensalidade=competencia,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=competencia,
            data_fim=date(2026, 5, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        parcela = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=competencia,
            valor=Decimal("300.00"),
            data_vencimento=competencia,
            status=Parcela.Status.EM_ABERTO,
        )
        pagamento = PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="manual-import",
            referencia_month=competencia,
            status_code="",
            matricula="MAT-123",
            orgao_pagto="ORG",
            nome_relatorio="JOSE DA SILVA",
            cpf_cnpj="12345678901",
            associado=associado,
            valor=Decimal("300.00"),
            esperado_manual=Decimal("300.00"),
            recebido_manual=Decimal("300.00"),
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
            manual_paid_at=timezone.make_aware(
                datetime(2026, 3, 15, 12, 40),
                timezone.get_current_timezone(),
            ),
            manual_forma_pagamento="pix",
        )

        parse_report_mock.return_value = ManualReturnReport(
            competencia=competencia,
            generated_at=datetime(2026, 3, 16, 10, 12),
            esperado_total=Decimal("300.00"),
            recebido_total=Decimal("300.00"),
            ok_total=1,
            total=1,
            rows=[
                ManualReturnRow(
                    legacy_id=1,
                    nome="JOSE DA SILVA",
                    cpf_cnpj="12345678901",
                    esperado=Decimal("300.00"),
                    recebido=Decimal("300.00"),
                    situacao="PAGO",
                    status="O",
                    paid_at=datetime(2026, 3, 15, 12, 40),
                )
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "mes_retorno_ref_2026-03.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 manual report test")
            dump_path = Path(temp_dir) / "legacy.sql"
            _build_legacy_dump(
                dump_path,
                competencia=competencia,
                cpf="12345678901",
                manual_paid_at="2026-03-15 12:40:00",
            )

            result, report = ManualReturnReportService().create_or_update_from_pdf(
                pdf_path=pdf_path,
                dump_path=dump_path,
                uploaded_by=self.tesoureiro,
                expected_competencia=competencia,
                execute=True,
            )

        self.assertEqual(report.total, 1)
        self.assertEqual(result.arquivo_id, ArquivoRetorno.objects.get().id)
        self.assertEqual(result.matched_pagamentos, 1)
        self.assertEqual(result.matched_parcelas, 1)

        arquivo = ArquivoRetorno.objects.get()
        self.assertEqual(arquivo.formato, ArquivoRetorno.Formato.MANUAL)
        self.assertEqual(arquivo.competencia, competencia)
        self.assertEqual(
            arquivo.resultado_resumo["origem_processamento"],
            "manual_relatorio",
        )

        item = ArquivoRetornoItem.objects.get()
        self.assertEqual(item.parcela_id, parcela.id)
        self.assertEqual(item.associado_id, associado.id)
        self.assertEqual(
            item.resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )
        self.assertEqual(item.payload_bruto["origem_baixa"], "manual_relatorio")
        self.assertEqual(item.payload_bruto["legacy_payment_id"], 1)
        self.assertEqual(item.payload_bruto["recebido_manual"], "300.00")
        self.assertTrue(arquivo.arquivo_url.endswith(".pdf"))
        self.assertEqual(pagamento.referencia_month, competencia)
