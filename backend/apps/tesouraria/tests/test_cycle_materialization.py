from __future__ import annotations

import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem
from apps.tesouraria.models import Pagamento
from apps.tesouraria.services import TesourariaService


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TesourariaCycleMaterializationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = Role.objects.create(codigo="TESOUREIRO", nome="Tesoureiro")
        cls.tesoureiro = User.objects.create_user(
            email="tesoureiro.materializacao@abase.local",
            password="Senha@123",
            first_name="Tesoureiro",
            last_name="Materializacao",
            is_active=True,
        )
        cls.tesoureiro.roles.add(role)

    def _create_associado_contrato(self, prazo_meses: int = 3) -> Contrato:
        associado = Associado.objects.create(
            nome_completo="Associado Materialização",
            cpf_cnpj=f"9998887776{prazo_meses}",
            email=f"materializacao-{prazo_meses}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-MAT-{prazo_meses}",
            status=Associado.Status.EM_ANALISE,
        )
        EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.TESOURARIA,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        return Contrato.objects.create(
            associado=associado,
            valor_bruto=Decimal("2000.00"),
            valor_liquido=Decimal("1600.00"),
            valor_mensalidade=Decimal("400.00"),
            prazo_meses=prazo_meses,
            status=Contrato.Status.EM_ANALISE,
        )

    def test_nao_cria_ciclo_no_cadastro_e_materializa_no_pagamento_inicial(self):
        contrato = self._create_associado_contrato(3)
        self.assertEqual(contrato.ciclos.count(), 0)

        TesourariaService.efetivar_contrato(
            contrato.id,
            SimpleUploadedFile("associado.pdf", b"associado", content_type="application/pdf"),
            SimpleUploadedFile("agente.pdf", b"agente", content_type="application/pdf"),
            self.tesoureiro,
        )

        contrato.refresh_from_db()
        ciclo = contrato.ciclos.get(numero=1)
        parcelas = list(ciclo.parcelas.order_by("numero"))

        self.assertEqual(contrato.status, Contrato.Status.ATIVO)
        self.assertEqual(ciclo.status, ciclo.Status.ABERTO)
        self.assertEqual(len(parcelas), 3)
        self.assertEqual(parcelas[0].status, Parcela.Status.EM_ABERTO)
        self.assertEqual(parcelas[1].status, Parcela.Status.FUTURO)
        self.assertEqual(parcelas[2].status, Parcela.Status.FUTURO)
        self.assertTrue(
            Pagamento.objects.filter(cadastro=contrato.associado, contrato_codigo=contrato.codigo).exists()
        )

    def test_materializacao_inicial_respeita_contrato_de_quatro_parcelas(self):
        contrato = self._create_associado_contrato(4)

        TesourariaService.efetivar_contrato(
            contrato.id,
            SimpleUploadedFile("associado.pdf", b"associado", content_type="application/pdf"),
            SimpleUploadedFile("agente.pdf", b"agente", content_type="application/pdf"),
            self.tesoureiro,
        )

        contrato.refresh_from_db()
        ciclo = contrato.ciclos.get(numero=1)
        parcelas = list(ciclo.parcelas.order_by("numero"))

        self.assertEqual(len(parcelas), 4)
        self.assertEqual(
            [parcela.status for parcela in parcelas],
            [
                Parcela.Status.EM_ABERTO,
                Parcela.Status.FUTURO,
                Parcela.Status.FUTURO,
                Parcela.Status.FUTURO,
            ],
        )
