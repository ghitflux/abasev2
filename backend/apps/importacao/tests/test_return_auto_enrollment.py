from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.importacao.return_auto_enrollment import ensure_return_parcela

from .base import ImportacaoBaseTestCase


class ReturnAutoEnrollmentGuardTestCase(ImportacaoBaseTestCase):
    def test_ensure_return_parcela_does_not_create_retimp_when_operational_contract_exists(self):
        associado, contrato, _ = self.create_associado_com_contrato(
            cpf="77777777777",
            nome="Associado Canonico",
            competencia_final=date(2025, 5, 1),
        )

        parcela, created = ensure_return_parcela(
            associado=associado,
            competencia=date(2026, 4, 1),
            arquivo_nome="retorno_abril.txt",
            data_geracao=date(2026, 4, 6),
            cpf_cnpj=associado.cpf_cnpj,
            matricula=associado.matricula_orgao or "",
            valor=Decimal("300.00"),
        )

        self.assertIsNone(parcela)
        self.assertFalse(created)
        self.assertEqual(
            Contrato.objects.filter(associado=associado, codigo__startswith="RETIMP-").count(),
            0,
        )
        self.assertEqual(Contrato.objects.filter(associado=associado).count(), 1)

    def test_ensure_return_parcela_does_not_create_retimp_without_existing_contract(self):
        associado = Associado.objects.create(
            nome_completo="Associado Sem Contrato",
            cpf_cnpj="88888888888",
            email="88888888888@teste.local",
            telefone="86999999999",
            orgao_publico="Órgão Teste",
            matricula_orgao="MAT-8888",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.tesoureiro,
        )

        parcela, created = ensure_return_parcela(
            associado=associado,
            competencia=date(2026, 4, 1),
            arquivo_nome="retorno_abril.txt",
            data_geracao=date(2026, 4, 6),
            cpf_cnpj=associado.cpf_cnpj,
            matricula=associado.matricula_orgao or "",
            valor=Decimal("300.00"),
        )

        self.assertIsNone(parcela)
        self.assertFalse(created)
        self.assertEqual(
            Contrato.objects.filter(associado=associado, codigo__startswith="RETIMP-").count(),
            0,
        )
