from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.small_value_return_renewal_repair import (
    repair_small_value_return_renewal_block,
)
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.refinanciamento.models import Refinanciamento


class SmallValueReturnRenewalRepairTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = Role.objects.create(codigo="AGENTE", nome="Agente")
        cls.agente = User.objects.create_user(
            email="agente.30-50@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Teste",
            is_active=True,
        )
        cls.agente.roles.add(role)

    def _create_associado(self, cpf: str, nome: str) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )

    def _create_imported_small_value_contract(self) -> Contrato:
        associado = self._create_associado("70100000001", "Associado 30 Importado")
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("90.00"),
            valor_liquido=Decimal("90.00"),
            margem_disponivel=Decimal("30.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=3,
            taxa_antecipacao=Decimal("0.00"),
            status=Contrato.Status.ATIVO,
            data_contrato=date(2026, 1, 1),
            data_aprovacao=date(2026, 1, 1),
            data_primeira_mensalidade=date(2026, 1, 1),
            admin_manual_layout_enabled=True,
        )
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.APTO_A_RENOVAR,
            valor_total=Decimal("90.00"),
        )
        parcelas = [
            Parcela.objects.create(
                ciclo=ciclo,
                associado=associado,
                numero=index,
                referencia_mes=referencia,
                valor=Decimal("30.00"),
                data_vencimento=referencia,
                status=Parcela.Status.DESCONTADO,
                data_pagamento=referencia,
            )
            for index, referencia in enumerate(
                [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
                start=1,
            )
        ]
        arquivo = ArquivoRetorno.objects.create(
            arquivo_nome="retorno_30.txt",
            arquivo_url="retornos/2026-01.txt",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="SEFAZ",
            competencia=date(2026, 1, 1),
            total_registros=1,
            processados=1,
            status=ArquivoRetorno.Status.CONCLUIDO,
            uploaded_by=self.agente,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor=associado.matricula_orgao,
            nome_servidor=associado.nome_completo,
            competencia="01/2026",
            valor_descontado=Decimal("30.00"),
            associado=associado,
            parcela=parcelas[0],
            processado=True,
            resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA,
        )
        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=self.agente,
            competencia_solicitada=date(2026, 3, 1),
            status=Refinanciamento.Status.APTO_A_RENOVAR,
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2026-01|2026-02|2026-03",
            ref1=date(2026, 1, 1),
            ref2=date(2026, 2, 1),
            ref3=date(2026, 3, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=contrato.codigo,
        )
        return contrato

    def test_repair_removes_imported_small_value_contract_from_apto_flow(self):
        contrato = self._create_imported_small_value_contract()

        before = build_contract_cycle_projection(contrato)
        self.assertEqual(
            before["status_renovacao"],
            "",
            "A projeção já não deve mais expor apto para 30/50 importado.",
        )

        report = repair_small_value_return_renewal_block(apply=True)

        contrato.refresh_from_db()
        projection = build_contract_cycle_projection(contrato)
        self.assertEqual(report["candidate_contract_total"], 1)
        self.assertEqual(report["candidate_apto_after_total"], 0)
        self.assertEqual(projection["status_renovacao"], "")
        self.assertEqual(
            sorted(projection["cycles"], key=lambda item: item["numero"])[0]["status"],
            Ciclo.Status.ABERTO,
        )
        self.assertFalse(
            Refinanciamento.objects.filter(
                contrato_origem=contrato,
                deleted_at__isnull=True,
                origem=Refinanciamento.Origem.OPERACIONAL,
                status=Refinanciamento.Status.APTO_A_RENOVAR,
            ).exists()
        )
