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


class RevertDiscountedReferenceToForecastCommandTestCase(ImportacaoBaseTestCase):
    def _create_april_case(
        self,
        *,
        cpf: str,
    ) -> tuple[Associado, Contrato, Parcela]:
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
            codigo=f"CTR-APR-{cpf[-4:]}",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("900.00"),
            valor_total_antecipacao=Decimal("900.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 2, 1),
            data_aprovacao=date(2026, 2, 1),
            data_primeira_mensalidade=date(2026, 2, 1),
            auxilio_liberado_em=date(2026, 1, 25),
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
        Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("300.00"),
            data_vencimento=date(2026, 3, 5),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 3, 5),
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
        pagamento_abril = PagamentoMensalidade.objects.create(
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

        baixa = BaixaManual.objects.create(
            parcela=parcela_abril,
            realizado_por=self.tesoureiro,
            comprovante=SimpleUploadedFile(
                "abril.pdf",
                b"pdf",
                content_type="application/pdf",
            ),
            nome_comprovante="abril.pdf",
            observacao="Baixa manual em abril.",
            valor_pago=Decimal("300.00"),
            data_baixa=date(2026, 4, 6),
        )
        arquivo = self.create_arquivo_retorno(nome=f"retorno_{cpf}_abril.txt")
        arquivo.competencia = date(2026, 4, 1)
        arquivo.save(update_fields=["competencia", "updated_at"])
        item = ArquivoRetornoItem.objects.create(
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
            gerou_encerramento=True,
            gerou_novo_ciclo=True,
        )

        return associado, contrato, parcela_abril, pagamento_abril, baixa, item

    def _run_command(self, *args: str) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            call_command(
                "revert_discounted_reference_to_forecast",
                *args,
                "--report-json",
                str(report_path),
            )
            return json.loads(report_path.read_text(encoding="utf-8"))

    def test_command_dry_run_detects_revertible_april_case(self):
        associado, contrato, _parcela_abril, _pagamento_abril, _baixa, _item = self._create_april_case(
            cpf="71000000021",
        )

        with mock.patch(
            "apps.contratos.cycle_projection.timezone.localdate",
            return_value=date(2026, 4, 3),
        ):
            projection_before = build_contract_cycle_projection(contrato)
            payload = self._run_command("--dry-run", "--cpf", associado.cpf_cnpj)

        self.assertEqual(payload["summary"]["repairable"], 1)
        self.assertEqual(payload["summary"]["reverted"], 0)
        self.assertEqual(payload["results"][0]["classification"], "repairable")
        self.assertEqual(
            payload["results"][0]["changes"]["target_parcela"]["status"],
            Parcela.Status.DESCONTADO,
        )
        self.assertEqual(
            payload["results"][0]["projection_before"]["target_ref_in_projection"],
            any(
                parcela["referencia_mes"] == date(2026, 4, 1)
                for ciclo in projection_before["cycles"]
                for parcela in ciclo["parcelas"]
            ),
        )

    def test_command_execute_reverts_april_evidences_and_returns_reference_to_forecast(self):
        associado, contrato, parcela_abril, pagamento_abril, baixa, item = self._create_april_case(
            cpf="71000000022",
        )

        with mock.patch(
            "apps.contratos.cycle_projection.timezone.localdate",
            return_value=date(2026, 4, 3),
        ):
            self.assertEqual(parcela_abril.status, Parcela.Status.DESCONTADO)

            payload = self._run_command(
                "--execute",
                "--cpf",
                associado.cpf_cnpj,
                "--target-ref",
                "2026-04",
            )

            parcela_abril.refresh_from_db()
            pagamento_abril.refresh_from_db()
            item.refresh_from_db()
            projection_after = build_contract_cycle_projection(contrato)

        baixa.refresh_from_db()
        self.assertEqual(payload["summary"]["reverted"], 1)
        self.assertEqual(payload["results"][0]["classification"], "reverted_to_forecast")
        self.assertEqual(
            pagamento_abril.manual_status,
            PagamentoMensalidade.ManualStatus.CANCELADO,
        )
        self.assertEqual(item.status_desconto, ArquivoRetornoItem.StatusDesconto.CANCELADO)
        self.assertEqual(
            item.resultado_processamento,
            ArquivoRetornoItem.ResultadoProcessamento.ERRO,
        )
        self.assertFalse(item.gerou_encerramento)
        self.assertFalse(item.gerou_novo_ciclo)
        self.assertIsNone(item.parcela_id)
        self.assertIsNotNone(baixa.deleted_at)
        self.assertEqual(parcela_abril.status, Parcela.Status.EM_PREVISAO)
        self.assertIsNone(parcela_abril.data_pagamento)
        self.assertEqual(
            [parcela["referencia_mes"] for parcela in projection_after["cycles"][0]["parcelas"]],
            [date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
        )
        self.assertEqual(
            [parcela["status"] for parcela in projection_after["cycles"][0]["parcelas"]],
            [
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.EM_PREVISAO,
            ],
        )
        self.assertFalse(payload["results"][0]["projection_after"]["target_ref_counts_as_paid"])
        if payload["results"][0]["projection_after"]["target_ref_in_projection"]:
            self.assertEqual(
                payload["results"][0]["projection_after"]["target_ref_status"],
                Parcela.Status.EM_PREVISAO,
            )
