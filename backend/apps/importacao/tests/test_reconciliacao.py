from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.refinanciamento.models import Refinanciamento

from .base import ImportacaoBaseTestCase
from ..models import ArquivoRetornoItem, ImportacaoLog
from ..reconciliacao import MotorReconciliacao


class MotorReconciliacaoTestCase(ImportacaoBaseTestCase):
    def test_status_1_baixa_automatica_nao_altera_status_do_ciclo(self):
        _, contrato, ciclo = self.create_associado_com_contrato(
            cpf="23993596315",
            nome="Maria de Jesus Santana Costa",
        )
        arquivo = self.create_arquivo_retorno()
        item = ArquivoRetornoItem.objects.create(
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

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        ciclo.refresh_from_db()
        ultima_parcela = ciclo.parcelas.get(numero=3)

        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertFalse(outcome["gerou_encerramento"])
        self.assertFalse(outcome["gerou_novo_ciclo"])
        self.assertEqual(ultima_parcela.status, Parcela.Status.DESCONTADO)
        self.assertEqual(ciclo.status, Ciclo.Status.ABERTO)
        self.assertEqual(contrato.ciclos.count(), 1)

    def test_status_1_preserva_ciclo_mesmo_quando_proxima_janela_ja_esta_ocupada(self):
        associado, contrato, ciclo = self.create_associado_com_contrato(
            cpf="23993596316",
            nome="Maria Competencia Ocupada",
        )
        contrato_conflitante = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 6, 1),
            data_aprovacao=date(2025, 5, 25),
        )
        ciclo_conflitante = Ciclo.objects.create(
            contrato=contrato_conflitante,
            numero=1,
            data_inicio=date(2025, 6, 1),
            data_fim=date(2025, 8, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=1,
                    referencia_mes=date(2025, 6, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 6, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=2,
                    referencia_mes=date(2025, 7, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 7, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
                Parcela(
                    ciclo=ciclo_conflitante,
                    numero=3,
                    referencia_mes=date(2025, 8, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 8, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        arquivo = self.create_arquivo_retorno(nome="retorno_sem_novo_ciclo.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=11,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="MAT-CONFLITO",
            nome_servidor="MARIA COMPETENCIA OCUPADA",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        ciclo.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertFalse(outcome["gerou_encerramento"])
        self.assertFalse(outcome["gerou_novo_ciclo"])
        self.assertEqual(ciclo.status, Ciclo.Status.ABERTO)
        self.assertEqual(contrato.ciclos.count(), 1)
        self.assertFalse(
            ImportacaoLog.objects.filter(
                arquivo_retorno=arquivo,
                mensagem="Conflito de competência impediu a abertura do próximo ciclo.",
            ).exists()
        )

    def test_status_rejeitado_marca_inadimplencia(self):
        associado, _, ciclo = self.create_associado_com_contrato(
            cpf="21819424391",
            nome="Francisco Crisostomo Batista",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_rejeitado.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=2,
            cpf_cnpj="21819424391",
            matricula_servidor="019061-6",
            nome_servidor="FRANCISCO CRISOSTOMO BATISTA",
            cargo="2-AGENTE TECNICO DE SERVICO",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="2",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não Lançado por Falta de Margem Temporariamente",
            motivo_rejeicao="Não Lançado por Falta de Margem Temporariamente",
            orgao_codigo="012",
            orgao_pagto_codigo="012",
            orgao_pagto_nome="SEC DE SAUDE",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        associado.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        self.assertEqual(ciclo.parcelas.get(numero=3).status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)

    def test_status_4_baixa_automatica_com_diferenca(self):
        _, _, ciclo = self.create_associado_com_contrato(
            cpf="48204773315",
            nome="Maria de Jesus Araujo Goncalves",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_pendente.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=4,
            cpf_cnpj="48204773315",
            matricula_servidor="108993-5",
            nome_servidor="MARIA DE JESUS ARAUJO GONCALVE",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="4",
            status_desconto=ArquivoRetornoItem.StatusDesconto.PENDENTE,
            status_descricao="Lançado com Valor Diferente",
            orgao_codigo="090",
            orgao_pagto_codigo="090",
            orgao_pagto_nome="PIAUIPREV PENSIONISTAS",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        parcela = ciclo.parcelas.get(numero=3)
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertEqual(parcela.status, Parcela.Status.DESCONTADO)
        self.assertIn("divergência", item.observacao.lower())

    def test_status_s_marca_nao_descontado(self):
        associado, _, ciclo = self.create_associado_com_contrato(
            cpf="11122233344",
            nome="Servidor Suspenso",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_suspenso.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=5,
            cpf_cnpj="11122233344",
            matricula_servidor="000555-5",
            nome_servidor="SERVIDOR SUSPENSO",
            cargo="CARGO TESTE",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="S",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não Lançado: Compra de Dívida ou Suspensão SEAD",
            motivo_rejeicao="Não Lançado: Compra de Dívida ou Suspensão SEAD",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SECRETARIA TESTE",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        associado.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        self.assertEqual(ciclo.parcelas.get(numero=3).status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)

    def test_divergencia_de_valor_vai_para_pendencia_manual(self):
        _, _, ciclo = self.create_associado_com_contrato(
            cpf="99988877766",
            nome="Servidor Divergente",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_divergente.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=6,
            cpf_cnpj="99988877766",
            matricula_servidor="000666-6",
            nome_servidor="SERVIDOR DIVERGENTE",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("29.99"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SECRETARIA TESTE",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL)
        self.assertEqual(ciclo.parcelas.get(numero=3).status, Parcela.Status.EM_ABERTO)

    def test_status_1_alinha_parcela_quando_contrato_ja_tem_valor_do_retorno(self):
        associado, contrato, ciclo = self.create_associado_com_contrato(
            cpf="09945431315",
            nome="Divaldo de Teste",
            valor_mensalidade=Decimal("500.00"),
        )
        associado.status = Associado.Status.INADIMPLENTE
        associado.save(update_fields=["status", "updated_at"])
        parcela = ciclo.parcelas.get(numero=3)
        parcela.valor = Decimal("30.00")
        parcela.status = Parcela.Status.EM_ABERTO
        parcela.save(update_fields=["valor", "status", "updated_at"])

        arquivo = self.create_arquivo_retorno(nome="retorno_alinha_valor.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=20,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="002795-2",
            nome_servidor="DIVALDO DE TESTE",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("500.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SECRETARIA TESTE",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        parcela.refresh_from_db()
        associado.refresh_from_db()
        contrato.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertEqual(parcela.valor, Decimal("500.00"))
        self.assertEqual(parcela.status, Parcela.Status.DESCONTADO)
        self.assertEqual(associado.status, Associado.Status.ATIVO)
        self.assertEqual(item.parcela_id, parcela.id)

    def test_cpf_nao_encontrado(self):
        arquivo = self.create_arquivo_retorno(nome="retorno_nao_encontrado.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=3,
            cpf_cnpj="18084974300",
            matricula_servidor="021293-8",
            nome_servidor="MIGUEL ALVES DO NASCIMENTO",
            cargo="1-AGENTE OPERACIONAL DE SERVIC",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="3",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não Lançado por Outros Motivos",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        associado = item.associado
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        self.assertEqual(item.resultado_processamento, ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        self.assertTrue(outcome["associado_importado"])
        self.assertIsNotNone(associado)
        self.assertEqual(associado.status, Associado.Status.INADIMPLENTE)
        self.assertEqual(associado.arquivo_retorno_origem, "retorno_nao_encontrado.txt")
        self.assertEqual(associado.ultimo_arquivo_retorno, "retorno_nao_encontrado.txt")
        self.assertEqual(associado.competencia_importacao_retorno, date(2025, 5, 1))
        self.assertIsNone(item.parcela_id)

    def test_associado_existente_sem_parcela_processa_sem_criar_contrato_ou_ciclo(self):
        associado = Associado.objects.create(
            nome_completo="ASSOCIADO SEM PARCELA",
            cpf_cnpj="11122233344",
            status=Associado.Status.ATIVO,
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_sem_parcela.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=9,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="RET-9001",
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        self.assertEqual(Contrato.objects.filter(associado=associado).count(), 0)
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertIsNone(item.parcela_id)
        self.assertIn("sem parcela local", item.observacao.lower())

    def test_contrato_sem_parcela_na_competencia_nao_ganha_novo_ciclo(self):
        associado = Associado.objects.create(
            nome_completo="ASSOCIADO RETIMP INCOMPLETO",
            cpf_cnpj="11122233355",
            status=Associado.Status.ATIVO,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            codigo="CTR-RET-9002",
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 2, 1),
            data_aprovacao=date(2025, 1, 20),
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 2, 1),
            data_fim=date(2025, 4, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=1,
                    referencia_mes=date(2025, 2, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 2, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 2, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=2,
                    referencia_mes=date(2025, 3, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 3, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 3, 15),
                ),
                Parcela(
                    ciclo=ciclo,
                    associado=associado,
                    numero=3,
                    referencia_mes=date(2025, 4, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 4, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 4, 15),
                ),
            ]
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_retimp_incompleto.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=10,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="RET-9002",
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        contrato.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertIsNone(item.parcela_id)
        self.assertEqual(contrato.ciclos.count(), 1)
        self.assertFalse(
            contrato.ciclos.filter(parcelas__referencia_mes=date(2025, 5, 1)).exists()
        )

    def test_casamento_por_matricula_faz_baixa_quando_cpf_nao_bate(self):
        _, _, ciclo = self.create_associado_com_contrato(
            cpf="55544433322",
            nome="Servidor Matricula",
            matricula_orgao="030759-9",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_matricula.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=7,
            cpf_cnpj="00000000000",
            matricula_servidor="030759-9",
            nome_servidor="SERVIDOR MATRICULA",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertIsNotNone(item.associado_id)
        self.assertEqual(ciclo.parcelas.get(numero=3).status, Parcela.Status.DESCONTADO)

    def test_casamento_por_nome_e_orgao_quando_cpf_e_matricula_nao_batem(self):
        _, _, ciclo = self.create_associado_com_contrato(
            cpf="22233344455",
            nome="Servidor Nome Orgao",
            matricula_orgao="RET-3001",
            orgao_publico="SECRETARIA DE TESTE",
        )
        arquivo = self.create_arquivo_retorno(nome="retorno_nome_orgao.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=8,
            cpf_cnpj="99999999999",
            matricula_servidor="SEM-MATCH",
            nome_servidor="Servidor Nome Orgao",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SECRETARIA DE TESTE",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertIsNotNone(item.associado_id)
        self.assertEqual(ciclo.parcelas.get(numero=3).status, Parcela.Status.DESCONTADO)

    def test_busca_parcela_prioriza_contrato_ativo_mais_recente_na_competencia(self):
        associado, contrato_antigo, ciclo_antigo = self.create_associado_com_contrato(
            cpf="33322211100",
            nome="Servidor Dois Contratos",
            matricula_orgao="RET-5001",
        )
        self.release_cycle_competencia_locks(ciclo_antigo)
        contrato_antigo.data_aprovacao = date(2025, 2, 20)
        contrato_antigo.save(update_fields=["data_aprovacao", "updated_at"])

        contrato_recente = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 3, 1),
            data_aprovacao=date(2025, 4, 25),
        )
        ciclo_recente = Ciclo.objects.create(
            contrato=contrato_recente,
            numero=1,
            data_inicio=date(2025, 3, 1),
            data_fim=date(2025, 5, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_recente,
                    numero=1,
                    referencia_mes=date(2025, 3, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 3, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 3, 15),
                ),
                Parcela(
                    ciclo=ciclo_recente,
                    numero=2,
                    referencia_mes=date(2025, 4, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 4, 1),
                    status=Parcela.Status.DESCONTADO,
                    data_pagamento=date(2025, 4, 15),
                ),
                Parcela(
                    ciclo=ciclo_recente,
                    numero=3,
                    referencia_mes=date(2025, 5, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 5, 1),
                    status=Parcela.Status.EM_ABERTO,
                ),
            ]
        )

        arquivo = self.create_arquivo_retorno(nome="retorno_contratos_duplicados.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=9,
            cpf_cnpj="33322211100",
            matricula_servidor="RET-5001",
            nome_servidor="SERVIDOR DOIS CONTRATOS",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertEqual(item.parcela.ciclo.contrato_id, contrato_recente.id)
        self.assertEqual(
            ciclo_antigo.parcelas.get(numero=3).status,
            Parcela.Status.DESCONTADO,
        )
        self.assertEqual(
            ciclo_recente.parcelas.get(numero=3).status,
            Parcela.Status.DESCONTADO,
        )

    def test_nao_abre_ciclo_futuro_de_refinanciamento_pendente(self):
        associado, contrato, ciclo_atual = self.create_associado_com_contrato(
            cpf="44455566677",
            nome="Servidor Refinanciado",
        )
        ciclo_futuro = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2025, 6, 1),
            data_fim=date(2025, 8, 1),
            status=Ciclo.Status.FUTURO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo_futuro,
                    numero=1,
                    referencia_mes=date(2025, 6, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 6, 1),
                    status=Parcela.Status.FUTURO,
                ),
                Parcela(
                    ciclo=ciclo_futuro,
                    numero=2,
                    referencia_mes=date(2025, 7, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 7, 1),
                    status=Parcela.Status.FUTURO,
                ),
                Parcela(
                    ciclo=ciclo_futuro,
                    numero=3,
                    referencia_mes=date(2025, 8, 1),
                    valor=Decimal("30.00"),
                    data_vencimento=date(2025, 8, 1),
                    status=Parcela.Status.FUTURO,
                ),
            ]
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.tesoureiro,
            competencia_solicitada=date(2025, 6, 1),
            status=Refinanciamento.Status.PENDENTE_APTO,
            ciclo_origem=ciclo_atual,
            ciclo_destino=ciclo_futuro,
            valor_refinanciamento=Decimal("90.00"),
            repasse_agente=Decimal("9.00"),
        )

        arquivo = self.create_arquivo_retorno(nome="retorno_refinanciamento_pendente.txt")
        item = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=10,
            cpf_cnpj="44455566677",
            matricula_servidor="MAT-REFI",
            nome_servidor="SERVIDOR REFINANCIADO",
            cargo="-",
            competencia="05/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
        )

        outcome = MotorReconciliacao(arquivo).reconciliar_item(item)

        item.refresh_from_db()
        ciclo_atual.refresh_from_db()
        ciclo_futuro.refresh_from_db()
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        self.assertFalse(item.gerou_encerramento)
        self.assertFalse(item.gerou_novo_ciclo)
        self.assertEqual(ciclo_atual.status, Ciclo.Status.ABERTO)
        self.assertEqual(ciclo_futuro.status, Ciclo.Status.FUTURO)
        self.assertFalse(
            ciclo_futuro.parcelas.exclude(status=Parcela.Status.FUTURO).exists()
        )
