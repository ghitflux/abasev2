from __future__ import annotations

from decimal import Decimal

from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.importacao.reconciliacao import MotorReconciliacao
from apps.importacao.tests.base import ImportacaoBaseTestCase


class RenovacaoCicloViewSetTestCase(ImportacaoBaseTestCase):
    def test_endpoints_refletem_importacao_e_renovacao(self):
        _, _, _ = self.create_associado_com_contrato(
            cpf="23993596315",
            nome="Maria de Jesus Santana Costa",
        )
        _, _, _ = self.create_associado_com_contrato(
            cpf="21819424391",
            nome="Francisco Crisostomo Batista",
        )
        self.create_associado_com_contrato(
            cpf="48204773315",
            nome="Maria de Jesus Araujo Goncalves",
        )

        arquivo = self.create_arquivo_retorno(nome="retorno_renovacao.txt")
        arquivo.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo.save(update_fields=["status", "updated_at"])

        item_efetivado = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj="23993596315",
            matricula_servidor="030759-9",
            nome_servidor="MARIA DE JESUS SANTANA COSTA",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SEC. EST. ADMIN. E PREVIDEN.",
        )
        MotorReconciliacao(arquivo).reconciliar_item(item_efetivado)

        item_rejeitado = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=2,
            cpf_cnpj="21819424391",
            matricula_servidor="019061-6",
            nome_servidor="FRANCISCO CRISOSTOMO BATISTA",
            cargo="2-AGENTE TECNICO DE SERVICO",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="S",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não Lançado: Compra de Dívida ou Suspensão SEAD",
            motivo_rejeicao="Não Lançado: Compra de Dívida ou Suspensão SEAD",
            orgao_codigo="012",
            orgao_pagto_codigo="012",
            orgao_pagto_nome="SEC DE SAUDE",
        )
        MotorReconciliacao(arquivo).reconciliar_item(item_rejeitado)

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/visao-mensal/",
            {"competencia": "2025-05"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        resumo = response.json()
        self.assertEqual(resumo["competencia"], "05/2025")
        self.assertEqual(resumo["total_associados"], 3)
        self.assertEqual(resumo["ciclo_iniciado"], 1)
        self.assertEqual(resumo["inadimplente"], 1)
        self.assertEqual(resumo["em_aberto"], 1)

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2025-05", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["results"][0]["competencia"], "05/2025")

        response = self.tes_client.get("/api/v1/renovacao-ciclos/meses/")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()[0]["id"], "2025-05")

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/exportar/",
            {"competencia": "2025-05"},
        )
        self.assertEqual(response.status_code, 200, response.json())
        export_payload = response.json()
        self.assertEqual(export_payload["competencia"], "05/2025")
        self.assertEqual(export_payload["total"], 3)
