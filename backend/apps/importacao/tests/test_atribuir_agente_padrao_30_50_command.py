from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command

from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.importacao.models import ArquivoRetornoItem
from apps.accounts.models import User

from .base import ImportacaoBaseTestCase


class AtribuirAgentePadrao3050CommandTestCase(ImportacaoBaseTestCase):
    def _run_command(self, *args: str) -> str:
        stdout = StringIO()
        call_command("atribuir_agente_padrao_30_50", *args, stdout=stdout)
        return stdout.getvalue()

    def test_dry_run_lista_associados_sem_agente_de_30_50(self):
        agente_padrao = User.objects.create_user(
            email="agente@abase.com",
            password="Senha@123",
            first_name="Agente",
            last_name="Padrão",
            is_active=True,
        )
        agente_padrao.roles.add(self.role_agente)

        arquivo = self.create_arquivo_retorno(nome="retorno_30_50.txt")
        associado_retorno = Associado.objects.create(
            nome_completo="Associado Retorno",
            cpf_cnpj="11111111111",
            email="retorno@teste.local",
            telefone="86999999999",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-RET",
            status=Associado.Status.ATIVO,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj=associado_retorno.cpf_cnpj,
            matricula_servidor=associado_retorno.matricula_orgao,
            nome_servidor=associado_retorno.nome_completo,
            cargo="-",
            competencia="10/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="2",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não descontado",
            orgao_codigo="001",
            orgao_pagto_codigo="001",
            orgao_pagto_nome="SEDUC",
        )

        associado_contrato = Associado.objects.create(
            nome_completo="Associado Contrato",
            cpf_cnpj="22222222222",
            email="contrato@teste.local",
            telefone="86999999998",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-CON",
            status=Associado.Status.ATIVO,
        )
        Contrato.objects.create(
            associado=associado_contrato,
            agente=self.tesoureiro,
            valor_bruto=Decimal("150.00"),
            valor_liquido=Decimal("150.00"),
            valor_mensalidade=Decimal("50.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
        )

        output = self._run_command()

        associado_retorno.refresh_from_db()
        associado_contrato.refresh_from_db()
        self.assertIsNone(associado_retorno.agente_responsavel_id)
        self.assertIsNone(associado_contrato.agente_responsavel_id)
        self.assertEqual(agente_padrao.email, "agente@abase.com")
        self.assertIn("modo: dry-run", output)
        self.assertIn("associado_total: 2", output)
        self.assertIn(associado_retorno.cpf_cnpj, output)
        self.assertIn(associado_contrato.cpf_cnpj, output)

    def test_apply_atribui_agente_padrao_aos_associados_sem_agente(self):
        agente_padrao = User.objects.create_user(
            email="agente@abase.com",
            password="Senha@123",
            first_name="Agente",
            last_name="Padrão",
            is_active=True,
        )
        agente_padrao.roles.add(self.role_agente)

        arquivo = self.create_arquivo_retorno(nome="retorno_30.txt")
        associado = Associado.objects.create(
            nome_completo="Associado Sem Agente",
            cpf_cnpj="33333333333",
            email="semagente@teste.local",
            telefone="86999999997",
            orgao_publico="SEDUC",
            matricula_orgao="MAT-SEM",
            status=Associado.Status.ATIVO,
        )
        ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo,
            linha_numero=1,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor=associado.matricula_orgao,
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="11/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="001",
            orgao_pagto_codigo="001",
            orgao_pagto_nome="SEDUC",
        )

        output = self._run_command("--apply")

        associado.refresh_from_db()
        self.assertEqual(associado.agente_responsavel_id, agente_padrao.id)
        self.assertIn("modo: apply", output)
        self.assertIn("associado_total: 1", output)
