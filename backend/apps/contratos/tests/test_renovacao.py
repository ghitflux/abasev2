from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone

from apps.associados.models import Associado
from apps.accounts.models import User
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.importacao.reconciliacao import MotorReconciliacao
from apps.importacao.tests.base import ImportacaoBaseTestCase
from apps.refinanciamento.models import Refinanciamento


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

    def test_listagem_inclui_apto_projetado_sem_parcela_na_competencia(self):
        associado = Associado.objects.create(
            nome_completo="Servidor Sem Parcela em Abril",
            cpf_cnpj="90123456789",
            email="90123456789@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-APRIL-01",
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
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2026-04", "status": "apto_a_renovar", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        row = payload["results"][0]
        self.assertEqual(row["contrato_id"], contrato.id)
        self.assertEqual(row["contrato_codigo"], contrato.codigo)
        self.assertEqual(row["competencia"], "04/2026")
        self.assertEqual(row["status_visual"], "apto_a_renovar")
        self.assertEqual(row["resultado_importacao"], "sem_competencia")

    def test_listagem_remove_apto_quando_renovacao_foi_efetivada_na_competencia(self):
        associado = Associado.objects.create(
            nome_completo="Servidor Renovado em Abril",
            cpf_cnpj="90123456780",
            email="90123456780@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-APRIL-02",
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
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    numero=1,
                    referencia_mes=date(2026, 1, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 1, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 1, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=2,
                    referencia_mes=date(2026, 2, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 2, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2026, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    numero=3,
                    referencia_mes=date(2026, 3, 1),
                    valor=Decimal("300.00"),
                    data_vencimento=date(2026, 3, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )
        ciclo_destino = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 4, 1),
            data_fim=date(2026, 6, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            ciclo_origem=ciclo,
            ciclo_destino=ciclo_destino,
            solicitado_por=self.tesoureiro,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.EFETIVADO,
            executado_em=timezone.make_aware(datetime(2026, 4, 10, 9, 0)),
            data_ativacao_ciclo=timezone.make_aware(datetime(2026, 4, 10, 9, 0)),
        )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2026-04", "status": "apto_a_renovar", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["count"], 0)

    def test_listagem_apta_restringe_agente_aos_proprios_contratos(self):
        associado_agente, contrato_agente, _ = self.create_associado_com_contrato(
            cpf="90111111111",
            nome="Apto do Agente",
        )
        associado_agente.agente_responsavel = self.agente
        associado_agente.save(update_fields=["agente_responsavel", "updated_at"])
        contrato_agente.agente = self.agente
        contrato_agente.save(update_fields=["agente", "updated_at"])

        self.create_associado_com_contrato(
            cpf="90222222222",
            nome="Apto de Outro Agente",
        )

        response = self.agent_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2025-05", "status": "apto_a_renovar", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["contrato_id"], contrato_agente.id)
        self.assertEqual(payload["results"][0]["associado_id"], associado_agente.id)

    def test_listagem_apta_inclui_associado_ainda_ativo_quando_contrato_esta_apto(self):
        associado_base = Associado.objects.create(
            nome_completo="Base Fila Apta",
            cpf_cnpj="90233333333",
            email="90233333333@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-BASE",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato_base = Contrato.objects.create(
            associado=associado_base,
            agente=self.tesoureiro,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
            data_contrato=date(2026, 1, 10),
        )
        ciclo_base = Ciclo.objects.create(
            contrato=contrato_base,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("900.00"),
        )
        for numero, referencia in enumerate(
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo_base,
                associado=associado_base,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )

        associado = Associado.objects.create(
            nome_completo="Apto Manual Ainda Ativo",
            cpf_cnpj="90244444444",
            email="90244444444@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-MANUAL",
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
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
            data_contrato=date(2026, 1, 12),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        for numero, referencia in enumerate(
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2026-04", "status": "apto_a_renovar", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        returned_associado_ids = {item["associado_id"] for item in payload["results"]}
        self.assertIn(associado.id, returned_associado_ids)

    def test_listagem_apta_inclui_ciclo_concluido_quando_elegivel_sem_fluxo_novo(self):
        associado = Associado.objects.create(
            nome_completo="Apto Concluido Sem Fluxo",
            cpf_cnpj="90255555555",
            email="90255555555@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-CONCLUIDO",
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
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
            data_contrato=date(2026, 1, 12),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.FECHADO,
            valor_total=Decimal("900.00"),
        )
        for numero, referencia in enumerate(
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            start=1,
        ):
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=numero,
                referencia_mes=referencia,
                valor=Decimal("300.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )

        response = self.tes_client.get(
            "/api/v1/renovacao-ciclos/",
            {"competencia": "2026-04", "status": "apto_a_renovar", "page_size": 20},
        )

        self.assertEqual(response.status_code, 200, response.json())
        payload = response.json()
        returned_associado_ids = {item["associado_id"] for item in payload["results"]}
        self.assertIn(associado.id, returned_associado_ids)

    @patch("apps.contratos.views.resolve_current_renewal_competencia", return_value=date(2026, 4, 1))
    def test_resumo_renovacao_mostra_renovados_globais_para_admin_e_proprios_para_agente(self, _competencia_mock):
        outro_agente = User.objects.create_user(
            email="outro.agente@abase.local",
            password="Senha@123",
            first_name="Outro",
            last_name="Agente",
            is_active=True,
        )
        outro_agente.roles.add(self.role_agente)

        associado_admin = Associado.objects.create(
            nome_completo="Associado Renovado Admin",
            cpf_cnpj="90333333333",
            email="90333333333@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-RES-ADMIN",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato_admin = Contrato.objects.create(
            associado=associado_admin,
            agente=self.agente,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
            data_contrato=date(2026, 1, 10),
        )
        ciclo_admin = Ciclo.objects.create(
            contrato=contrato_admin,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        Refinanciamento.objects.create(
            associado=associado_admin,
            contrato_origem=contrato_admin,
            ciclo_origem=ciclo_admin,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.EFETIVADO,
            executado_em=timezone.make_aware(datetime(2026, 3, 10, 10, 0)),
            data_ativacao_ciclo=timezone.make_aware(datetime(2026, 3, 10, 10, 0)),
            valor_refinanciamento=Decimal("90.00"),
            repasse_agente=Decimal("9.00"),
            origem=Refinanciamento.Origem.OPERACIONAL,
        )

        associado_outro = Associado.objects.create(
            nome_completo="Associado Renovado Outro",
            cpf_cnpj="90444444444",
            email="90444444444@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-RES-OUTRO",
            status=Associado.Status.ATIVO,
            agente_responsavel=outro_agente,
        )
        contrato_outro = Contrato.objects.create(
            associado=associado_outro,
            agente=outro_agente,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2026, 1, 1),
            data_aprovacao=date(2025, 12, 28),
            data_contrato=date(2026, 1, 12),
        )
        ciclo_outro = Ciclo.objects.create(
            contrato=contrato_outro,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("900.00"),
        )
        Refinanciamento.objects.create(
            associado=associado_outro,
            contrato_origem=contrato_outro,
            ciclo_origem=ciclo_outro,
            solicitado_por=outro_agente,
            competencia_solicitada=date(2026, 2, 1),
            status=Refinanciamento.Status.EFETIVADO,
            executado_em=timezone.make_aware(datetime(2026, 2, 10, 10, 0)),
            data_ativacao_ciclo=timezone.make_aware(datetime(2026, 2, 10, 10, 0)),
            valor_refinanciamento=Decimal("90.00"),
            repasse_agente=Decimal("9.00"),
            origem=Refinanciamento.Origem.OPERACIONAL,
        )

        em_analise = Refinanciamento.objects.create(
            associado=associado_admin,
            contrato_origem=contrato_admin,
            ciclo_origem=ciclo_admin,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 4, 1),
            status=Refinanciamento.Status.PENDENTE_TERMO_AGENTE,
            valor_refinanciamento=Decimal("90.00"),
            repasse_agente=Decimal("9.00"),
            origem=Refinanciamento.Origem.OPERACIONAL,
        )
        self.assertIsNotNone(em_analise.id)

        admin_response = self.admin_client.get("/api/v1/contratos/renovacao-resumo/")
        self.assertEqual(admin_response.status_code, 200, admin_response.json())
        self.assertEqual(admin_response.json()["renovados"], 2)
        self.assertEqual(admin_response.json()["em_analise"], 1)

        agent_response = self.agent_client.get("/api/v1/contratos/renovacao-resumo/")
        self.assertEqual(agent_response.status_code, 200, agent_response.json())
        self.assertEqual(agent_response.json()["renovados"], 1)
        self.assertEqual(agent_response.json()["em_analise"], 1)
