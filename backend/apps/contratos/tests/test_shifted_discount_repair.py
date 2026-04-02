from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.importacao.tests.base import ImportacaoBaseTestCase
from apps.tesouraria.models import BaixaManual


class RepairShiftedDiscountReferencesCommandTestCase(ImportacaoBaseTestCase):
    def _create_shifted_case(
        self,
        *,
        cpf: str,
        with_payment: bool = True,
        with_baixa: bool = False,
        with_return_item: bool = False,
        with_competing_correct_payment: bool = False,
    ) -> tuple[Associado, Contrato, Parcela, Parcela]:
        associado = Associado.objects.create(
            nome_completo=f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            codigo=f"CTR-SHIFT-{cpf[-4:]}",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 2, 1),
            data_aprovacao=date(2026, 1, 20),
            data_primeira_mensalidade=date(2026, 2, 1),
            auxilio_liberado_em=date(2026, 1, 20),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 2, 1),
            data_fim=date(2026, 4, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 2, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )
        parcela_marco = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.EM_PREVISAO,
        )
        parcela_abril = Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=3,
            referencia_mes=date(2026, 4, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 4, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 4, 5),
        )

        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid=f"{cpf}-2026-02-1",
            referencia_month=date(2026, 2, 1),
            status_code="1",
            matricula=associado.matricula_orgao,
            orgao_pagto="SEDUC",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("300.00"),
            source_file_path="retornos/2026-02.txt",
        )
        if with_payment:
            PagamentoMensalidade.objects.create(
                created_by=self.tesoureiro,
                import_uuid=f"{cpf}-2026-04-1",
                referencia_month=date(2026, 4, 1),
                status_code="1",
                matricula=associado.matricula_orgao,
                orgao_pagto="SEDUC",
                nome_relatorio=associado.nome_completo,
                cpf_cnpj=associado.cpf_cnpj,
                associado=associado,
                valor=Decimal("300.00"),
                source_file_path="retornos/2026-04.txt",
            )
        if with_competing_correct_payment:
            PagamentoMensalidade.objects.create(
                created_by=self.tesoureiro,
                import_uuid=f"{cpf}-2026-03-1",
                referencia_month=date(2026, 3, 1),
                status_code="1",
                matricula=associado.matricula_orgao,
                orgao_pagto="SEDUC",
                nome_relatorio=associado.nome_completo,
                cpf_cnpj=associado.cpf_cnpj,
                associado=associado,
                valor=Decimal("300.00"),
                source_file_path="retornos/2026-03.txt",
            )

        if with_baixa:
            BaixaManual.objects.create(
                parcela=parcela_abril,
                realizado_por=self.tesoureiro,
                comprovante=SimpleUploadedFile(
                    "baixa-abril.pdf",
                    b"pdf",
                    content_type="application/pdf",
                ),
                nome_comprovante="baixa-abril.pdf",
                observacao="Baixa manual em referencia errada.",
                valor_pago=Decimal("300.00"),
                data_baixa=date(2026, 4, 6),
            )

        if with_return_item:
            arquivo = self.create_arquivo_retorno(nome=f"retorno_{cpf}_abril.txt")
            arquivo.competencia = date(2026, 4, 1)
            arquivo.save(update_fields=["competencia", "updated_at"])
            ArquivoRetornoItem.objects.create(
                arquivo_retorno=arquivo,
                linha_numero=1,
                cpf_cnpj=associado.cpf_cnpj,
                matricula_servidor=associado.matricula_orgao,
                nome_servidor=associado.nome_completo,
                cargo="SERVIDOR",
                competencia="04/2026",
                valor_descontado=Decimal("300.00"),
                status_codigo="1",
                status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
                status_descricao="Lançado e Efetivado",
                associado=associado,
                parcela=parcela_abril,
                processado=True,
                resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
            )

        return associado, contrato, parcela_marco, parcela_abril

    def _run_command(self, *args: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            call_command(
                "repair_shifted_discount_references",
                *args,
                "--report-json",
                str(report_path),
            )
            return json.loads(report_path.read_text(encoding="utf-8"))

    def test_command_execute_moves_imported_payment_and_return_item_to_correct_reference(self):
        associado, contrato, parcela_marco, parcela_abril = self._create_shifted_case(
            cpf="71000000010",
            with_payment=True,
            with_return_item=True,
        )

        with mock.patch(
            "apps.contratos.cycle_projection.timezone.localdate",
            return_value=date(2026, 4, 21),
        ):
            projection_before = build_contract_cycle_projection(contrato)
            self.assertEqual(projection_before["meses_nao_descontados_count"], 1)
            self.assertEqual(
                projection_before["unpaid_months"][0]["referencia_mes"],
                date(2026, 3, 1),
            )

            payload = self._run_command(
                "--execute",
                "--cpf",
                associado.cpf_cnpj,
                "--paid-ref",
                "2026-04",
                "--correct-ref",
                "2026-03",
            )

            parcela_marco.refresh_from_db()
            parcela_abril.refresh_from_db()
            item = ArquivoRetornoItem.objects.get(cpf_cnpj=associado.cpf_cnpj)
            projection_after = build_contract_cycle_projection(contrato)

        self.assertEqual(payload["summary"]["repaired"], 1)
        self.assertEqual(payload["results"][0]["classification"], "repaired")
        self.assertEqual(
            PagamentoMensalidade.objects.filter(
                associado=associado,
                referencia_month=date(2026, 4, 1),
            ).count(),
            0,
        )
        self.assertEqual(
            PagamentoMensalidade.objects.filter(
                associado=associado,
                referencia_month=date(2026, 3, 1),
                status_code="1",
            ).count(),
            1,
        )
        self.assertEqual(parcela_marco.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_marco.data_pagamento, date(2026, 4, 5))
        self.assertEqual(parcela_abril.status, Parcela.Status.EM_PREVISAO)
        self.assertIsNone(parcela_abril.data_pagamento)
        self.assertEqual(item.parcela_id, parcela_marco.id)
        self.assertEqual(item.competencia, "03/2026")
        self.assertEqual(projection_after["meses_nao_descontados_count"], 0)
        self.assertFalse(projection_after["possui_meses_nao_descontados"])

    def test_command_reassigns_baixa_manual_to_correct_reference(self):
        associado, contrato, parcela_marco, parcela_abril = self._create_shifted_case(
            cpf="71000000011",
            with_payment=False,
            with_baixa=True,
        )

        with mock.patch(
            "apps.contratos.cycle_projection.timezone.localdate",
            return_value=date(2026, 4, 21),
        ):
            payload = self._run_command(
                "--execute",
                "--cpf",
                associado.cpf_cnpj,
                "--paid-ref",
                "2026-04",
                "--correct-ref",
                "2026-03",
            )

        baixa = BaixaManual.objects.get()
        parcela_marco.refresh_from_db()
        parcela_abril.refresh_from_db()
        self.assertEqual(payload["summary"]["repaired"], 1)
        self.assertEqual(baixa.parcela_id, parcela_marco.id)
        self.assertEqual(parcela_marco.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_marco.data_pagamento, date(2026, 4, 6))
        self.assertEqual(parcela_abril.status, Parcela.Status.EM_PREVISAO)
        self.assertIsNone(parcela_abril.data_pagamento)

    def test_command_reports_manual_review_when_correct_reference_already_has_payment(self):
        associado, _contrato, _parcela_marco, _parcela_abril = self._create_shifted_case(
            cpf="71000000012",
            with_payment=True,
            with_competing_correct_payment=True,
        )

        payload = self._run_command(
            "--dry-run",
            "--cpf",
            associado.cpf_cnpj,
            "--paid-ref",
            "2026-04",
            "--correct-ref",
            "2026-03",
        )

        self.assertEqual(payload["summary"]["manual_review"], 1)
        self.assertEqual(payload["results"][0]["classification"], "manual_review")
        self.assertIn(
            "correct_reference_already_has_financial_record",
            payload["results"][0]["reasons"],
        )
