from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    sync_associado_mother_status,
)
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state, relink_contract_documents
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Ciclo, Parcela
from apps.refinanciamento.models import Refinanciamento


def _parse_competencia(raw: str | None) -> date:
    if not raw:
        return date(2026, 4, 1)
    year, month = [int(part) for part in raw.split("-", 1)]
    return date(year, month, 1)


def _report_path(prefix: str = "repair_april_effectivated_cycle_materialization") -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return Path(settings.BASE_DIR) / "media" / "relatorios" / f"{prefix}_{timestamp}.json"


def _cycle_rows(ciclo: Ciclo | None) -> list[tuple[str, str]]:
    if ciclo is None:
        return []
    return [
        (parcela.referencia_mes.isoformat(), str(parcela.status))
        for parcela in Parcela.objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("numero", "id")
    ]


def _projection_rows(cycle: dict[str, object] | None) -> list[tuple[str, str]]:
    if not cycle:
        return []
    return [
        (parcela["referencia_mes"].isoformat(), str(parcela["status"]))
        for parcela in cycle["parcelas"]
    ]


def _find_projected_cycle(
    projection: dict[str, object],
    cycle_number: int | None,
) -> dict[str, object] | None:
    if cycle_number is None:
        return None
    return next(
        (
            cycle
            for cycle in projection.get("cycles", [])
            if int(cycle.get("numero") or 0) == cycle_number
        ),
        None,
    )


@dataclass
class RepairSnapshot:
    current_cycle_number: int | None
    current_cycle_status: str | None
    current_cycle_rows: list[tuple[str, str]]
    next_cycle_number: int | None
    next_cycle_status: str | None
    next_cycle_rows: list[tuple[str, str]]
    unresolved_unpaid: list[tuple[str, str]]


def _snapshot(
    refinanciamento: Refinanciamento,
    *,
    projection: dict[str, object] | None = None,
) -> RepairSnapshot:
    contrato = refinanciamento.contrato_origem
    current_cycle_number = (
        refinanciamento.ciclo_origem.numero
        if refinanciamento.ciclo_origem_id is not None
        else None
    )
    next_cycle_number = current_cycle_number + 1 if current_cycle_number is not None else None
    projection = projection or build_contract_cycle_projection(contrato)
    current_projected = _find_projected_cycle(projection, current_cycle_number)
    next_projected = _find_projected_cycle(projection, next_cycle_number)
    current_cycle = (
        Ciclo.objects.filter(
            contrato=contrato,
            numero=current_cycle_number,
            deleted_at__isnull=True,
        )
        .order_by("id")
        .first()
        if current_cycle_number is not None
        else None
    )
    next_cycle = (
        Ciclo.objects.filter(
            contrato=contrato,
            numero=next_cycle_number,
            deleted_at__isnull=True,
        )
        .order_by("id")
        .first()
        if next_cycle_number is not None
        else None
    )
    return RepairSnapshot(
        current_cycle_number=current_cycle_number,
        current_cycle_status=(
            str(current_cycle.status)
            if current_cycle is not None
            else str(current_projected.get("status") or "") if current_projected else None
        ),
        current_cycle_rows=_cycle_rows(current_cycle),
        next_cycle_number=next_cycle_number,
        next_cycle_status=(
            str(next_cycle.status)
            if next_cycle is not None
            else str(next_projected.get("status") or "") if next_projected else None
        ),
        next_cycle_rows=_cycle_rows(next_cycle),
        unresolved_unpaid=[
            (row["referencia_mes"].isoformat(), str(row["status"]))
            for row in projection.get("unpaid_months", [])
            if str(row.get("status") or "") not in {"quitada", "descontado", "liquidada"}
        ],
    )


