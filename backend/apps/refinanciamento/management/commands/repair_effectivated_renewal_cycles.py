from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.contratos.cycle_projection import sync_associado_mother_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Ciclo
from apps.refinanciamento.models import Refinanciamento


def _parse_competencia(raw: str | None) -> date | None:
    if not raw:
        return None
    year, month = [int(part) for part in raw.split("-", 1)]
    return date(year, month, 1)


class Command(BaseCommand):
    help = (
        "Audita e corrige renovações efetivadas sem retorno do associado para ativo "
        "ou sem ciclo futuro materializado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            type=str,
            help="Competência no formato YYYY-MM para limitar a auditoria.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção no banco.",
        )

    def handle(self, *args, **options):
        competencia = _parse_competencia(options.get("competencia"))
        apply_changes = bool(options.get("apply"))

        queryset = (
            Refinanciamento.objects.filter(status=Refinanciamento.Status.EFETIVADO)
            .select_related("associado", "contrato_origem", "ciclo_origem", "ciclo_destino")
            .prefetch_related("ciclo_destino__parcelas")
            .order_by("competencia_solicitada", "id")
        )
        if competencia is not None:
            queryset = queryset.filter(competencia_solicitada=competencia)

        audited = 0
        broken = 0
        repaired = 0

        for refinanciamento in queryset:
            audited += 1
            contrato = refinanciamento.contrato_origem
            if contrato is None:
                continue

            cycle_size = get_contract_cycle_size(contrato)
            target_cycle_number = (
                refinanciamento.ciclo_origem.numero + 1
                if refinanciamento.ciclo_origem_id is not None
                else None
            )
            ciclo_destino = refinanciamento.ciclo_destino
            destino_parcelas = (
                ciclo_destino.parcelas.filter(deleted_at__isnull=True).count()
                if ciclo_destino is not None
                else 0
            )
            expected_destino = (
                Ciclo.objects.filter(
                    contrato=contrato,
                    numero=target_cycle_number,
                    deleted_at__isnull=True,
                )
                .order_by("id")
                .first()
                if target_cycle_number is not None
                else None
            )

            if competencia is not None:
                needs_assoc_sync = str(refinanciamento.associado.status or "") != "ativo"
                needs_cycle = (
                    ciclo_destino is None
                    or destino_parcelas < cycle_size
                    or (
                        expected_destino is not None
                        and ciclo_destino is not None
                        and ciclo_destino.id != expected_destino.id
                    )
                )
            else:
                needs_assoc_sync = False
                needs_cycle = ciclo_destino is None

            if not (needs_assoc_sync or needs_cycle):
                continue

            broken += 1
            self.stdout.write(
                f"[BROKEN] refi={refinanciamento.id} cpf={refinanciamento.associado.cpf_cnpj} "
                f"assoc_status={refinanciamento.associado.status} "
                f"ciclo_destino={refinanciamento.ciclo_destino_id} parcelas_destino={destino_parcelas}/{cycle_size}"
            )

            if not apply_changes:
                continue

            rebuild_contract_cycle_state(contrato, execute=True)
            refinanciamento.refresh_from_db()

            if refinanciamento.ciclo_destino_id is None and target_cycle_number is not None:
                refinanciamento.ciclo_destino = (
                    Ciclo.objects.filter(
                        contrato=contrato,
                        numero=target_cycle_number,
                        deleted_at__isnull=True,
                    )
                    .order_by("id")
                    .first()
                )
                if refinanciamento.ciclo_destino_id is not None:
                    refinanciamento.save(update_fields=["ciclo_destino", "updated_at"])

            sync_associado_mother_status(refinanciamento.associado)
            repaired += 1

        self.stdout.write("")
        self.stdout.write(f"Refinanciamentos efetivados auditados: {audited}")
        self.stdout.write(f"Refinanciamentos efetivados com problema: {broken}")
        self.stdout.write(f"Refinanciamentos efetivados reparados: {repaired}")
