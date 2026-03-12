from __future__ import annotations

from decimal import Decimal

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Parcela

from .base import ImportacaoBaseTestCase
from ..models import ArquivoRetornoItem
from ..reconciliacao import MotorReconciliacao


class MotorReconciliacaoTestCase(ImportacaoBaseTestCase):
    def test_status_1_baixa_automatica_e_abre_novo_ciclo(self):
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
        self.assertTrue(outcome["gerou_encerramento"])
        self.assertTrue(outcome["gerou_novo_ciclo"])
        self.assertEqual(ultima_parcela.status, Parcela.Status.DESCONTADO)
        self.assertEqual(ciclo.status, Ciclo.Status.CICLO_RENOVADO)
        self.assertEqual(contrato.ciclos.count(), 2)
        self.assertEqual(contrato.ciclos.get(numero=2).status, Ciclo.Status.ABERTO)

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
        self.assertEqual(associado.status, Associado.Status.INADIMPLENTE)

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
        self.assertEqual(associado.status, Associado.Status.INADIMPLENTE)

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
        self.assertEqual(outcome["resultado"], ArquivoRetornoItem.ResultadoProcessamento.NAO_ENCONTRADO)
        self.assertEqual(item.resultado_processamento, ArquivoRetornoItem.ResultadoProcessamento.NAO_ENCONTRADO)

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
