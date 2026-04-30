from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    sync_associado_mother_status,
)
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state, relink_contract_documents
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.refinanciamento.models import Refinanciamento
from apps.refinanciamento.services import annotate_renewal_materialization


def _parse_competencia(raw: str | None) -> date:
    if not raw:
        return date(2026, 4, 1)
    year, month = [int(part) for part in raw.split("-", 1)]
    return date(year, month, 1)


def _parse_iso_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return date.fromisoformat(raw)


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def _to_local_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()
    return value


def _effective_datetime(refinanciamento: Refinanciamento) -> datetime | date | None:
    return (
        refinanciamento.data_ativacao_ciclo
        or refinanciamento.executado_em
        or getattr(refinanciamento, "linked_payment_paid_at", None)
        or getattr(refinanciamento, "associado_payment_proof_paid_at", None)
        or getattr(refinanciamento, "agente_payment_proof_paid_at", None)
        or refinanciamento.updated_at
        or refinanciamento.created_at
    )


def _renewal_origin_references(refinanciamento: Refinanciamento) -> list[date]:
    explicit_refs = [
        value.replace(day=1)
        for value in [
            refinanciamento.ref1,
            refinanciamento.ref2,
            refinanciamento.ref3,
            refinanciamento.ref4,
        ]
        if value is not None
    ]
    if explicit_refs:
        return sorted(explicit_refs)
    if refinanciamento.ciclo_origem_id is None:
        return []
    return [
        parcela.referencia_mes.replace(day=1)
        for parcela in Parcela.objects.filter(
            ciclo=refinanciamento.ciclo_origem,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "numero", "id")
        if parcela.referencia_mes is not None
    ]


def _destination_start_reference(
    refinanciamento: Refinanciamento,
    *,
    cycle_size: int,
    effective_at: datetime | date | None,
) -> date:
    activation_date = _to_local_date(effective_at) or timezone.localdate()
    activation_reference = activation_date.replace(day=1)
    origin_refs = _renewal_origin_references(refinanciamento)
    if not origin_refs:
        return activation_reference

    next_reference = _add_months(origin_refs[-1], 1)
    if (
        len(origin_refs) >= max(cycle_size - 1, 1)
        and activation_reference == next_reference
    ):
        return _add_months(next_reference, 1)
    return next_reference


def _ensure_effectivation_fields(
    refinanciamento: Refinanciamento,
    *,
    effective_at: datetime | date | None,
) -> bool:
    changed_fields: list[str] = []
    if refinanciamento.status != Refinanciamento.Status.EFETIVADO:
        refinanciamento.status = Refinanciamento.Status.EFETIVADO
        changed_fields.append("status")
    if isinstance(effective_at, date) and not isinstance(effective_at, datetime):
        effective_at = timezone.make_aware(datetime.combine(effective_at, datetime.min.time()))
    if effective_at is not None and refinanciamento.executado_em is None:
        refinanciamento.executado_em = effective_at
        changed_fields.append("executado_em")
    if effective_at is not None and refinanciamento.data_ativacao_ciclo is None:
        refinanciamento.data_ativacao_ciclo = effective_at
        changed_fields.append("data_ativacao_ciclo")
    if changed_fields:
        refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
        return True
    return False


