from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from openpyxl import Workbook

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.tesouraria.models import BaixaManual

from .base import ImportacaoBaseTestCase


class ReconcileMaristelaSheetCommandTestCase(ImportacaoBaseTestCase):
    def _create_workbook(self, rows: list[list[object]]) -> Path:
        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Página1"
        sheet.append(
            [
                "CPF",
                " NOME",
                "MENSALIDADE",
                "MATRICULA",
                "outubro/25",
                "dezembro/25",
                "janeiro/26",
                "fevereiro/26",
                "março/26",
            ]
        )
        for row in rows:
            sheet.append(row)
        workbook.save(handle.name)
        return Path(handle.name)

    def _create_contract_fixture(
        self,
        *,
        cpf: str,
        nome: str,
        matricula_orgao: str,
        mensalidade: Decimal = Decimal("100.00"),
    ) -> tuple[Associado, Contrato]:
        associado = Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SECRETARIA DE TESTE",
            matricula_orgao=matricula_orgao,
            status=Associado.Status.EM_ANALISE,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=f"CTR-{cpf[-6:]}",
            valor_bruto=Decimal("400.00"),
            valor_liquido=Decimal("300.00"),
            valor_mensalidade=mensalidade,
            prazo_meses=4,
            taxa_antecipacao=Decimal("30.00"),
            margem_disponivel=Decimal("300.00"),
            valor_total_antecipacao=Decimal("400.00"),
            comissao_agente=Decimal("30.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 11, 15),
            data_aprovacao=date(2025, 11, 15),
            data_primeira_mensalidade=date(2025, 12, 1),
            mes_averbacao=date(2025, 12, 1),
            auxilio_liberado_em=date(2025, 11, 15),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 12, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("400.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=1,
                    referencia_mes=date(2025, 12, 1),
                    valor=mensalidade,
                    data_vencimento=date(2025, 12, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=2,
                    referencia_mes=date(2026, 1, 1),
                    valor=mensalidade,
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=3,
                    referencia_mes=date(2026, 2, 1),
                    valor=mensalidade,
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=4,
                    referencia_mes=date(2026, 3, 1),
                    valor=mensalidade,
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )
        return associado, contrato

    def test_dry_run_reports_unmatched_and_system_only_without_mutating(self):
        associado, _ = self._create_contract_fixture(
            cpf="11122233344",
            nome="Associado Dry Run",
            matricula_orgao="MAT-DRY-1",
        )
        outside, _ = self._create_contract_fixture(
            cpf="55566677788",
            nome="Associado Fora Planilha",
            matricula_orgao="MAT-OUT-1",
        )
        workbook_path = self._create_workbook(
            [
                [
                    11122233344,
                    " ASSOCIADO DRY RUN",
                    100,
                    "MAT-DRY-1",
                    None,
                    "AVERBADO CCH DE DEZEMBRO",
                    "AVERBADO CCH DE JANEIRO",
                    "AVERBADO CCH DE FEVEREIRO",
                    "baixado parcela manual no sistema aguardando CCH de MARÇO",
                ],
                [
                    99988877766,
                    " SEM MATCH",
                    100,
                    "SEM-MATCH",
                    None,
                    "AVERBADO CCH DE DEZEMBRO",
                    None,
                    None,
                    None,
                ],
            ]
        )
        with tempfile.TemporaryDirectory() as report_dir:
            call_command(
                "reconcile_maristela_sheet",
                "--file",
                str(workbook_path),
                "--report-dir",
                report_dir,
                "--dry-run",
            )

            associado.refresh_from_db()
            self.assertEqual(associado.status, Associado.Status.EM_ANALISE)
            self.assertEqual(
                Parcela.objects.get(
                    associado=associado, referencia_mes=date(2025, 12, 1)
                ).status,
                Parcela.Status.EM_ABERTO,
            )

            summary = json.loads(Path(report_dir, "dry_run_summary.json").read_text(encoding="utf-8"))
            system_only = json.loads(
                Path(report_dir, "sistema_fora_da_planilha.json").read_text(encoding="utf-8")
            )
            unmatched = json.loads(
                Path(report_dir, "planilha_sem_match.json").read_text(encoding="utf-8")
            )

        self.assertEqual(summary["mode"], "dry-run")
        self.assertEqual(summary["planilha_sem_match"], 1)
        self.assertTrue(any(row["associado_id"] == outside.id for row in system_only))
        self.assertEqual(unmatched[0]["reason"], "no_match")

    def test_execute_reconciles_paid_months_and_creates_manual_march_baixa(self):
        associado, _ = self._create_contract_fixture(
            cpf="22233344455",
            nome="Associado Pago",
            matricula_orgao="MAT-PAGO-1",
        )
        PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="dez-errado",
            referencia_month=date(2025, 12, 1),
            status_code="3",
            matricula="MAT-PAGO-1",
            orgao_pagto="918",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/dezembro_errado.txt",
        )

        workbook_path = self._create_workbook(
            [
                [
                    22233344455,
                    " ASSOCIADO PAGO",
                    100,
                    "MAT-PAGO-1",
                    None,
                    "AVERBADO CCH DE DEZEMBRO",
                    "AVERBADO CCH DE JANEIRO",
                    "AVERBADO CCH DE FEVEREIRO",
                    "baixado parcela manual no sistema aguardando CCH de MARÇO",
                ]
            ]
        )
        with tempfile.TemporaryDirectory() as report_dir:
            call_command(
                "reconcile_maristela_sheet",
                "--file",
                str(workbook_path),
                "--report-dir",
                report_dir,
                "--execute",
            )

            summary = json.loads(Path(report_dir, "execute_summary.json").read_text(encoding="utf-8"))
            corrections = json.loads(
                Path(report_dir, "correcoes_aplicadas.json").read_text(encoding="utf-8")
            )

        associado.refresh_from_db()
        parcelas = {
            parcela.referencia_mes: parcela
            for parcela in Parcela.objects.filter(associado=associado).order_by("referencia_mes")
        }
        pagamento_dez = PagamentoMensalidade.objects.get(
            associado=associado,
            referencia_month=date(2025, 12, 1),
        )
        pagamento_mar = PagamentoMensalidade.objects.get(
            associado=associado,
            referencia_month=date(2026, 3, 1),
        )

        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(parcelas[date(2025, 12, 1)].status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcelas[date(2026, 1, 1)].status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcelas[date(2026, 2, 1)].status, Parcela.Status.DESCONTADO)
        self.assertNotIn(date(2026, 3, 1), parcelas)
        self.assertTrue(
            BaixaManual.objects.filter(
                parcela__associado=associado,
                data_baixa=date(2026, 3, 1),
            ).exists()
        )
        self.assertEqual(pagamento_dez.status_code, "1")
        self.assertEqual(pagamento_mar.status_code, "M")
        self.assertEqual(pagamento_mar.manual_status, PagamentoMensalidade.ManualStatus.PAGO)
        self.assertEqual(summary["mode"], "execute")
        self.assertTrue(any(row["entity"] == "baixa_manual" for row in corrections))

    def test_execute_marks_associado_inactive_for_falecimento(self):
        associado, _ = self._create_contract_fixture(
            cpf="33344455566",
            nome="Associado Falecimento",
            matricula_orgao="MAT-FAIL-1",
        )
        pagamento = PagamentoMensalidade.objects.create(
            created_by=self.tesoureiro,
            import_uuid="jan-pago",
            referencia_month=date(2026, 1, 1),
            status_code="1",
            matricula="MAT-FAIL-1",
            orgao_pagto="918",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal("100.00"),
            source_file_path="retornos/janeiro.txt",
        )

        workbook_path = self._create_workbook(
            [
                [
                    33344455566,
                    " ASSOCIADO FALECIMENTO",
                    100,
                    "MAT-FAIL-1",
                    None,
                    None,
                    "Não Lancado: Falecimento.",
                    None,
                    None,
                ]
            ]
        )
        call_command(
            "reconcile_maristela_sheet",
            "--file",
            str(workbook_path),
            "--execute",
        )

        associado.refresh_from_db()
        pagamento.refresh_from_db()
        self.assertEqual(associado.status, Associado.Status.INATIVO)
        self.assertFalse(
            Parcela.objects.filter(
                associado=associado,
                referencia_mes=date(2026, 1, 1),
            ).exists()
        )
        self.assertEqual(pagamento.status_code, "3")
