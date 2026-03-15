from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.importacao.models import ArquivoRetornoItem
from apps.importacao.tests.base import ImportacaoBaseTestCase

from ..cycle_normalization import dedupe_cycles_for_display, normalize_duplicate_cycles
from ..models import Ciclo, Contrato, Parcela


class CycleNormalizationTestCase(ImportacaoBaseTestCase):
    def test_dedupe_cycles_for_display_prefers_active_cycle_with_more_progress(self):
        associado, contrato_ativo, ciclo_ativo = self.create_associado_com_contrato(
            cpf="70000000001",
            nome="Associado Duplicado",
        )
        self.release_cycle_competencia_locks(ciclo_ativo)
        contrato_duplicado = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_primeira_mensalidade=date(2025, 3, 1),
            data_aprovacao=date(2025, 2, 20),
        )
        ciclo_duplicado = Ciclo.objects.create(
            contrato=contrato_duplicado,
            numero=1,
            data_inicio=ciclo_ativo.data_inicio,
            data_fim=ciclo_ativo.data_fim,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_duplicado,
                    numero=1,
                    referencia_mes=date(2025, 3, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 3, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_duplicado,
                    numero=2,
                    referencia_mes=date(2025, 4, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 4, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_duplicado,
                    numero=3,
                    referencia_mes=date(2025, 5, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 5, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        ciclos = list(
            Ciclo.objects.filter(contrato__associado=associado)
            .select_related("contrato")
            .prefetch_related("parcelas__itens_retorno")
        )
        deduped = dedupe_cycles_for_display(ciclos)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].id, ciclo_ativo.id)

    def test_normalize_duplicate_cycles_syncs_duplicate_contract_without_canceling(self):
        associado, contrato_ativo, ciclo_ativo = self.create_associado_com_contrato(
            cpf="70000000002",
            nome="Associado Reatribuido",
        )
        self.release_cycle_competencia_locks(ciclo_ativo)
        contrato_duplicado = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_primeira_mensalidade=date(2025, 3, 1),
            data_aprovacao=date(2025, 2, 20),
        )
        ciclo_duplicado = Ciclo.objects.create(
            contrato=contrato_duplicado,
            numero=1,
            data_inicio=ciclo_ativo.data_inicio,
            data_fim=ciclo_ativo.data_fim,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        duplicate_parcelas = [
            Parcela.objects.create(
                ciclo=ciclo_duplicado,
                numero=1,
                referencia_mes=date(2025, 3, 1),
                valor=Decimal("30.00"),
                data_vencimento=date(2025, 3, 1),
                status=Parcela.Status.EM_ABERTO,
            ),
            Parcela.objects.create(
                ciclo=ciclo_duplicado,
                numero=2,
                referencia_mes=date(2025, 4, 1),
                valor=Decimal("30.00"),
                data_vencimento=date(2025, 4, 1),
                status=Parcela.Status.EM_ABERTO,
            ),
            Parcela.objects.create(
                ciclo=ciclo_duplicado,
                numero=3,
                referencia_mes=date(2025, 5, 1),
                valor=Decimal("30.00"),
                data_vencimento=date(2025, 5, 1),
                status=Parcela.Status.EM_ABERTO,
            ),
        ]
        arquivo = self.create_arquivo_retorno(nome="duplicado.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="MAT-1",
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="001",
            orgao_pagto_codigo="001",
            orgao_pagto_nome="Órgão Teste",
            associado=associado,
            parcela=duplicate_parcelas[0],
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )

        summary = normalize_duplicate_cycles(
            cpf_cnpj=associado.cpf_cnpj,
            execute=True,
        )

        contrato_duplicado.refresh_from_db()
        ciclo_duplicado.refresh_from_db()
        item.refresh_from_db()
        duplicate_parcelas[0].refresh_from_db()

        self.assertEqual(summary["groups"], 1)
        self.assertEqual(summary["duplicate_cycles"], 1)
        self.assertEqual(summary["reassigned_return_items"], 0)
        self.assertEqual(contrato_duplicado.status, Contrato.Status.EM_ANALISE)
        self.assertEqual(ciclo_duplicado.status, ciclo_ativo.status)
        self.assertEqual(duplicate_parcelas[0].status, ciclo_ativo.parcelas.get(numero=1).status)
        self.assertEqual(
            duplicate_parcelas[0].data_pagamento,
            ciclo_ativo.parcelas.get(numero=1).data_pagamento,
        )
        self.assertEqual(item.parcela_id, duplicate_parcelas[0].id)
