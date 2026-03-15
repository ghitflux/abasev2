from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.importacao.reconciliacao import MotorReconciliacao
from apps.importacao.tests.base import ImportacaoBaseTestCase


class RenovacaoCicloViewSetTestCase(ImportacaoBaseTestCase):
    @patch("apps.contratos.renovacao.build_financeiro_resumo")
    def test_visao_mensal_prioriza_financeiro_sem_filtros(self, financeiro_mock):
        self.create_associado_com_contrato(
            cpf="11122233344",
            nome="Servidor Financeiro Janeiro",
        )
        financeiro_mock.return_value = {
            "total": 588,
            "esperado": Decimal("138996.42"),
            "recebido": Decimal("113099.84"),
            "percentual": 81.4,
        }

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/visao-mensal/",
            {"competencia": "2025-05"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["total_associados"], 588)
        self.assertEqual(payload["apto_a_renovar"], 1)
        self.assertEqual(payload["esperado_total"], "138996.42")
        self.assertEqual(payload["arrecadado_total"], "113099.84")
        self.assertEqual(payload["percentual_arrecadado"], 81.4)
        financeiro_mock.assert_called_once()

    @patch("apps.contratos.renovacao.build_financeiro_resumo")
    def test_visao_mensal_com_filtros_mantem_resumo_operacional(self, financeiro_mock):
        self.create_associado_com_contrato(
            cpf="44433322211",
            nome="Servidor Filtro Renovacao",
        )
        financeiro_mock.return_value = {
            "total": 588,
            "esperado": Decimal("138996.42"),
            "recebido": Decimal("113099.84"),
            "percentual": 81.4,
        }

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/visao-mensal/",
            {"competencia": "2025-05", "search": "Filtro"},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["total_associados"], 1)
        self.assertEqual(payload["apto_a_renovar"], 1)
        self.assertEqual(payload["esperado_total"], "30.00")
        self.assertEqual(payload["arrecadado_total"], "0.00")
        self.assertEqual(payload["percentual_arrecadado"], 0.0)
        financeiro_mock.assert_not_called()

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
        self.assertEqual(resumo["ciclo_renovado"], 1)
        self.assertEqual(resumo["apto_a_renovar"], 1)
        self.assertEqual(resumo["ciclo_iniciado"], 1)
        self.assertEqual(resumo["inadimplente"], 1)
        self.assertEqual(resumo["em_aberto"], 0)

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2025-05", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["results"][0]["competencia"], "05/2025")
        self.assertTrue(payload["results"][0]["matricula"].startswith("MAT-"))
        self.assertEqual(payload["results"][0]["agente_responsavel"], "Tes ABASE")

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

    def test_listagem_prioriza_item_do_arquivo_concluido_mais_recente(self):
        _, _, ciclo = self.create_associado_com_contrato(
            cpf="55566677788",
            nome="Servidor Arquivos Repetidos",
        )
        parcela = ciclo.parcelas.get(numero=3)

        arquivo_antigo = self.create_arquivo_retorno(nome="retorno_antigo_competencia.txt")
        arquivo_antigo.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo_antigo.save(update_fields=["status", "updated_at"])
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_antigo,
            linha_numero=1,
            cpf_cnpj="55566677788",
            matricula_servidor="RET-7001",
            nome_servidor="SERVIDOR ARQUIVOS REPETIDOS",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="S",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não Lançado por Suspensão",
            associado=parcela.ciclo.contrato.associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
            orgao_pagto_nome="Órgão Antigo",
        )

        arquivo_recente = self.create_arquivo_retorno(nome="retorno_recente_competencia.txt")
        arquivo_recente.status = ArquivoRetorno.Status.CONCLUIDO
        arquivo_recente.save(update_fields=["status", "updated_at"])
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_recente,
            linha_numero=2,
            cpf_cnpj="55566677788",
            matricula_servidor="RET-7001",
            nome_servidor="SERVIDOR ARQUIVOS REPETIDOS",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            associado=parcela.ciclo.contrato.associado,
            parcela=parcela,
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
            orgao_pagto_nome="Órgão Recente",
            gerou_encerramento=True,
            gerou_novo_ciclo=True,
        )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2025-05", "page_size": 10},
        )
        self.assertEqual(response.status_code, 200, response.json())
        row = response.json()["results"][0]
        self.assertEqual(row["resultado_importacao"], "baixa_efetuada")
        self.assertEqual(row["status_codigo_etipi"], "1")
        self.assertEqual(row["status_descricao_etipi"], "Lançado e Efetivado")
        self.assertEqual(row["orgao_pagto_nome"], "Órgão Recente")
        self.assertTrue(row["gerou_encerramento"])
        self.assertTrue(row["gerou_novo_ciclo"])
        self.assertEqual(row["agente_responsavel"], "Tes ABASE")

    def test_apto_a_renovar_respeita_regra_2_de_3_e_informa_contrato_referencia(self):
        associado = Associado.objects.create(
            nome_completo="Maria Helena Oliveira Sampaio",
            cpf_cnpj="07878702349",
            email="07878702349@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-397",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )

        contrato_antigo = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("750.00"),
            valor_liquido=Decimal("750.00"),
            valor_mensalidade=Decimal("250.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 11, 1),
            data_aprovacao=date(2025, 10, 25),
        )
        ciclo_antigo = Ciclo.objects.create(
            contrato=contrato_antigo,
            numero=1,
            data_inicio=date(2025, 11, 1),
            data_fim=date(2026, 1, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("750.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_antigo,
                    numero=1,
                    referencia_mes=date(2025, 11, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2025, 11, 1),
                    status=Parcela.Status.NAO_DESCONTADO,
                ),
                Parcela(
                    ciclo=ciclo_antigo,
                    numero=2,
                    referencia_mes=date(2025, 12, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2025, 12, 1),
                    status=Parcela.Status.NAO_DESCONTADO,
                ),
                Parcela(
                    ciclo=ciclo_antigo,
                    numero=3,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
            ]
        )
        Parcela.all_objects.filter(ciclo=ciclo_antigo).update(competencia_lock=None)

        contrato_atual = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("750.00"),
            valor_liquido=Decimal("750.00"),
            valor_mensalidade=Decimal("250.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
        )
        ciclo_atual = Ciclo.objects.create(
            contrato=contrato_atual,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("750.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_atual,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
                Parcela(
                    ciclo=ciclo_atual,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo_atual,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("250.00"),
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2026-01", "status": "apto_a_renovar", "page_size": 20},
        )
        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)

        row = payload["results"][0]
        self.assertEqual(row["contrato_id"], contrato_atual.id)
        self.assertEqual(row["contrato_codigo"], contrato_atual.codigo)
        self.assertEqual(row["parcelas_pagas"], 2)
        self.assertEqual(row["parcelas_total"], 3)
        self.assertEqual(row["contrato_referencia_renovacao_id"], contrato_atual.id)
        self.assertEqual(
            row["contrato_referencia_renovacao_codigo"],
            contrato_atual.codigo,
        )
        self.assertTrue(row["possui_multiplos_contratos"])
        self.assertIn("2/3 parcelas baixadas", row["status_explicacao"])
        self.assertIn(contrato_atual.codigo, row["status_explicacao"])
