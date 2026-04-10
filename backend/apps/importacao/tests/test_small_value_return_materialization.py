from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.importacao.small_value_return_materialization import (
    materialize_small_value_return_items,
)

from .base import ImportacaoBaseTestCase


class SmallValueReturnMaterializationTestCase(ImportacaoBaseTestCase):
    def _create_arquivo(self, *, nome: str, competencia: date) -> ArquivoRetorno:
        return ArquivoRetorno.objects.create(
            arquivo_nome=nome,
            arquivo_url=f"arquivos_retorno/{nome}",
            formato=ArquivoRetorno.Formato.TXT,
            orgao_origem="ETIPI/iNETConsig",
            competencia=competencia,
            uploaded_by=self.tesoureiro,
            resultado_resumo={"data_geracao": competencia.strftime("%d/%m/%Y")},
            status=ArquivoRetorno.Status.CONCLUIDO,
        )

    def test_materialize_small_value_items_creates_imported_associado_and_parcelas(self):
        arquivo_outubro = self._create_arquivo(
            nome="retorno_outubro.txt",
            competencia=date(2025, 10, 1),
        )
        arquivo_novembro = self._create_arquivo(
            nome="retorno_novembro.txt",
            competencia=date(2025, 11, 1),
        )
        item_outubro = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_outubro,
            linha_numero=1,
            cpf_cnpj="23993596315",
            matricula_servidor="030759-9",
            nome_servidor="MARIA DE JESUS SANTANA COSTA",
            cargo="-",
            competencia="10/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SEC. EST. ADMIN. E PREVIDEN.",
        )
        item_novembro = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_novembro,
            linha_numero=1,
            cpf_cnpj="23993596315",
            matricula_servidor="030759-9",
            nome_servidor="MARIA DE JESUS SANTANA COSTA",
            cargo="-",
            competencia="11/2025",
            valor_descontado=Decimal("30.00"),
            status_codigo="2",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não descontado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="SEC. EST. ADMIN. E PREVIDEN.",
        )

        report = materialize_small_value_return_items(
            cpf_cnpj="23993596315",
            apply=True,
        )

        associado = Associado.objects.get(cpf_cnpj="23993596315")
        contrato = Contrato.objects.get(associado=associado, valor_mensalidade=Decimal("30.00"))
        parcelas = {
            parcela.referencia_mes: parcela
            for parcela in Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            ).exclude(status=Parcela.Status.CANCELADO)
        }
        item_outubro.refresh_from_db()
        item_novembro.refresh_from_db()

        self.assertEqual(report["summary"]["cpf_total"], 1)
        self.assertEqual(report["summary"]["associados_criados"], 1)
        self.assertEqual(associado.status, Associado.Status.IMPORTADO)
        self.assertEqual(associado.agente_responsavel_id, self.agente.id)
        self.assertTrue(contrato.admin_manual_layout_enabled)
        self.assertEqual(parcelas[date(2025, 10, 1)].status, Parcela.Status.DESCONTADO)
        self.assertEqual(parcelas[date(2025, 11, 1)].status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(item_outubro.associado_id, associado.id)
        self.assertEqual(item_novembro.associado_id, associado.id)
        self.assertEqual(item_outubro.parcela_id, parcelas[date(2025, 10, 1)].id)
        self.assertEqual(item_novembro.parcela_id, parcelas[date(2025, 11, 1)].id)

    def test_command_is_idempotent_and_relinks_item_with_wrong_parcela_value(self):
        associado = Associado.objects.create(
            nome_completo="DIVALDO SOARES LOUREIRO",
            cpf_cnpj="09945431315",
            email="divaldo@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="002795-2",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )
        contrato_principal = Contrato.objects.create(
            associado=associado,
            agente=self.tesoureiro,
            valor_bruto=Decimal("1500.00"),
            valor_liquido=Decimal("1500.00"),
            valor_mensalidade=Decimal("500.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_primeira_mensalidade=date(2025, 12, 1),
            data_aprovacao=date(2025, 11, 20),
        )
        ciclo_principal = Ciclo.objects.create(
            contrato=contrato_principal,
            numero=1,
            data_inicio=date(2025, 12, 1),
            data_fim=date(2026, 2, 1),
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal("1500.00"),
        )
        parcela_errada = Parcela.objects.create(
            ciclo=ciclo_principal,
            associado=associado,
            numero=3,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("500.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 10),
        )
        arquivo_fev = self._create_arquivo(
            nome="retorno_fevereiro.txt",
            competencia=date(2026, 2, 1),
        )
        arquivo_mar = self._create_arquivo(
            nome="retorno_marco.txt",
            competencia=date(2026, 3, 1),
        )
        item_fev = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_fev,
            linha_numero=1,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="002795-2",
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="02/2026",
            valor_descontado=Decimal("30.00"),
            status_codigo="1",
            status_desconto=ArquivoRetornoItem.StatusDesconto.EFETIVADO,
            status_descricao="Lançado e Efetivado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
            associado=associado,
            parcela=parcela_errada,
        )
        item_mar = ArquivoRetornoItem.objects.create(
            arquivo_retorno=arquivo_mar,
            linha_numero=1,
            cpf_cnpj=associado.cpf_cnpj,
            matricula_servidor="002795-2",
            nome_servidor=associado.nome_completo,
            cargo="-",
            competencia="03/2026",
            valor_descontado=Decimal("30.00"),
            status_codigo="2",
            status_desconto=ArquivoRetornoItem.StatusDesconto.REJEITADO,
            status_descricao="Não descontado",
            orgao_codigo="002",
            orgao_pagto_codigo="002",
            orgao_pagto_nome="Órgão Teste",
            associado=associado,
        )

        out = StringIO()
        call_command(
            "materializar_valores_30_50",
            "--cpf",
            associado.cpf_cnpj,
            "--apply",
            stdout=out,
        )
        call_command(
            "materializar_valores_30_50",
            "--cpf",
            associado.cpf_cnpj,
            "--apply",
            stdout=StringIO(),
        )

        dedicated_contracts = Contrato.objects.filter(
            associado=associado,
            valor_mensalidade=Decimal("30.00"),
            admin_manual_layout_enabled=True,
        )
        self.assertEqual(dedicated_contracts.count(), 1)

        dedicated_contract = dedicated_contracts.get()
        dedicated_parcelas = {
            parcela.referencia_mes: parcela
            for parcela in Parcela.all_objects.filter(
                ciclo__contrato=dedicated_contract,
                deleted_at__isnull=True,
            ).exclude(status=Parcela.Status.CANCELADO)
        }
        associado.refresh_from_db()
        item_fev.refresh_from_db()
        item_mar.refresh_from_db()

        self.assertEqual(dedicated_parcelas[date(2026, 2, 1)].valor, Decimal("30.00"))
        self.assertEqual(dedicated_parcelas[date(2026, 2, 1)].status, Parcela.Status.DESCONTADO)
        self.assertEqual(dedicated_parcelas[date(2026, 3, 1)].status, Parcela.Status.NAO_DESCONTADO)
        self.assertEqual(item_fev.parcela_id, dedicated_parcelas[date(2026, 2, 1)].id)
        self.assertEqual(item_mar.parcela_id, dedicated_parcelas[date(2026, 3, 1)].id)
        self.assertEqual(associado.status, Associado.Status.INADIMPLENTE)
        self.assertIn("itens_reconciliados", out.getvalue())

    def test_command_rerun_handles_soft_deleted_reserved_numbers_without_collision(self):
        associado = Associado.objects.create(
            nome_completo="FRANCINEIDE NASCIMENTO SILVA",
            cpf_cnpj="34801383300",
            email="francineide@teste.local",
            telefone="86999999998",
            orgao_publico="Órgão Teste",
            matricula_orgao="000098-1",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            valor_bruto=Decimal("180.00"),
            valor_liquido=Decimal("180.00"),
            valor_mensalidade=Decimal("30.00"),
            prazo_meses=6,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 10, 1),
            data_aprovacao=date(2025, 10, 1),
            data_primeira_mensalidade=date(2025, 10, 1),
            mes_averbacao=date(2025, 10, 1),
            admin_manual_layout_enabled=True,
        )
        ciclo_1 = Ciclo.objects.create(
            contrato=contrato,
            numero=1,
            data_inicio=date(2025, 10, 1),
            data_fim=date(2025, 12, 1),
            status=Ciclo.Status.PENDENCIA,
            valor_total=Decimal("90.00"),
        )
        ciclo_2 = Ciclo.objects.create(
            contrato=contrato,
            numero=2,
            data_inicio=date(2026, 1, 1),
            data_fim=date(2026, 3, 1),
            status=Ciclo.Status.FECHADO,
            valor_total=Decimal("90.00"),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=1,
            referencia_mes=date(2025, 10, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2025, 10, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 10, 1),
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=2,
            referencia_mes=date(2025, 11, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2025, 11, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )
        Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=3,
            referencia_mes=date(2025, 12, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2025, 12, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2025, 12, 1),
        )
        parcela_soft_deleted = Parcela.objects.create(
            ciclo=ciclo_1,
            associado=associado,
            numero=103,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2026, 1, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 1, 1),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=1,
            referencia_mes=date(2026, 1, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2026, 1, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 1, 1),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=2,
            referencia_mes=date(2026, 2, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 1),
        )
        Parcela.objects.create(
            ciclo=ciclo_2,
            associado=associado,
            numero=3,
            referencia_mes=date(2026, 3, 1),
            valor=Decimal("30.00"),
            data_vencimento=date(2026, 3, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 3, 1),
        )
        parcela_soft_deleted.soft_delete()
        Parcela.all_objects.filter(pk=parcela_soft_deleted.pk).update(
            numero=103,
            deleted_at=timezone.now(),
        )

        competencias = [
            (date(2025, 10, 1), "10/2025", "1", ArquivoRetornoItem.StatusDesconto.EFETIVADO),
            (date(2025, 11, 1), "11/2025", "2", ArquivoRetornoItem.StatusDesconto.REJEITADO),
            (date(2025, 12, 1), "12/2025", "1", ArquivoRetornoItem.StatusDesconto.EFETIVADO),
            (date(2026, 1, 1), "01/2026", "1", ArquivoRetornoItem.StatusDesconto.EFETIVADO),
            (date(2026, 2, 1), "02/2026", "1", ArquivoRetornoItem.StatusDesconto.EFETIVADO),
            (date(2026, 3, 1), "03/2026", "1", ArquivoRetornoItem.StatusDesconto.EFETIVADO),
        ]
        for linha_numero, (competencia_data, competencia_texto, status_codigo, status_desconto) in enumerate(
            competencias,
            start=1,
        ):
            arquivo = self._create_arquivo(
                nome=f"retorno_{competencia_texto.replace('/', '_')}.txt",
                competencia=competencia_data,
            )
            ArquivoRetornoItem.objects.create(
                arquivo_retorno=arquivo,
                linha_numero=linha_numero,
                cpf_cnpj=associado.cpf_cnpj,
                matricula_servidor=associado.matricula_orgao,
                nome_servidor=associado.nome_completo,
                cargo="-",
                competencia=competencia_texto,
                valor_descontado=Decimal("30.00"),
                status_codigo=status_codigo,
                status_desconto=status_desconto,
                status_descricao="Lançado e Efetivado"
                if status_codigo == "1"
                else "Não descontado",
                orgao_codigo="002",
                orgao_pagto_codigo="002",
                orgao_pagto_nome="Órgão Teste",
                associado=associado,
            )

        call_command(
            "materializar_valores_30_50",
            "--cpf",
            associado.cpf_cnpj,
            "--apply",
            stdout=StringIO(),
        )

        parcelas = {
            parcela.referencia_mes: parcela
            for parcela in Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            ).exclude(status=Parcela.Status.CANCELADO)
        }

        self.assertEqual(parcelas[date(2025, 11, 1)].numero, 2)
        self.assertEqual(parcelas[date(2025, 11, 1)].status, Parcela.Status.NAO_DESCONTADO)
        self.assertTrue(
            ArquivoRetornoItem.objects.filter(
                cpf_cnpj=associado.cpf_cnpj,
                competencia="11/2025",
                parcela_id=parcelas[date(2025, 11, 1)].id,
            ).exists()
        )