class Command(BaseCommand):
    help = (
        "Audita e corrige a materialização dos ciclos dos refinanciamentos "
        "efetivados em abril/2026."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            type=str,
            default="2026-04",
            help="Competência no formato YYYY-MM. Padrão: 2026-04.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção no banco.",
        )
        parser.add_argument(
            "--report-path",
            type=str,
            help="Caminho opcional do relatório JSON.",
        )

    def handle(self, *args, **options):
        competencia = _parse_competencia(options.get("competencia"))
        apply_changes = bool(options.get("apply"))
        target_reference = competencia.replace(day=1)
        report_path = Path(options["report_path"]) if options.get("report_path") else _report_path()

        queryset = (
            Refinanciamento.objects.filter(
                status=Refinanciamento.Status.EFETIVADO,
                competencia_solicitada=competencia,
            )
            .select_related("associado", "contrato_origem", "ciclo_origem", "ciclo_destino")
            .order_by("id")
        )

        audited = 0
        broken = 0
        repaired = 0
        report_rows: list[dict[str, object]] = []

        for refinanciamento in queryset:
            contrato = refinanciamento.contrato_origem or resolve_operational_contract_for_associado(
                refinanciamento.associado
            )
            if contrato is None:
                continue

            audited += 1
            projection = build_contract_cycle_projection(contrato)
            cycle_size = get_contract_cycle_size(contrato)
            current_cycle_number = (
                refinanciamento.ciclo_origem.numero
                if refinanciamento.ciclo_origem_id is not None
                else None
            )
            next_cycle_number = current_cycle_number + 1 if current_cycle_number is not None else None
            current_cycle = (
                Ciclo.objects.filter(
                    contrato=contrato,
                    numero=current_cycle_number,
                    deleted_at__isnull=True,
                )
                .order_by("id")
                .first()
                if current_cycle_number is not None
                else None
            )
            next_cycle = (
                Ciclo.objects.filter(
                    contrato=contrato,
                    numero=next_cycle_number,
                    deleted_at__isnull=True,
                )
                .order_by("id")
                .first()
                if next_cycle_number is not None
                else None
            )
            projected_current = _find_projected_cycle(projection, current_cycle_number)
            projected_next = _find_projected_cycle(projection, next_cycle_number)
            current_rows = _cycle_rows(current_cycle)
            next_rows = _cycle_rows(next_cycle)
            projected_current_rows = _projection_rows(projected_current)
            projected_next_rows = _projection_rows(projected_next)
            unresolved_unpaid = [
                (row["referencia_mes"].isoformat(), str(row["status"]))
                for row in projection.get("unpaid_months", [])
                if str(row.get("status") or "") not in {"quitada", "descontado", "liquidada"}
            ]

            reasons: list[str] = []
            if projected_current is None or current_cycle is None:
                reasons.append("current_cycle_missing")
            else:
                if len(current_rows) != cycle_size:
                    reasons.append("current_cycle_wrong_size")
                if current_rows != projected_current_rows:
                    reasons.append("current_cycle_rows_mismatch")
                if str(current_cycle.status) != str(projected_current.get("status") or ""):
                    reasons.append("current_cycle_status_mismatch")
            if projected_next is None or next_cycle is None:
                reasons.append("next_cycle_missing")
            else:
                if len(next_rows) != cycle_size:
                    reasons.append("next_cycle_wrong_size")
                if next_rows != projected_next_rows:
                    reasons.append("next_cycle_rows_mismatch")
                if str(next_cycle.status) != str(projected_next.get("status") or ""):
                    reasons.append("next_cycle_status_mismatch")
            if any(reference == target_reference.isoformat() for reference, _ in unresolved_unpaid):
                reasons.append("target_reference_outside_cycle")

            before = _snapshot(refinanciamento, projection=projection)
            row = {
                "refinanciamento_id": refinanciamento.id,
                "cpf": refinanciamento.associado.cpf_cnpj,
                "nome": refinanciamento.associado.nome_completo,
                "contrato_codigo": contrato.codigo,
                "cycle_size": cycle_size,
                "broken": bool(reasons),
                "reasons": reasons,
                "before": asdict(before),
            }

            if reasons:
                broken += 1
                self.stdout.write(
                    f"[BROKEN] refi={refinanciamento.id} cpf={refinanciamento.associado.cpf_cnpj} "
                    f"contrato={contrato.codigo} reasons={','.join(reasons)}"
                )
                if apply_changes:
                    rebuild_contract_cycle_state(contrato, execute=True)
                    relink_contract_documents({contrato.id})
                    sync_associado_mother_status(contrato.associado)
                    refinanciamento.refresh_from_db()
                    repaired += 1
                    row["after"] = asdict(_snapshot(refinanciamento))
            report_rows.append(row)

        report_payload = {
            "competencia": competencia.isoformat(),
            "audited": audited,
            "broken": broken,
            "repaired": repaired,
            "rows": report_rows,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report_payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write("")
        self.stdout.write(f"Competência auditada: {competencia.isoformat()}")
        self.stdout.write(f"Refinanciamentos auditados: {audited}")
        self.stdout.write(f"Refinanciamentos com problema: {broken}")
        self.stdout.write(f"Refinanciamentos reparados: {repaired}")
        self.stdout.write(f"Relatório: {report_path}")
