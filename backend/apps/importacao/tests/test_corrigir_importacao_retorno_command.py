from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from apps.associados.models import Associado
from apps.contratos.models import Parcela

from .base import ImportacaoBaseTestCase
from ..financeiro import build_financeiro_resumo
from ..models import ArquivoRetorno, PagamentoMensalidade
from ..services import ArquivoRetornoService


class CorrigirImportacaoRetornoCommandTestCase(ImportacaoBaseTestCase):
    def test_apply_reprocessa_competencia_sem_alterar_ciclos(self):
        associado_ok, contrato_ok, _ = self.create_associado_com_contrato(
            cpf="23993596315",
            nome="Maria de Jesus Santana Costa",
        )
        associado_nao, contrato_nao, _ = self.create_associado_com_contrato(
            cpf="21819424391",
            nome="Francisco Crisostomo Batista",
        )
        associado_diff, contrato_diff, _ = self.create_associado_com_contrato(
            cpf="48204773315",
            nome="Maria de Jesus Araujo Goncalves",
        )

        pagamento_extra = PagamentoMensalidade.objects.create(
            created_by=self.coordenador,
            import_uuid="manual-extra",
            referencia_month=date(2025, 5, 1),
            status_code="1",
            matricula="EXTRA-1",
            orgao_pagto="EXTRA",
            nome_relatorio="PAGAMENTO EXTRA",
            cpf_cnpj="99999999999",
            valor=Decimal("77.00"),
            source_file_path="legacy/pagamentos_mensalidades",
        )

        arquivo = ArquivoRetornoService().upload(
            SimpleUploadedFile(
                "retorno_etipi_052025.txt",
                self.fixture_bytes(),
                content_type="text/plain",
            ),
            self.coordenador,
        )

        stdout = StringIO()
        call_command(
            "corrigir_importacao_retorno",
            "--competencia",
            "2025-05",
            "--arquivo-retorno-id",
            str(arquivo.id),
            "--apply",
            stdout=stdout,
        )

        arquivo.refresh_from_db()
        self.assertEqual(arquivo.status, ArquivoRetorno.Status.CONCLUIDO)
        self.assertEqual(arquivo.resultado_resumo["baixa_efetuada"], 2)
        self.assertEqual(arquivo.resultado_resumo["nao_descontado"], 2)
        self.assertEqual(arquivo.resultado_resumo["ciclo_aberto"], 0)

        pagamentos = PagamentoMensalidade.objects.filter(referencia_month=date(2025, 5, 1))
        self.assertEqual(pagamentos.count(), 5)
        self.assertEqual(
            dict(sorted(Counter(pagamentos.values_list("status_code", flat=True)).items())),
            {"1": 2, "2": 1, "3": 1, "4": 1},
        )
        pagamento_extra.refresh_from_db()
        self.assertIsNone(pagamento_extra.deleted_at)

        financeiro = build_financeiro_resumo(competencia=date(2025, 5, 1))
        self.assertEqual(financeiro["total"], 4)
        self.assertEqual(financeiro["ok"], 2)
        self.assertEqual(financeiro["faltando"], 2)

        associado_importado = Associado.objects.get(cpf_cnpj="18084974300")
        self.assertEqual(associado_importado.status, Associado.Status.INADIMPLENTE)
        self.assertEqual(associado_importado.ultimo_arquivo_retorno, arquivo.arquivo_nome)

        parcela_ok = Parcela.objects.get(associado=associado_ok, referencia_mes=date(2025, 5, 1))
        parcela_nao = Parcela.objects.get(associado=associado_nao, referencia_mes=date(2025, 5, 1))
        parcela_diff = Parcela.objects.get(associado=associado_diff, referencia_mes=date(2025, 5, 1))
        self.assertEqual(parcela_ok.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_nao.status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(parcela_diff.status, Parcela.Status.DESCONTADO)

        contrato_ok.refresh_from_db()
        contrato_nao.refresh_from_db()
        contrato_diff.refresh_from_db()
        self.assertEqual(contrato_ok.ciclos.count(), 1)
        self.assertEqual(contrato_nao.ciclos.count(), 1)
        self.assertEqual(contrato_diff.ciclos.count(), 1)

        output = stdout.getvalue()
        self.assertIn("esperado_total: 4", output)
        self.assertIn("pagamentos_before_total: 1", output)
        self.assertIn("pagamentos_after_total: 5", output)
