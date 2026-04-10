from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.duplicate_billing import (
    audit_duplicate_billing_months,
    repair_duplicate_billing_months,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import BaixaManual


class DuplicateBillingRepairTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = Role.objects.create(codigo="OPERADOR", nome="Operador")
        cls.user = User.objects.create_user(
            email="operador.duplicado@abase.local",
            password="Senha@123",
            first_name="Operador",
            last_name="Duplicado",
            is_active=True,
        )
        cls.user.roles.add(role)

    def _create_associado(self, cpf: str, nome: str) -> Associado:
        return Associado.objects.create(
            nome_completo=nome,
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.user,
        )

    def _create_financial_row(
        self,
        associado: Associado,
        referencia: date,
        *,
        valor: str = "300.00",
        status_code: str = "1",
    ) -> PagamentoMensalidade:
        return PagamentoMensalidade.objects.create(
            created_by=self.user,
            import_uuid=f"{associado.id}-{referencia.isoformat()}-{status_code}",
            referencia_month=referencia,
            status_code=status_code,
            matricula=associado.matricula_orgao or associado.matricula,
            orgao_pagto="SEFAZ",
            nome_relatorio=associado.nome_completo,
            cpf_cnpj=associado.cpf_cnpj,
            associado=associado,
            valor=Decimal(valor),
            source_file_path=f"retornos/{referencia.strftime('%Y-%m')}.txt",
        )

    def _create_cycle(
        self,
        *,
        contrato: Contrato,
        numero: int,
        referencias: list[date],
        status: str,
        parcela_statuses: list[str],
    ) -> Ciclo:
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=numero,
            data_inicio=referencias[0],
            data_fim=referencias[-1],
            status=status,
            valor_total=Decimal("900.00"),
        )
        Parcela.objects.bulk_create(
            [
                Parcela(
                    ciclo=ciclo,
                    associado=contrato.associado,
                    numero=index + 1,
                    referencia_mes=referencia,
                    valor=Decimal("300.00"),
                    data_vencimento=referencia,
                    status=parcela_statuses[index],
                    data_pagamento=referencia if parcela_statuses[index] == Parcela.Status.DESCONTADO else None,
                )
                for index, referencia in enumerate(referencias)
            ]
        )
        return ciclo

    def test_repair_duplicate_billing_months_merges_duplicate_contract_and_rebuilds_primary(self):
        associado = self._create_associado("71339477300", "JEAN DOUGLAS RODRIGUES REIS")
        primary = Contrato.objects.create(
            associado=associado,
            agente=self.user,
            codigo="CTR-20250919170719-2YAMN",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.ATIVO,
            data_contrato=date(2025, 9, 19),
            data_aprovacao=date(2025, 9, 19),
            data_primeira_mensalidade=date(2025, 11, 5),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 9, 19),
        )
        duplicate = Contrato.objects.create(
            associado=associado,
            agente=self.user,
            codigo="CTR-20260114102948-FZJ2I",
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal("300.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_contrato=date(2026, 1, 14),
            data_aprovacao=date(2026, 1, 14),
            data_primeira_mensalidade=date(2026, 2, 1),
        )

        primary_cycle_1 = self._create_cycle(
            contrato=primary,
            numero=1,
            referencias=[date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1)],
            status=Ciclo.Status.CICLO_RENOVADO,
            parcela_statuses=[
                Parcela.Status.NAO_DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )
        primary_cycle_2 = self._create_cycle(
            contrato=primary,
            numero=2,
            referencias=[date(2026, 2, 1), date(2026, 3, 1), date(2026, 4, 1)],
            status=Ciclo.Status.ABERTO,
            parcela_statuses=[
                Parcela.Status.DESCONTADO,
                Parcela.Status.EM_ABERTO,
                Parcela.Status.FUTURO,
            ],
        )
        duplicate_cycle = self._create_cycle(
            contrato=duplicate,
            numero=1,
            referencias=[date(2025, 10, 1), date(2025, 12, 1), date(2026, 1, 1)],
            status=Ciclo.Status.APTO_A_RENOVAR,
            parcela_statuses=[
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )

        Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=primary,
            solicitado_por=self.user,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.EFETIVADO,
            origem=Refinanciamento.Origem.LEGADO,
            legacy_refinanciamento_id=52,
            data_ativacao_ciclo=timezone.make_aware(
                datetime(2026, 1, 16, 14, 45, 56)
            ),
            executado_em=timezone.make_aware(
                datetime(2026, 1, 16, 14, 45, 56)
            ),
            cycle_key="2025-10|2025-11|2025-12",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 11, 1),
            ref3=date(2025, 12, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=primary.codigo,
            ciclo_origem=primary_cycle_1,
            ciclo_destino=primary_cycle_2,
        )
        duplicate_refi = Refinanciamento.objects.create(
            associado=associado,
            contrato_origem=duplicate,
            solicitado_por=self.user,
            competencia_solicitada=date(2026, 1, 1),
            status=Refinanciamento.Status.APTO_A_RENOVAR,
            origem=Refinanciamento.Origem.OPERACIONAL,
            cycle_key="2025-10|2025-12|2026-01",
            ref1=date(2025, 10, 1),
            ref2=date(2025, 12, 1),
            ref3=date(2026, 1, 1),
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            nome_snapshot=associado.nome_completo,
            contrato_codigo_origem=duplicate.codigo,
            ciclo_origem=duplicate_cycle,
        )

        for referencia, status_code in [
            (date(2025, 10, 1), "1"),
            (date(2025, 11, 1), "2"),
            (date(2025, 12, 1), "1"),
            (date(2026, 1, 1), "1"),
            (date(2026, 2, 1), "1"),
        ]:
            self._create_financial_row(associado, referencia, status_code=status_code)

        pre_audit = audit_duplicate_billing_months(cpf_cnpj=associado.cpf_cnpj)
        self.assertEqual(pre_audit["summary"]["groups"], 1)
        self.assertEqual(pre_audit["summary"]["duplicate_keys"], 2)

        payload = repair_duplicate_billing_months(cpf_cnpj=associado.cpf_cnpj, execute=True)

        duplicate.refresh_from_db()
        duplicate_refi.refresh_from_db()

        self.assertIsNotNone(duplicate.deleted_at)
        self.assertIsNotNone(duplicate_refi.deleted_at)
        self.assertEqual(payload["summary"]["remaining_duplicate_keys"], 0)
        self.assertEqual(payload["summary"]["remaining_multi_contract_associados"], 0)

        primary_cycles = list(
            Ciclo.objects.filter(contrato=primary).order_by("numero").prefetch_related("parcelas")
        )
        self.assertEqual(len(primary_cycles), 2)
        active_refs = list(
            Parcela.objects.filter(ciclo__contrato=primary)
            .exclude(status=Parcela.Status.CANCELADO)
            .values_list("referencia_mes", flat=True)
        )
        self.assertEqual(len(active_refs), len(set(active_refs)))
        self.assertIn(date(2025, 10, 1), active_refs)
        self.assertIn(date(2025, 12, 1), active_refs)
        self.assertIn(date(2026, 1, 1), active_refs)
        self.assertIn(date(2026, 2, 1), active_refs)

    def test_repair_duplicate_billing_months_keeps_oldest_intra_contract_parcela(self):
        associado = self._create_associado("51601370849", "UBIRAJARA DE SOUSA ROCHA")
        contrato = Contrato.objects.create(
            associado=associado,
            agente=self.user,
            codigo="CTR-20251009134547-V65BR",
            valor_bruto=Decimal("1050.00"),
            valor_liquido=Decimal("1050.00"),
            valor_mensalidade=Decimal("350.00"),
            prazo_meses=3,
            status=Contrato.Status.EM_ANALISE,
            data_contrato=date(2025, 10, 9),
            data_aprovacao=date(2025, 10, 9),
            data_primeira_mensalidade=date(2025, 12, 1),
            mes_averbacao=date(2025, 10, 1),
            auxilio_liberado_em=date(2025, 10, 9),
        )
        ciclo_1 = self._create_cycle(
            contrato=contrato,
            numero=1,
            referencias=[date(2025, 12, 1), date(2026, 2, 1)],
            status=Ciclo.Status.CICLO_RENOVADO,
            parcela_statuses=[
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )
        ciclo_2 = self._create_cycle(
            contrato=contrato,
            numero=2,
            referencias=[date(2026, 2, 1), date(2026, 3, 1)],
            status=Ciclo.Status.APTO_A_RENOVAR,
            parcela_statuses=[
                Parcela.Status.DESCONTADO,
                Parcela.Status.DESCONTADO,
            ],
        )
        antiga = ciclo_1.parcelas.order_by("numero").last()
        mais_nova = ciclo_2.parcelas.order_by("numero").first()
        BaixaManual.objects.create(
            parcela=mais_nova,
            realizado_por=self.user,
            comprovante=SimpleUploadedFile("baixa.pdf", b"ok", content_type="application/pdf"),
            nome_comprovante="baixa.pdf",
            observacao="Baixa lançada na parcela duplicada.",
            valor_pago=Decimal("350.00"),
            data_baixa=date(2026, 4, 1),
        )

        pre_audit = audit_duplicate_billing_months(cpf_cnpj=associado.cpf_cnpj)
        self.assertEqual(pre_audit["summary"]["duplicate_keys"], 1)

        payload = repair_duplicate_billing_months(cpf_cnpj=associado.cpf_cnpj, execute=True)

        antiga.refresh_from_db()
        mais_nova.refresh_from_db()
        baixa = BaixaManual.objects.get()

        self.assertEqual(payload["summary"]["remaining_duplicate_keys"], 0)
        self.assertFalse(payload["repairs"][0]["rebuilt_primary_contract"])
        self.assertIsNone(antiga.deleted_at)
        self.assertIsNotNone(mais_nova.deleted_at)
        self.assertEqual(baixa.parcela_id, antiga.id)
        self.assertIn("Competência consolidada", antiga.observacao)
        projection = build_contract_cycle_projection(contrato)
        projection_refs = [
            parcela["referencia_mes"]
            for cycle in projection["cycles"]
            for parcela in cycle["parcelas"]
        ]
        self.assertEqual(len(projection_refs), len(set(projection_refs)))
