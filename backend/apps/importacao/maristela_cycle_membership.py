from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.associados.models import Associado, only_digits
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    resolve_associado_mother_status,
)
from apps.contratos.cycle_rebuild import (
    rebuild_contract_cycle_state,
    relink_contract_documents,
)
from apps.contratos.models import Contrato, Parcela
from apps.importacao.manual_payment_flags import (
    MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE,
    MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE,
)
from apps.importacao.models import PagamentoMensalidade
from apps.tesouraria.models import BaixaManual

PAID_STATUS_CODES = {"1", "4"}


class CycleMembershipManualReview(Exception):
    pass


def _parse_reference(value: date | str) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    return datetime.strptime(str(value), "%Y-%m").date().replace(day=1)


def _default_manual_paid_at(referencia: date) -> datetime:
    return timezone.make_aware(datetime.combine(referencia, time(12, 0)))


def _serialize_projection_reference_map(
    projections: dict[int, dict[str, object]],
    reference: date,
) -> dict[str, list[int]]:
    in_cycle: list[int] = []
    outside_cycle: list[int] = []
    for contrato_id, projection in projections.items():
        if any(
            parcela["referencia_mes"] == reference
            for ciclo in projection["cycles"]
            for parcela in ciclo["parcelas"]
        ):
            in_cycle.append(contrato_id)
        if any(
            row["referencia_mes"] == reference
            for row in projection["movimentos_financeiros_avulsos"]
        ):
            outside_cycle.append(contrato_id)
            continue
        if any(
            row["referencia_mes"] == reference and str(row.get("status")) == "quitada"
            for row in projection["unpaid_months"]
        ):
            outside_cycle.append(contrato_id)
    return {
        "in_cycle": sorted(in_cycle),
        "outside_cycle": sorted(outside_cycle),
    }


@dataclass
class RepairContext:
    associado: Associado
    contratos: list[Contrato]
    pagamentos_march: list[PagamentoMensalidade]
    pagamentos_november: list[PagamentoMensalidade]
    parcelas_march: list[Parcela]
    parcelas_november: list[Parcela]
    baixas_march: list[BaixaManual]
    baixas_november: list[BaixaManual]
    projections_before: dict[int, dict[str, object]]