def _ensure_destination_cycle(
    refinanciamento: Refinanciamento,
    *,
    cycle_size: int,
    effective_at: datetime | date | None,
) -> bool:
    contrato = refinanciamento.contrato_origem
    if contrato is None:
        return False

    target_number = (
        refinanciamento.ciclo_origem.numero + 1
        if refinanciamento.ciclo_origem_id is not None
        else (
            Ciclo.objects.filter(contrato=contrato, deleted_at__isnull=True)
            .order_by("-numero")
            .values_list("numero", flat=True)
            .first()
            or 0
        )
        + 1
    )
    start_reference = _destination_start_reference(
        refinanciamento,
        cycle_size=cycle_size,
        effective_at=effective_at,
    )
    end_reference = _add_months(start_reference, cycle_size - 1)
    valor_total = ((contrato.valor_mensalidade or Decimal("0")) * cycle_size).quantize(
        Decimal("0.01")
    )

    changed = False
    destino = (
        Ciclo.all_objects.filter(contrato=contrato, numero=target_number)
        .order_by("deleted_at", "id")
        .first()
    )
    if destino is None:
        destino = Ciclo.objects.create(
            contrato=contrato,
            numero=target_number,
            data_inicio=start_reference,
            data_fim=end_reference,
            status=Ciclo.Status.ABERTO,
            valor_total=valor_total,
        )
        changed = True
    else:
        cycle_changed_fields: list[str] = []
        for field, value in {
            "deleted_at": None,
            "data_inicio": start_reference,
            "data_fim": end_reference,
            "status": Ciclo.Status.ABERTO,
            "valor_total": valor_total,
        }.items():
            if getattr(destino, field) != value:
                setattr(destino, field, value)
                cycle_changed_fields.append(field)
        if cycle_changed_fields:
            destino.save(update_fields=[*cycle_changed_fields, "updated_at"])
            changed = True

    for offset in range(cycle_size):
        reference = _add_months(start_reference, offset)
        parcela, created = Parcela.all_objects.update_or_create(
            ciclo=destino,
            numero=offset + 1,
            defaults={
                "associado": contrato.associado,
                "referencia_mes": reference,
                "valor": contrato.valor_mensalidade or Decimal("0"),
                "data_vencimento": reference,
                "status": Parcela.Status.EM_PREVISAO,
                "data_pagamento": None,
                "observacao": "",
                "layout_bucket": Parcela.LayoutBucket.CYCLE,
                "deleted_at": None,
            },
        )
        changed = changed or created or parcela.deleted_at is not None

    changed_fields: list[str] = []
    if refinanciamento.ciclo_destino_id != destino.id:
        refinanciamento.ciclo_destino = destino
        changed_fields.append("ciclo_destino")
    if refinanciamento.ciclo_origem_id and refinanciamento.ciclo_origem.status != Ciclo.Status.CICLO_RENOVADO:
        refinanciamento.ciclo_origem.status = Ciclo.Status.CICLO_RENOVADO
        refinanciamento.ciclo_origem.save(update_fields=["status", "updated_at"])
        changed = True
    if changed_fields:
        refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
        changed = True
    return changed


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
        "efetivados em abril/2026 ou em uma janela operacional informada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            type=str,
            help=(
                "Competência no formato YYYY-MM. Se não informar start/end, "
                "o padrão operacional continua 2026-04."
            ),
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Data inicial efetiva da renovação no formato YYYY-MM-DD.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            help="Data final efetiva da renovação no formato YYYY-MM-DD.",
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
        start_date = _parse_iso_date(options.get("start_date"))
        end_date = _parse_iso_date(options.get("end_date"))
        if start_date and end_date and start_date > end_date:
            raise ValueError("--start-date não pode ser maior que --end-date.")

        competencia_raw = options.get("competencia")
        should_default_competencia = not competencia_raw and not start_date and not end_date
        competencia = (
            _parse_competencia(competencia_raw if competencia_raw else "2026-04")
            if competencia_raw or should_default_competencia
            else None
        )
        apply_changes = bool(options.get("apply"))
        target_reference = competencia.replace(day=1) if competencia is not None else None
        report_path = Path(options["report_path"]) if options.get("report_path") else _report_path()

        queryset = (
            Refinanciamento.objects.filter(
                status=Refinanciamento.Status.EFETIVADO,
            )
            .select_related("associado", "contrato_origem", "ciclo_origem", "ciclo_destino")
            .order_by("id")
        )
        if competencia is not None:
            queryset = queryset.filter(competencia_solicitada=competencia)
        if start_date is not None or end_date is not None:
            queryset = annotate_renewal_materialization(queryset)

        audited = 0
        broken = 0
        repaired = 0
        report_rows: list[dict[str, object]] = []

        for refinanciamento in queryset:
            effective_at = _effective_datetime(refinanciamento)
            effective_date = _to_local_date(effective_at)
            if start_date is not None and (effective_date is None or effective_date < start_date):
                continue
            if end_date is not None and (effective_date is None or effective_date > end_date):
                continue

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

            is_inactive_contract = contrato.status in {
                Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO
            }
            reasons: list[str] = []
            if projected_current is None or current_cycle is None:
                reasons.append("current_cycle_missing")
            else:
                if len(current_rows) != cycle_size and len(projected_current_rows) == cycle_size:
                    reasons.append("current_cycle_wrong_size")
                if current_rows != projected_current_rows:
                    reasons.append("current_cycle_rows_mismatch")
                if str(current_cycle.status) != str(projected_current.get("status") or ""):
                    reasons.append("current_cycle_status_mismatch")
            if is_inactive_contract:
                # Para contratos cancelados/encerrados a projeção não projeta ciclo futuro.
                # Verifica apenas se ciclo_destino está linkado.
                if refinanciamento.ciclo_destino_id is None:
                    reasons.append("next_cycle_missing")
            elif projected_next is None or next_cycle is None:
                reasons.append("next_cycle_missing")
            else:
                if len(next_rows) != cycle_size:
                    reasons.append("next_cycle_wrong_size")
                if next_rows != projected_next_rows:
                    reasons.append("next_cycle_rows_mismatch")
                if str(next_cycle.status) != str(projected_next.get("status") or ""):
                    reasons.append("next_cycle_status_mismatch")
            if target_reference and any(
                reference == target_reference.isoformat() for reference, _ in unresolved_unpaid
            ):
                reasons.append("target_reference_outside_cycle")

            before = _snapshot(refinanciamento, projection=projection)
            row = {
                "refinanciamento_id": refinanciamento.id,
                "cpf": refinanciamento.associado.cpf_cnpj,
                "nome": refinanciamento.associado.nome_completo,
                "contrato_codigo": contrato.codigo,
                "effective_at": effective_at,
                "effective_date": effective_date.isoformat() if effective_date else None,
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
                    _ensure_effectivation_fields(refinanciamento, effective_at=effective_at)
                    refinanciamento.refresh_from_db()
                    # Contratos cancelados/encerrados: pula rebuild (a projeção não projeta
                    # ciclo futuro para esses contratos, o que causaria soft-delete do
                    # ciclo_destino recém-criado).
                    if not is_inactive_contract:
                        rebuild_contract_cycle_state(contrato, execute=True)
                        refinanciamento.refresh_from_db()
                    if (
                        refinanciamento.ciclo_destino_id is None
                        and refinanciamento.ciclo_origem_id is not None
                    ):
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
                            refinanciamento.save(update_fields=["ciclo_destino", "updated_at"])
                    destino_parcelas = (
                        refinanciamento.ciclo_destino.parcelas.filter(
                            deleted_at__isnull=True,
                        )
                        .exclude(status=Parcela.Status.CANCELADO)
                        .count()
                        if refinanciamento.ciclo_destino_id is not None
                        else 0
                    )
                    if (
                        refinanciamento.ciclo_destino_id is None
                        or destino_parcelas < cycle_size
                    ):
                        _ensure_destination_cycle(
                            refinanciamento,
                            cycle_size=cycle_size,
                            effective_at=effective_at,
                        )
                        refinanciamento.refresh_from_db()
                        # Segundo rebuild apenas para contratos ativos.
                        if not is_inactive_contract:
                            rebuild_contract_cycle_state(contrato, execute=True)
                            refinanciamento.refresh_from_db()
                    if not is_inactive_contract:
                        relink_contract_documents({contrato.id})
                        if contrato.associado.status in {
                            Associado.Status.INADIMPLENTE,
                            Associado.Status.APTO_A_RENOVAR,
                        }:
                            contrato.associado.status = Associado.Status.ATIVO
                            contrato.associado.save(update_fields=["status", "updated_at"])
                        sync_associado_mother_status(contrato.associado)
                    refinanciamento.refresh_from_db()
                    repaired += 1
                    row["after"] = asdict(_snapshot(refinanciamento))
            report_rows.append(row)

        report_payload = {
            "competencia": competencia.isoformat() if competencia is not None else None,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
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
        self.stdout.write(
            f"Competência auditada: {competencia.isoformat() if competencia is not None else 'todas'}"
        )
        if start_date or end_date:
            self.stdout.write(
                "Janela efetiva auditada: "
                f"{start_date.isoformat() if start_date else '-'} a "
                f"{end_date.isoformat() if end_date else '-'}"
            )
        self.stdout.write(f"Refinanciamentos auditados: {audited}")
        self.stdout.write(f"Refinanciamentos com problema: {broken}")
        self.stdout.write(f"Refinanciamentos reparados: {repaired}")
        self.stdout.write(f"Relatório: {report_path}")
