from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.cycle_projection import sync_associado_mother_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Ciclo
from apps.contratos.renovacao import RenovacaoCicloService
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.refinanciamento.services import (
    RefinanciamentoService,
    annotate_renewal_materialization,
    renewal_materialized_q,
)
from apps.relatorios.dashboard_service import AdminDashboardService, DashboardFilters


class Command(BaseCommand):
    help = (
        "Audita e corrige desalinhamentos de renovação entre projeção, "
        "coordenação, tesouraria e dashboard."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção dos refinanciamentos efetivados fantasmas.",
        )
        parser.add_argument(
            "--competencia",
            type=str,
            default=None,
            help="Competência de validação no formato YYYY-MM. Padrão: mês atual.",
        )

    def handle(self, *args, **options):
        competencia = self._parse_competencia(options.get("competencia"))
        ghosts = list(self._ghost_effective_queryset().order_by("-updated_at", "-id"))
        shadowed_aptos = list(
            self._shadowed_apto_queryset().order_by(
                "associado__nome_completo",
                "competencia_solicitada",
                "id",
            )
        )
        historical_materialized = list(
            self._historical_materialized_queryset().order_by(
                "associado__nome_completo",
                "competencia_solicitada",
                "id",
            )
        )

        self.stdout.write(
            self.style.WARNING(
                f"Refinanciamentos efetivados sem materialização: {len(ghosts)}"
            )
        )
        for refinanciamento in ghosts:
            self.stdout.write(
                f"- refi={refinanciamento.id} cpf={refinanciamento.associado.cpf_cnpj} "
                f"nome={refinanciamento.associado.nome_completo} "
                f"competencia={refinanciamento.competencia_solicitada} "
                f"status_atual={refinanciamento.status} "
                f"status_sugerido={self._target_status(refinanciamento)}"
            )

        self.stdout.write(
            self.style.WARNING(
                f"Refinanciamentos aptos ofuscados por etapa posterior na mesma competência: {len(shadowed_aptos)}"
            )
        )
        for refinanciamento in shadowed_aptos[:50]:
            self.stdout.write(
                f"- refi={refinanciamento.id} cpf={refinanciamento.associado.cpf_cnpj} "
                f"nome={refinanciamento.associado.nome_completo} "
                f"competencia={refinanciamento.competencia_solicitada} "
                f"status_atual={refinanciamento.status}"
            )

        self.stdout.write(
            self.style.WARNING(
                "Renovações materializadas fora da seção efetivada da tesouraria: "
                f"{len(historical_materialized)}"
            )
        )
        for refinanciamento in historical_materialized[:50]:
            self.stdout.write(
                f"- refi={refinanciamento.id} cpf={refinanciamento.associado.cpf_cnpj} "
                f"nome={refinanciamento.associado.nome_completo} "
                f"competencia={refinanciamento.competencia_solicitada} "
                f"status_atual={refinanciamento.status}"
            )

        stale_associados, missing_associados = self._audit_apto_status_drift(competencia)
        self.stdout.write(
            self.style.WARNING(
                "Associados com status apto fora da fila real: "
                f"{len(stale_associados)}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Associados aptos na fila real com status persistido divergente: "
                f"{len(missing_associados)}"
            )
        )

        if options.get("apply"):
            affected_associados: set[int] = set()
            for refinanciamento in ghosts:
                target_status = self._target_status(refinanciamento)
                if refinanciamento.status != target_status:
                    refinanciamento.status = target_status
                    refinanciamento.save(update_fields=["status", "updated_at"])
                if refinanciamento.contrato_origem_id:
                    rebuild_contract_cycle_state(refinanciamento.contrato_origem, execute=True)
                affected_associados.add(refinanciamento.associado_id)

            for refinanciamento in shadowed_aptos:
                refinanciamento.deleted_at = timezone.now()
                refinanciamento.save(update_fields=["deleted_at", "updated_at"])
                if refinanciamento.contrato_origem_id:
                    rebuild_contract_cycle_state(refinanciamento.contrato_origem, execute=True)
                affected_associados.add(refinanciamento.associado_id)

            repaired_materialized = 0
            for refinanciamento in historical_materialized:
                if self._repair_materialized_historical_refinanciamento(refinanciamento):
                    repaired_materialized += 1
                    affected_associados.add(refinanciamento.associado_id)

            affected_associados.update(stale_associados)
            affected_associados.update(missing_associados)
            for associado in Associado.objects.filter(id__in=affected_associados):
                sync_associado_mother_status(associado)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Correção aplicada em {len(ghosts)} refinanciamentos e "
                    f"{len(shadowed_aptos)} aptos ofuscados e "
                    f"{repaired_materialized} materializados históricos e "
                    f"{len(affected_associados)} associados."
                )
            )

        self._print_alignment_summary(competencia)

    def _parse_competencia(self, raw_value: str | None) -> date:
        if raw_value:
            return date.fromisoformat(f"{raw_value}-01")
        return timezone.localdate().replace(day=1)

    def _ghost_effective_queryset(self):
        return Refinanciamento.objects.select_related("associado", "contrato_origem").filter(
            deleted_at__isnull=True,
            status=Refinanciamento.Status.EFETIVADO,
            executado_em__isnull=True,
            data_ativacao_ciclo__isnull=True,
            ciclo_destino__isnull=True,
        )

    def _shadowed_apto_queryset(self):
        final_statuses = [
            Refinanciamento.Status.EFETIVADO,
            Refinanciamento.Status.CONCLUIDO,
            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
            Refinanciamento.Status.PENDENTE_TERMO_ANALISTA,
            Refinanciamento.Status.PENDENTE_TERMO_AGENTE,
            Refinanciamento.Status.EM_ANALISE_RENOVACAO,
            Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
            Refinanciamento.Status.BLOQUEADO,
            Refinanciamento.Status.REVERTIDO,
            Refinanciamento.Status.DESATIVADO,
        ]
        shadowed_ids: set[int] = set()
        aptos = list(
            Refinanciamento.objects.select_related("associado", "contrato_origem").filter(
                deleted_at__isnull=True,
                status=Refinanciamento.Status.APTO_A_RENOVAR,
            )
        )
        for refinanciamento in aptos:
            if not refinanciamento.contrato_origem_id:
                continue
            has_newer = Refinanciamento.objects.filter(
                deleted_at__isnull=True,
                contrato_origem_id=refinanciamento.contrato_origem_id,
                competencia_solicitada=refinanciamento.competencia_solicitada,
                status__in=final_statuses,
            ).exclude(id=refinanciamento.id).filter(
                Q(executado_em__isnull=False)
                | Q(data_ativacao_ciclo__isnull=False)
                | Q(ciclo_destino__isnull=False)
                | Q(updated_at__gt=refinanciamento.updated_at)
                | Q(created_at__gt=refinanciamento.created_at)
            )
            if has_newer.exists():
                shadowed_ids.add(refinanciamento.id)
        return Refinanciamento.objects.select_related("associado", "contrato_origem").filter(
            id__in=shadowed_ids
        )

    def _target_status(self, refinanciamento: Refinanciamento) -> str:
        has_coord_progress = bool(
            refinanciamento.aprovado_por_id
            or refinanciamento.reviewed_by_id
            or Comprovante.objects.filter(
                refinanciamento=refinanciamento,
                deleted_at__isnull=True,
                tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            ).exists()
        )
        if has_coord_progress:
            return Refinanciamento.Status.APROVADO_PARA_RENOVACAO
        return Refinanciamento.Status.APTO_A_RENOVAR

    def _historical_materialized_queryset(self):
        cancelados = {
            Refinanciamento.Status.BLOQUEADO,
            Refinanciamento.Status.REVERTIDO,
            Refinanciamento.Status.DESATIVADO,
        }
        return annotate_renewal_materialization(
            Refinanciamento.objects.select_related(
                "associado",
                "contrato_origem",
                "ciclo_origem",
                "ciclo_destino",
            ).filter(deleted_at__isnull=True)
        ).filter(renewal_materialized_q()).exclude(
            status=Refinanciamento.Status.EFETIVADO,
        ).exclude(
            status__in=cancelados,
        )

    def _repair_materialized_historical_refinanciamento(
        self,
        refinanciamento: Refinanciamento,
    ) -> bool:
        contrato = refinanciamento.contrato_origem
        if contrato is None:
            return False

        repaired = False
        payment = RefinanciamentoService._get_renewal_payment(refinanciamento)
        comprovante_associado = RefinanciamentoService._latest_payment_comprovante(
            refinanciamento,
            Comprovante.Papel.ASSOCIADO,
        )
        comprovante_agente = RefinanciamentoService._latest_payment_comprovante(
            refinanciamento,
            Comprovante.Papel.AGENTE,
        )
        effective_dt = (
            refinanciamento.executado_em
            or refinanciamento.data_ativacao_ciclo
            or getattr(payment, "paid_at", None)
            or getattr(comprovante_associado, "data_pagamento", None)
            or getattr(comprovante_agente, "data_pagamento", None)
            or getattr(comprovante_associado, "updated_at", None)
            or getattr(comprovante_agente, "updated_at", None)
        )

        changed_fields: list[str] = []
        if refinanciamento.status != Refinanciamento.Status.EFETIVADO:
            refinanciamento.status = Refinanciamento.Status.EFETIVADO
            changed_fields.append("status")
        if effective_dt is not None and refinanciamento.executado_em is None:
            refinanciamento.executado_em = effective_dt
            changed_fields.append("executado_em")
        if effective_dt is not None and refinanciamento.data_ativacao_ciclo is None:
            refinanciamento.data_ativacao_ciclo = effective_dt
            changed_fields.append("data_ativacao_ciclo")

        if refinanciamento.ciclo_destino_id is None and refinanciamento.ciclo_origem_id is not None:
            if changed_fields:
                refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
                repaired = True
                changed_fields = []
            rebuild_contract_cycle_state(contrato, execute=True)
            refinanciamento.refresh_from_db()
            refinanciamento.ciclo_destino = (
                Ciclo.objects.filter(
                    contrato=contrato,
                    numero=refinanciamento.ciclo_origem.numero + 1,
                    deleted_at__isnull=True,
                )
                .order_by("id")
                .first()
            )
            if refinanciamento.ciclo_destino_id is not None:
                changed_fields.append("ciclo_destino")

        if changed_fields:
            refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
            repaired = True

        if refinanciamento.ciclo_destino_id is not None:
            updated = refinanciamento.comprovantes.filter(deleted_at__isnull=True).exclude(
                ciclo_id=refinanciamento.ciclo_destino_id
            ).update(ciclo=refinanciamento.ciclo_destino)
            repaired = repaired or bool(updated)

        if contrato:
            rebuild_contract_cycle_state(contrato, execute=True)
        return repaired

    def _audit_apto_status_drift(self, competencia: date) -> tuple[set[int], set[int]]:
        queue_rows = RenovacaoCicloService.listar_detalhes(
            competencia=competencia,
            status="apto_a_renovar",
        )
        queue_associado_ids = {
            int(row["associado_id"])
            for row in queue_rows
            if row.get("associado_id") is not None
        }
        persisted_apto_ids = set(
            Associado.objects.filter(status=Associado.Status.APTO_A_RENOVAR).values_list("id", flat=True)
        )
        stale_associados = persisted_apto_ids - queue_associado_ids
        missing_associados = queue_associado_ids - persisted_apto_ids
        return stale_associados, missing_associados

    def _print_alignment_summary(self, competencia: date) -> None:
        current_year = competencia.year
        tesouraria_efetivados = AdminDashboardService._effective_renewal_queryset().filter(
            competencia_solicitada__year=current_year
        )
        coord_base = Refinanciamento.objects.filter(
            deleted_at__isnull=True,
            status__in=[
                Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
                Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                Refinanciamento.Status.EFETIVADO,
                Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
            ],
            competencia_solicitada__year=current_year,
        )
        dashboard_month = next(
            row
            for row in AdminDashboardService.resumo_mensal_associacao(
                DashboardFilters(competencia=competencia)
            )["rows"]
            if row["mes"] == competencia
        )

        self.stdout.write("")
        self.stdout.write(f"Resumo de alinhamento {competencia:%Y-%m}")
        self.stdout.write(
            f"- tesouraria.efetivados_ano={tesouraria_efetivados.count()}"
        )
        self.stdout.write(f"- coordenacao.total_ano={coord_base.count()}")
        self.stdout.write(
            f"- coordenacao.renovados_ano={coord_base.filter(status=Refinanciamento.Status.EFETIVADO).count()}"
        )
        self.stdout.write(
            f"- coordenacao.em_processo_ano={coord_base.exclude(status=Refinanciamento.Status.EFETIVADO).count()}"
        )
        self.stdout.write(
            f"- dashboard.renovacoes_associado_mes={dashboard_month['renovacoes_associado']}"
        )
