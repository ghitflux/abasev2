from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.importacao.tests.base import ImportacaoBaseTestCase


class CorrigirPrevisoesVencidasCommandTestCase(ImportacaoBaseTestCase):
    def _create_parcela(
        self,
        *,
        cpf: str,
        nome: str,
        competencia: date,
        codigo: str,
        numero: int = 1,
    ) -> Parcela:
        associado = Associado.objects.create(
            nome_completo=nome,
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
            codigo=codigo,
            valor_bruto=Decimal("300.00"),
            valor_liquido=Decimal("300.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=competencia,
            data_aprovacao=competencia,
            data_primeira_mensalidade=competencia,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=competencia,
            data_fim=competencia,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("300.00"),
        )
        return Parcela.objects.create(
            ciclo=ciclo,
            associado=associado,
            numero=numero,
            referencia_mes=competencia,
            valor=Decimal("300.00"),
            data_vencimento=competencia,
            status=Parcela.Status.EM_PREVISAO,
        )

    def _create_arquivo(self, *, competencia: date) -> ArquivoRetorno:
        arquivo = self.create_arquivo_retorno(nome=f"retorno_{competencia:%Y_%m}.txt")
        arquivo.competencia = competencia
        arquivo.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo.processado_em = timezone.make_aware(
            datetime.combine(competencia, datetime.min.time())
        )
        arquivo.save(update_fields=["competencia", "status", "processado_em", "updated_at"])
        return arquivo

    def _create_item(
        self,
        *,
        arquivo: ArquivoRetorno,
        parcela: Parcela,
        status_codigo: str,
        linha_numero: int,
    ) -> None:
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=linha_numero,
            cpf_cnpj=parcela.associado.cpf_cnpj,
            matricula_servidor=parcela.associado.matricula_orgao,
            nome_servidor=parcela.associado.nome_completo,
            cargo="SERVIDOR",
            competencia=arquivo.competencia.strftime("%m/%Y"),
            valor_descontado=parcela.valor,
            status_codigo=status_codigo,
            status_desconto=(
                ArquivoRetornoItem.StatusDesconto.EFETIVADO
                if status_codigo in {"1", "4"}
                else ArquivoRetornoItem.StatusDesconto.REJEITADO
            ),
            status_descricao="Teste",
            associado=parcela.associado,
            parcela=parcela,
            processado=True,
        )

    def _run_command(self, *args: str) -> str:
        stdout = StringIO()
        call_command("corrigir_previsoes_vencidas", *args, stdout=stdout)
        return stdout.getvalue()

    def test_dry_run_resume_quantidades_por_destino(self):
        competencia = date(2025, 10, 1)
        arquivo = self._create_arquivo(competencia=competencia)
        parcela_descontado = self._create_parcela(
            cpf="11111111111",
            nome="Associado Descontado",
            competencia=competencia,
            codigo="CTR-DESC",
        )
        parcela_nao_descontado = self._create_parcela(
            cpf="22222222222",
            nome="Associado Nao Descontado",
            competencia=competencia,
            codigo="CTR-NDESC",
        )
        _parcela_sem_item = self._create_parcela(
            cpf="33333333333",
            nome="Associado Sem Item",
            competencia=competencia,
            codigo="CTR-SEMITEM",
        )
        self._create_item(
            arquivo=arquivo,
            parcela=parcela_descontado,
            status_codigo="1",
            linha_numero=1,
        )
        self._create_item(
            arquivo=arquivo,
            parcela=parcela_nao_descontado,
            status_codigo="2",
            linha_numero=2,
        )

        with patch(
            "apps.importacao.overdue_forecast_correction.timezone.localdate",
            return_value=date(2026, 4, 8),
        ):
            output = self._run_command(
                "--competencia-inicial",
                "2025-10",
                "--competencia-final",
                "2025-10",
            )

        self.assertIn("modo: dry-run", output)
        self.assertIn("parcelas_avaliadas: 3", output)
        self.assertIn("parcelas_descontado: 1", output)
        self.assertIn("parcelas_nao_descontado: 2", output)
        self.assertIn("parcelas_sem_item: 1", output)

    def test_apply_converte_previsao_passada_com_item_e_sem_item(self):
        competencia = date(2025, 10, 1)
        arquivo = self._create_arquivo(competencia=competencia)
        parcela_descontado = self._create_parcela(
            cpf="44444444444",
            nome="Associado Descontado",
            competencia=competencia,
            codigo="CTR-DESC-APPLY",
        )
        parcela_nao_descontado = self._create_parcela(
            cpf="55555555555",
            nome="Associado Nao Descontado",
            competencia=competencia,
            codigo="CTR-NDESC-APPLY",
        )
        parcela_sem_item = self._create_parcela(
            cpf="66666666666",
            nome="Associado Sem Item",
            competencia=competencia,
            codigo="CTR-SEMITEM-APPLY",
        )
        parcela_setembro = self._create_parcela(
            cpf="77777777777",
            nome="Associado Setembro",
            competencia=date(2025, 9, 1),
            codigo="CTR-SETEMBRO",
        )
        self._create_item(
            arquivo=arquivo,
            parcela=parcela_descontado,
            status_codigo="1",
            linha_numero=1,
        )
        self._create_item(
            arquivo=arquivo,
            parcela=parcela_nao_descontado,
            status_codigo="2",
            linha_numero=2,
        )

        with patch(
            "apps.importacao.overdue_forecast_correction.timezone.localdate",
            return_value=date(2026, 4, 8),
        ):
            self._run_command(
                "--competencia-inicial",
                "2025-10",
                "--competencia-final",
                "2025-10",
                "--apply",
            )

        parcela_descontado.refresh_from_db()
        parcela_nao_descontado.refresh_from_db()
        parcela_sem_item.refresh_from_db()
        parcela_setembro.refresh_from_db()
        parcela_nao_descontado.associado.refresh_from_db()
        parcela_sem_item.associado.refresh_from_db()

        self.assertEqual(parcela_descontado.status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcela_descontado.data_pagamento, competencia)
        self.assertEqual(parcela_nao_descontado.status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(parcela_sem_item.status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(
            parcela_nao_descontado.associado.status,
            Associado.Status.INADIMPLENTE,
        )
        self.assertEqual(
            parcela_sem_item.associado.status,
            Associado.Status.INADIMPLENTE,
        )
        self.assertEqual(parcela_setembro.status, Parcela.Status.EM_PREVISAO)