class MaristelaCycleMembershipRepairRunner:
    def __init__(
        self,
        *,
        execute: bool,
        march_ref: date | str = "2026-03",
        november_ref: date | str = "2025-11",
        sheet_file: str | Path,
        actor=None,
        cpf: str | None = None,
        associado_id: int | None = None,
        contrato_id: int | None = None,
    ) -> None:
        self.execute = execute
        self.march_ref = _parse_reference(march_ref)
        self.november_ref = _parse_reference(november_ref)
        self.sheet_file = Path(sheet_file).expanduser()
        self.sheet_source_path = str(sheet_file)
        self.actor = actor
        self.cpf = only_digits(cpf) if cpf else ""
        self.associado_id = int(associado_id) if associado_id else None
        self.contrato_id = int(contrato_id) if contrato_id else None
        self.generated_at = timezone.now()

    def run(self) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        stats = Counter()
        candidate_ids = self._load_candidate_associado_ids()

        for associado in (
            Associado.objects.filter(id__in=sorted(candidate_ids), deleted_at__isnull=True)
            .order_by("id")
        ):
            result = self._process_associado(associado)
            if result is None:
                continue
            results.append(result)
            stats[result["classification"]] += 1
            for key, value in result["changes"].items():
                stats[key] += int(value)

        return {
            "summary": {
                "generated_at": self.generated_at.isoformat(),
                "mode": "execute" if self.execute else "dry-run",
                "march_ref": self.march_ref.isoformat(),
                "november_ref": self.november_ref.isoformat(),
                "sheet_file": str(self.sheet_file),
                "associados_auditados": len(results),
                "repairable": stats["repairable"],
                "repaired": stats["repaired"],
                "already_normalized": stats["already_normalized"],
                "manual_review": stats["manual_review"],
                "pagamentos_created": stats["pagamentos_created"],
                "pagamentos_updated": stats["pagamentos_updated"],
                "baixas_soft_deleted": stats["baixas_soft_deleted"],
                "parcelas_removed_from_cycle": stats["parcelas_removed_from_cycle"],
                "parcelas_reintroduced_in_cycle": stats["parcelas_reintroduced_in_cycle"],
                "rebuilds_executed": stats["rebuilds_executed"],
                "associado_status_updates": stats["associado_status_updates"],
            },
            "results": results,
        }

    def _load_candidate_associado_ids(self) -> set[int]:
        if self.associado_id is not None:
            return {self.associado_id}

        if self.contrato_id is not None:
            contrato = (
                Contrato.objects.filter(id=self.contrato_id, deleted_at__isnull=True)
                .only("associado_id")
                .first()
            )
            return {contrato.associado_id} if contrato else set()

        if self.cpf:
            return set(
                Associado.objects.filter(cpf_cnpj=self.cpf, deleted_at__isnull=True).values_list(
                    "id", flat=True
                )
            )

        cpf_to_associado_id = {
            only_digits(cpf_cnpj): associado_id
            for associado_id, cpf_cnpj in Associado.objects.filter(
                deleted_at__isnull=True
            ).values_list("id", "cpf_cnpj")
        }

        candidate_ids: set[int] = set(
            Parcela.all_objects.filter(
                referencia_mes__in=[self.march_ref, self.november_ref],
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .values_list("associado_id", flat=True)
        )
        candidate_ids.update(
            BaixaManual.objects.filter(
                deleted_at__isnull=True,
                parcela__referencia_mes__in=[self.march_ref, self.november_ref],
            ).values_list("parcela__associado_id", flat=True)
        )

        for associado_id, cpf_cnpj in PagamentoMensalidade.objects.filter(
            referencia_month__in=[self.march_ref, self.november_ref]
        ).values_list("associado_id", "cpf_cnpj"):
            if associado_id:
                candidate_ids.add(associado_id)
                continue
            mapped_associado_id = cpf_to_associado_id.get(only_digits(cpf_cnpj))
            if mapped_associado_id:
                candidate_ids.add(mapped_associado_id)
        return candidate_ids

    def _load_context(self, associado: Associado) -> RepairContext:
        contratos = list(
            Contrato.objects.select_related("associado")
            .filter(associado=associado, deleted_at__isnull=True)
            .exclude(status=Contrato.Status.CANCELADO)
            .order_by("id")
        )
        pagamentos = list(
            PagamentoMensalidade.objects.filter(
                Q(associado=associado) | Q(cpf_cnpj=associado.cpf_cnpj),
                referencia_month__in=[self.march_ref, self.november_ref],
            ).order_by("referencia_month", "id")
        )
        parcelas = list(
            Parcela.all_objects.filter(
                associado=associado,
                referencia_mes__in=[self.march_ref, self.november_ref],
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .select_related("ciclo__contrato")
            .order_by("referencia_mes", "ciclo__contrato_id", "numero", "id")
        )
        baixas = list(
            BaixaManual.objects.filter(
                deleted_at__isnull=True,
                parcela__associado=associado,
                parcela__referencia_mes__in=[self.march_ref, self.november_ref],
            )
            .select_related("parcela__ciclo__contrato")
            .order_by("parcela__referencia_mes", "id")
        )
        projections_before = {
            contrato.id: build_contract_cycle_projection(contrato) for contrato in contratos
        }

        return RepairContext(
            associado=associado,
            contratos=contratos,
            pagamentos_march=[
                pagamento
                for pagamento in pagamentos
                if pagamento.referencia_month == self.march_ref
            ],
            pagamentos_november=[
                pagamento
                for pagamento in pagamentos
                if pagamento.referencia_month == self.november_ref
            ],
            parcelas_march=[
                parcela for parcela in parcelas if parcela.referencia_mes == self.march_ref
            ],
            parcelas_november=[
                parcela for parcela in parcelas if parcela.referencia_mes == self.november_ref
            ],
            baixas_march=[
                baixa
                for baixa in baixas
                if baixa.parcela.referencia_mes == self.march_ref
            ],
            baixas_november=[
                baixa
                for baixa in baixas
                if baixa.parcela.referencia_mes == self.november_ref
            ],
            projections_before=projections_before,
        )

    def _process_associado(self, associado: Associado) -> dict[str, Any] | None:
        context = self._load_context(associado)
        if not context.contratos:
            return None

        before_march = _serialize_projection_reference_map(
            context.projections_before,
            self.march_ref,
        )
        before_november = _serialize_projection_reference_map(
            context.projections_before,
            self.november_ref,
        )
        original_status = associado.status
        march_issue = self._needs_march_fix(context, before_march)
        november_issue = self._needs_november_fix(context, before_november)
        if not march_issue and not november_issue:
            return {
                "associado_id": associado.id,
                "cpf_cnpj": associado.cpf_cnpj,
                "nome_completo": associado.nome_completo,
                "classification": "already_normalized",
                "issues": {
                    "march": march_issue,
                    "november": november_issue,
                },
                "before": {
                    "march": before_march,
                    "november": before_november,
                    "status_associado": original_status,
                },
                "after": {
                    "march": before_march,
                    "november": before_november,
                    "status_associado": original_status,
                },
                "changes": {
                    "pagamentos_created": 0,
                    "pagamentos_updated": 0,
                    "baixas_soft_deleted": 0,
                    "parcelas_removed_from_cycle": 0,
                    "parcelas_reintroduced_in_cycle": 0,
                    "rebuilds_executed": 0,
                    "associado_status_updates": 0,
                },
            }

        changes = Counter()
        after_payload: dict[str, Any] = {}
        classification = "repairable"
        error_message = ""

        try:
            with transaction.atomic():
                if march_issue:
                    self._normalize_march(context, changes)
                if november_issue:
                    self._normalize_november(context, changes)

                for contrato in context.contratos:
                    rebuild_contract_cycle_state(contrato, execute=True)
                    changes["rebuilds_executed"] += 1
                relink_contract_documents({contrato.id for contrato in context.contratos})

                after_projections = {
                    contrato.id: build_contract_cycle_projection(contrato)
                    for contrato in context.contratos
                }
                self._validate_after(context, after_projections, march_issue, november_issue)
                if self._sync_associado_status(context.associado, context.contratos, after_projections):
                    changes["associado_status_updates"] += 1

                after_payload = {
                    "march": _serialize_projection_reference_map(
                        after_projections,
                        self.march_ref,
                    ),
                    "november": _serialize_projection_reference_map(
                        after_projections,
                        self.november_ref,
                    ),
                    "status_associado": context.associado.status,
                }

                if not self.execute:
                    transaction.set_rollback(True)
                else:
                    classification = "repaired"
        except CycleMembershipManualReview as exc:
            classification = "manual_review"
            error_message = str(exc)
            after_payload = {
                "march": before_march,
                "november": before_november,
                "status_associado": original_status,
            }

        return {
            "associado_id": associado.id,
            "cpf_cnpj": associado.cpf_cnpj,
            "nome_completo": associado.nome_completo,
            "classification": classification,
            "issues": {
                "march": march_issue,
                "november": november_issue,
            },
            "error": error_message or None,
            "before": {
                "march": before_march,
                "november": before_november,
                "status_associado": original_status,
            },
            "after": after_payload,
            "changes": {
                "pagamentos_created": changes["pagamentos_created"],
                "pagamentos_updated": changes["pagamentos_updated"],
                "baixas_soft_deleted": changes["baixas_soft_deleted"],
                "parcelas_removed_from_cycle": changes["parcelas_removed_from_cycle"],
                "parcelas_reintroduced_in_cycle": changes["parcelas_reintroduced_in_cycle"],
                "rebuilds_executed": changes["rebuilds_executed"],
                "associado_status_updates": changes["associado_status_updates"],
            },
        }

    def _needs_march_fix(
        self,
        context: RepairContext,
        before_march: dict[str, list[int]],
    ) -> bool:
        if context.baixas_march:
            return True
        if before_march["outside_cycle"]:
            return True
        if not context.pagamentos_march and not context.parcelas_march:
            return False
        if before_march["in_cycle"]:
            return any(
                pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
                and pagamento.manual_forma_pagamento != MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE
                for pagamento in context.pagamentos_march
            )
        return bool(context.pagamentos_march or context.parcelas_march)

    def _needs_november_fix(
        self,
        context: RepairContext,
        before_november: dict[str, list[int]],
    ) -> bool:
        if before_november["in_cycle"]:
            return True
        return any(
            pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO
            and pagamento.manual_forma_pagamento != MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE
            for pagamento in context.pagamentos_november
        )

    def _normalize_march(self, context: RepairContext, changes: Counter[str]) -> None:
        for baixa in context.baixas_march:
            baixa.soft_delete()
            changes["baixas_soft_deleted"] += 1

        march_value = self._resolve_reference_value(
            context.pagamentos_march,
            context.parcelas_march,
            context.baixas_march,
        )
        if not context.pagamentos_march:
            pagamento = PagamentoMensalidade.objects.create(
                created_by=self.actor,
                import_uuid=f"repair-maristela-march-{context.associado.id}",
                referencia_month=self.march_ref,
                status_code="M",
                matricula=(
                    context.associado.matricula_orgao
                    or context.associado.matricula
                    or ""
                ),
                orgao_pagto="",
                nome_relatorio=context.associado.nome_completo,
                cpf_cnpj=context.associado.cpf_cnpj,
                associado=context.associado,
                valor=march_value,
                recebido_manual=march_value,
                manual_status=PagamentoMensalidade.ManualStatus.PAGO,
                manual_paid_at=_default_manual_paid_at(self.march_ref),
                manual_forma_pagamento=MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE,
                manual_by=self.actor,
                source_file_path=self.sheet_source_path,
            )
            context.pagamentos_march = [pagamento]
            changes["pagamentos_created"] += 1
        else:
            for pagamento in context.pagamentos_march:
                if self._update_pagamento_manual(
                    pagamento,
                    manual_kind=MANUAL_PAYMENT_KIND_MARISTELA_IN_CYCLE,
                    default_value=march_value,
                    associado=context.associado,
                ):
                    changes["pagamentos_updated"] += 1

        self._materialize_march_in_cycle(context, march_value, changes)

    def _normalize_november(self, context: RepairContext, changes: Counter[str]) -> None:
        november_value = self._resolve_reference_value(
            context.pagamentos_november,
            context.parcelas_november,
            context.baixas_november,
        )
        if not context.pagamentos_november:
            pagamento = PagamentoMensalidade.objects.create(
                created_by=self.actor,
                import_uuid=f"repair-maristela-november-{context.associado.id}",
                referencia_month=self.november_ref,
                status_code="M",
                matricula=(
                    context.associado.matricula_orgao
                    or context.associado.matricula
                    or ""
                ),
                orgao_pagto="",
                nome_relatorio=context.associado.nome_completo,
                cpf_cnpj=context.associado.cpf_cnpj,
                associado=context.associado,
                valor=november_value,
                recebido_manual=november_value,
                manual_status=PagamentoMensalidade.ManualStatus.PAGO,
                manual_paid_at=_default_manual_paid_at(self.november_ref),
                manual_forma_pagamento=MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE,
                manual_by=self.actor,
                source_file_path=self.sheet_source_path,
            )
            context.pagamentos_november = [pagamento]
            changes["pagamentos_created"] += 1
        else:
            for pagamento in context.pagamentos_november:
                if self._update_pagamento_manual(
                    pagamento,
                    manual_kind=MANUAL_PAYMENT_KIND_MARISTELA_OUTSIDE_CYCLE,
                    default_value=november_value,
                    associado=context.associado,
                ):
                    changes["pagamentos_updated"] += 1

    def _update_pagamento_manual(
        self,
        pagamento: PagamentoMensalidade,
        *,
        manual_kind: str,
        default_value: Decimal,
        associado: Associado,
    ) -> bool:
        update_fields: list[str] = []
        if pagamento.associado_id != associado.id:
            pagamento.associado = associado
            update_fields.append("associado")
        if pagamento.cpf_cnpj != associado.cpf_cnpj:
            pagamento.cpf_cnpj = associado.cpf_cnpj
            update_fields.append("cpf_cnpj")
        if not pagamento.nome_relatorio:
            pagamento.nome_relatorio = associado.nome_completo
            update_fields.append("nome_relatorio")
        if not pagamento.matricula and (associado.matricula_orgao or associado.matricula):
            pagamento.matricula = associado.matricula_orgao or associado.matricula or ""
            update_fields.append("matricula")
        if pagamento.manual_status != PagamentoMensalidade.ManualStatus.PAGO:
            pagamento.manual_status = PagamentoMensalidade.ManualStatus.PAGO
            update_fields.append("manual_status")
        if pagamento.manual_forma_pagamento != manual_kind:
            pagamento.manual_forma_pagamento = manual_kind
            update_fields.append("manual_forma_pagamento")
        if pagamento.manual_paid_at is None:
            pagamento.manual_paid_at = _default_manual_paid_at(pagamento.referencia_month)
            update_fields.append("manual_paid_at")
        if pagamento.recebido_manual is None:
            pagamento.recebido_manual = (
                pagamento.valor if pagamento.valor not in (None, Decimal("0")) else default_value
            )
            update_fields.append("recebido_manual")
        if pagamento.valor in (None, Decimal("0")):
            pagamento.valor = default_value
            update_fields.append("valor")
        if not pagamento.source_file_path:
            pagamento.source_file_path = self.sheet_source_path
            update_fields.append("source_file_path")
        if "manual_by" not in update_fields and self.actor is not None and pagamento.manual_by_id != getattr(self.actor, "id", None):
            pagamento.manual_by = self.actor
            update_fields.append("manual_by")
        if update_fields:
            pagamento.save(update_fields=[*sorted(set(update_fields)), "updated_at"])
            return True
        return False

    def _resolve_reference_value(
        self,
        pagamentos: list[PagamentoMensalidade],
        parcelas: list[Parcela],
        baixas: list[BaixaManual],
    ) -> Decimal:
        values = [
            value
            for value in [
                *[pagamento.recebido_manual for pagamento in pagamentos],
                *[pagamento.valor for pagamento in pagamentos],
                *[parcela.valor for parcela in parcelas],
                *[baixa.valor_pago for baixa in baixas],
            ]
            if value not in (None, Decimal("0"))
        ]
        unique_values = {Decimal(str(value)) for value in values}
        if len(unique_values) > 1:
            raise CycleMembershipManualReview(
                f"Valores conflitantes para a mesma competência: {sorted(str(value) for value in unique_values)}"
            )
        if unique_values:
            return unique_values.pop()
        raise CycleMembershipManualReview("Nenhum valor financeiro elegível foi encontrado para a competência.")

    def _materialize_march_in_cycle(
        self,
        context: RepairContext,
        march_value: Decimal,
        changes: Counter[str],
    ) -> None:
        active_march = (
            Parcela.all_objects.filter(
                associado=context.associado,
                referencia_mes=self.march_ref,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .select_related("ciclo")
            .order_by("id")
            .first()
        )
        if active_march is not None:
            return

        candidate = (
            Parcela.all_objects.filter(
                associado=context.associado,
                referencia_mes__gt=self.march_ref,
                deleted_at__isnull=True,
                ciclo__deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .select_related("ciclo")
            .order_by("referencia_mes", "id")
            .first()
        )
        if candidate is not None:
            candidate.referencia_mes = self.march_ref
            candidate.data_vencimento = self.march_ref
            candidate.valor = march_value
            candidate.status = Parcela.Status.DESCONTADO
            candidate.data_pagamento = self.march_ref
            candidate.layout_bucket = Parcela.LayoutBucket.CYCLE
            candidate.observacao = (
                f"{candidate.observacao}\nReparado: março reintegrado ao ciclo."
                if candidate.observacao
                else "Reparado: março reintegrado ao ciclo."
            )
            candidate.save(
                update_fields=[
                    "referencia_mes",
                    "data_vencimento",
                    "valor",
                    "status",
                    "data_pagamento",
                    "layout_bucket",
                    "observacao",
                    "updated_at",
                ]
            )
            changes["parcelas_reintroduced_in_cycle"] += 1

    def _validate_after(
        self,
        context: RepairContext,
        after_projections: dict[int, dict[str, object]],
        march_issue: bool,
        november_issue: bool,
    ) -> None:
        after_march = _serialize_projection_reference_map(after_projections, self.march_ref)
        after_november = _serialize_projection_reference_map(
            after_projections,
            self.november_ref,
        )
        march_active_parcelas = list(
            Parcela.all_objects.filter(
                associado=context.associado,
                referencia_mes=self.march_ref,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("id")
        )
        november_active_parcelas = list(
            Parcela.all_objects.filter(
                associado=context.associado,
                referencia_mes=self.november_ref,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("id")
        )

        if march_issue:
            if len(after_march["in_cycle"]) < 1:
                raise CycleMembershipManualReview(
                    "Março não ficou materializado em ciclo após o rebuild."
                )
            if after_march["outside_cycle"] and not after_march["in_cycle"]:
                raise CycleMembershipManualReview(
                    "Março continuou aparecendo como movimento financeiro fora do ciclo."
                )
            if len(march_active_parcelas) != 1 or march_active_parcelas[0].status not in {
                Parcela.Status.DESCONTADO,
                Parcela.Status.LIQUIDADA,
            }:
                raise CycleMembershipManualReview(
                    "Parcela ativa de março não ficou quitada dentro do ciclo."
                )

        if november_issue:
            if after_november["in_cycle"]:
                raise CycleMembershipManualReview(
                    "Novembro continuou materializado dentro do ciclo."
                )
            if not after_november["outside_cycle"]:
                raise CycleMembershipManualReview(
                    "Novembro não apareceu como quitado fora do ciclo."
                )
            if november_active_parcelas:
                raise CycleMembershipManualReview(
                    "Ainda existem parcelas ativas de novembro vinculadas a ciclos."
                )

    def _sync_associado_status(
        self,
        associado: Associado,
        contratos: list[Contrato],
        after_projections: dict[int, dict[str, object]],
    ) -> bool:
        _ = contratos
        target_status = resolve_associado_mother_status(
            associado,
            projections_by_contract=after_projections,
        )
        if associado.status == target_status:
            return False
        associado.status = target_status
        associado.save(update_fields=["status", "updated_at"])
        return True
