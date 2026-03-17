from __future__ import annotations

from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.financeiro.models import Despesa
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import Confirmacao
from core.business_reference import backfill_business_references


class BusinessReferenceTestCase(TestCase):
    def test_pagamento_mensalidade_prefere_manual_paid_at(self):
        manual_paid_at = timezone.make_aware(datetime(2026, 1, 15, 9, 30))

        pagamento = PagamentoMensalidade.objects.create(
            import_uuid="import-1",
            referencia_month=date(2026, 1, 1),
            cpf_cnpj="12345678900",
            manual_paid_at=manual_paid_at,
        )

        self.assertEqual(pagamento.data_referencia_negocio, manual_paid_at)

    def test_confirmacao_prefere_data_confirmacao(self):
        associado = Associado.objects.create(
            cpf_cnpj="12345678900",
            nome_completo="Associado Teste",
        )
        contrato = Contrato.objects.create(
            associado=associado,
            codigo="CTR-BUSINESS-001",
            data_contrato=date(2026, 1, 1),
            data_aprovacao=date(2026, 1, 1),
        )
        data_confirmacao = timezone.make_aware(datetime(2026, 2, 10, 14, 0))

        confirmacao = Confirmacao.objects.create(
            contrato=contrato,
            tipo=Confirmacao.Tipo.AVERBACAO,
            competencia=date(2026, 2, 1),
            status=Confirmacao.Status.CONFIRMADO,
            data_confirmacao=data_confirmacao,
        )

        self.assertEqual(confirmacao.data_referencia_negocio, data_confirmacao)

    def test_refinanciamento_prefere_executado_em(self):
        associado = Associado.objects.create(
            cpf_cnpj="22345678900",
            nome_completo="Associado Refi",
        )
        user = User.objects.create_user(
            email="refi@example.com",
            password="senha",
            first_name="Refi",
        )
        contrato = Contrato.objects.create(
            associado=associado,
            codigo="CTR-BUSINESS-REFI",
            data_contrato=date(2026, 3, 1),
            data_aprovacao=date(2026, 3, 1),
        )
        executado_em = timezone.make_aware(datetime(2026, 3, 20, 11, 45))

        refinanciamento = Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=contrato,
            solicitado_por=user,
            competencia_solicitada=date(2026, 3, 1),
            executado_em=executado_em,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            cycle_key="2026-03",
            contrato_codigo_origem=contrato.codigo,
        )

        self.assertEqual(refinanciamento.data_referencia_negocio, executado_em)

    def test_backfill_recalcula_data_referencia_negocio(self):
        despesa = Despesa.objects.create(
            categoria="Operacional",
            descricao="Hospedagem",
            valor="199.90",
            data_despesa=date(2026, 4, 10),
            data_pagamento=date(2026, 4, 12),
        )
        Despesa.all_objects.filter(pk=despesa.pk).update(data_referencia_negocio=None)

        result = backfill_business_references([Despesa])

        despesa.refresh_from_db()
        self.assertEqual(result["financeiro.despesa"], 1)
        self.assertEqual(
            despesa.data_referencia_negocio,
            timezone.make_aware(datetime(2026, 4, 12, 0, 0)),
        )
