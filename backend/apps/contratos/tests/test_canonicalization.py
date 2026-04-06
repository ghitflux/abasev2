from __future__ import annotations

import json
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Role, User
from apps.associados.models import Associado
from apps.contratos.canonicalization import (
    operational_contracts_queryset,
    resolve_canonical_contract,
)
from apps.contratos.competencia import resolve_processing_competencia_parcela
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_associado_visual_status_payload,
    get_contract_visual_status_payload,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.tesouraria.services import BaixaManualService


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ContractCanonicalizationTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        role, _ = Role.objects.get_or_create(codigo="AGENTE", defaults={"nome": "Agente"})
        cls.agente = User.objects.create_user(
            email="agente.canonical@abase.local",
            password="Senha@123",
            first_name="Agente",
            last_name="Canonical",
            is_active=True,
        )
        cls.agente.roles.add(role)

    def _create_associado(self, cpf: str, nome: str | None = None) -> Associado:
        return Associado.objects.create(
            nome_completo=nome or f"Associado {cpf[-4:]}",
            cpf_cnpj=cpf,
            email=f"{cpf}@teste.local",
            telefone="86999999999",
            orgao_publico="SEFAZ",
            matricula_orgao=f"MAT-{cpf[-4:]}",
            status=Associado.Status.ATIVO,
            agente_responsavel=self.agente,
        )

    def _create_contrato(
        self,
        *,
        associado: Associado,
        codigo: str,
        status: str = Contrato.Status.ATIVO,
        valor_mensalidade: str = "300.00",
        data_base: date = date(2026, 1, 1),
        efetivo: bool = True,
    ) -> Contrato:
        return Contrato.objects.create(
            associado=associado,
            agente=self.agente,
            codigo=codigo,
            valor_bruto=Decimal("900.00"),
            valor_liquido=Decimal("900.00"),
            valor_mensalidade=Decimal(valor_mensalidade),
            prazo_meses=3,
            status=status,
            data_contrato=data_base,
            data_aprovacao=data_base if efetivo else None,
            data_primeira_mensalidade=data_base if efetivo else None,
            mes_averbacao=data_base if efetivo else None,
            auxilio_liberado_em=data_base if efetivo else None,
        )

    def _create_cycle_with_parcela(
        self,
        *,
        contrato: Contrato,
        referencia: date,
        status: str,
        numero: int = 1,
        valor: str = "300.00",
        data_pagamento: date | None = None,
    ) -> Parcela:
        ciclo = Ciclo.objects.create(
            contrato=contrato,
            numero=numero,
            data_inicio=referencia,
            data_fim=referencia,
            status=Ciclo.Status.ABERTO,
            valor_total=Decimal(valor),
        )
        return Parcela.objects.create(
            ciclo=ciclo,
            associado=contrato.associado,
            numero=1,
            referencia_mes=referencia,
            valor=Decimal(valor),
            data_vencimento=referencia,
            status=status,
            data_pagamento=data_pagamento,
        )

    def test_resolve_canonical_contract_prefers_active_ctr_over_retimp(self):
        associado = self._create_associado("05201186343", nome="MARCIANITA MICHELE RAMOS MENDES")
        ctr = self._create_contrato(
            associado=associado,
            codigo="CTR-20260101-AAA111",
            status=Contrato.Status.ATIVO,
        )
        self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-AAA111",
            status=Contrato.Status.ATIVO,
        )

        canonical = resolve_canonical_contract(associado)

        self.assertEqual(canonical.id, ctr.id)

    def test_resolve_canonical_contract_prefers_effective_ctr_in_triple_case(self):
        associado = self._create_associado("11111111111")
        ctr_canonico = self._create_contrato(
            associado=associado,
            codigo="CTR-ATIVO-1111",
            status=Contrato.Status.ATIVO,
            data_base=date(2026, 1, 1),
            efetivo=True,
        )
        self._create_cycle_with_parcela(
            contrato=ctr_canonico,
            referencia=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )
        self._create_contrato(
            associado=associado,
            codigo="CTR-ANALISE-1111",
            status=Contrato.Status.EM_ANALISE,
            data_base=date(2026, 3, 1),
            efetivo=False,
        )
        self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-1111",
            status=Contrato.Status.ATIVO,
            data_base=date(2026, 4, 1),
            efetivo=False,
        )

        canonical = resolve_canonical_contract(associado)

        self.assertEqual(canonical.id, ctr_canonico.id)

    def test_resolve_canonical_contract_is_stable_for_retimp_only_group(self):
        associado = self._create_associado("22222222222")
        retimp_sem_progresso = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-2222-A",
            data_base=date(2026, 2, 1),
            efetivo=False,
        )
        retimp_com_pagamento = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-2222-B",
            data_base=date(2026, 3, 1),
            efetivo=False,
        )
        self._create_cycle_with_parcela(
            contrato=retimp_com_pagamento,
            referencia=date(2026, 3, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 3, 5),
        )

        canonical = resolve_canonical_contract(associado)

        self.assertNotEqual(canonical.id, retimp_sem_progresso.id)
        self.assertEqual(canonical.id, retimp_com_pagamento.id)

    def test_command_dry_run_and_apply_mark_shadow_contracts(self):
        associado = self._create_associado("33333333333")
        canonical = self._create_contrato(
            associado=associado,
            codigo="CTR-20260101-333333",
        )
        shadow = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-3333",
            efetivo=False,
        )

        report_dir = Path(tempfile.mkdtemp())
        dry_run_path = report_dir / "dry-run.json"
        apply_path = report_dir / "apply.json"

        call_command(
            "canonicalizar_contratos_duplicados",
            "--cpf",
            associado.cpf_cnpj,
            "--report-path",
            str(dry_run_path),
        )

        shadow.refresh_from_db()
        self.assertIsNone(shadow.contrato_canonico_id)
        dry_run_payload = json.loads(dry_run_path.read_text(encoding="utf-8"))
        self.assertEqual(dry_run_payload["summary"]["groups"], 1)
        self.assertEqual(dry_run_payload["summary"]["changed_contracts"], 1)

        call_command(
            "canonicalizar_contratos_duplicados",
            "--cpf",
            associado.cpf_cnpj,
            "--apply",
            "--report-path",
            str(apply_path),
        )

        canonical.refresh_from_db()
        shadow.refresh_from_db()
        self.assertIsNone(canonical.contrato_canonico_id)
        self.assertEqual(shadow.contrato_canonico_id, canonical.id)
        self.assertEqual(shadow.tipo_unificacao, Contrato.TipoUnificacao.RETIMP_SHADOW)
        self.assertIsNotNone(shadow.unificado_em)
        self.assertEqual(
            list(
                operational_contracts_queryset(
                    Contrato.objects.filter(associado=associado)
                ).values_list("id", flat=True)
            ),
            [canonical.id],
        )

    def test_get_associado_visual_status_payload_ignores_duplicate_shadow_logic(self):
        associado = self._create_associado("44444444444")
        canonical = self._create_contrato(
            associado=associado,
            codigo="CTR-20260101-444444",
        )
        duplicate = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-4444",
            efetivo=False,
        )
        self._create_cycle_with_parcela(
            contrato=canonical,
            referencia=date(2026, 2, 1),
            status=Parcela.Status.DESCONTADO,
            data_pagamento=date(2026, 2, 5),
        )
        self._create_cycle_with_parcela(
            contrato=duplicate,
            referencia=date(2026, 2, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )

        expected = get_contract_visual_status_payload(
            canonical,
            projection=build_contract_cycle_projection(canonical),
        )
        payload = get_associado_visual_status_payload(associado)

        self.assertEqual(payload["status_visual_slug"], expected["status_visual_slug"])
        self.assertEqual(payload["status_visual_label"], expected["status_visual_label"])

    def test_resolve_processing_competencia_parcela_prefers_non_shadow_contract(self):
        associado = self._create_associado("55555555555")
        canonical = self._create_contrato(
            associado=associado,
            codigo="CTR-20260101-555555",
        )
        shadow = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-5555",
            efetivo=False,
        )
        parcela_canonica = self._create_cycle_with_parcela(
            contrato=canonical,
            referencia=date(2026, 3, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )
        shadow.contrato_canonico = canonical
        shadow.tipo_unificacao = Contrato.TipoUnificacao.RETIMP_SHADOW
        shadow.unificado_em = parcela_canonica.created_at
        shadow.save(update_fields=["contrato_canonico", "tipo_unificacao", "unificado_em", "updated_at"])
        parcela_sombra = self._create_cycle_with_parcela(
            contrato=shadow,
            referencia=date(2026, 3, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )

        resolved = resolve_processing_competencia_parcela(
            associado_id=associado.id,
            referencia_mes=date(2026, 3, 1),
        )

        self.assertEqual(resolved.id, parcela_canonica.id)
        self.assertNotEqual(resolved.id, parcela_sombra.id)

    def test_baixa_manual_service_ignores_shadow_duplicate_parcelas(self):
        associado = self._create_associado("66666666666")
        canonical = self._create_contrato(
            associado=associado,
            codigo="CTR-20260101-666666",
        )
        shadow = self._create_contrato(
            associado=associado,
            codigo="RETIMP-202603-MAT-6666",
            efetivo=False,
        )
        parcela_canonica = self._create_cycle_with_parcela(
            contrato=canonical,
            referencia=date(2026, 3, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )
        shadow.contrato_canonico = canonical
        shadow.tipo_unificacao = Contrato.TipoUnificacao.RETIMP_SHADOW
        shadow.unificado_em = parcela_canonica.created_at
        shadow.save(update_fields=["contrato_canonico", "tipo_unificacao", "unificado_em", "updated_at"])
        self._create_cycle_with_parcela(
            contrato=shadow,
            referencia=date(2026, 3, 1),
            status=Parcela.Status.NAO_DESCONTADO,
        )

        with mock.patch("apps.tesouraria.services.timezone.localdate", return_value=date(2026, 4, 6)):
            parcelas = list(BaixaManualService.listar_parcelas_pendentes())
            kpis = BaixaManualService.kpis()

        self.assertEqual([parcela.id for parcela in parcelas], [parcela_canonica.id])
        self.assertEqual(kpis["total_pendentes"], 1)
        self.assertEqual(kpis["nao_descontado"], 1)
