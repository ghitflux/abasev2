from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.importacao.models import ArquivoRetornoItem
from apps.refinanciamento.models import Assumption, Comprovante, Item, Refinanciamento
from apps.tesouraria.models import BaixaManual

from .cycle_projection import (
    build_contract_cycle_projection,
    refinanciamento_matches_contract_timeline,
)
from .cycle_timeline import get_contract_cycle_size
from .models import Ciclo, Contrato, Parcela
from .small_value_rules import is_return_imported_small_value_contract


def _normalize_status(status: str) -> str:
    mapping = {
        Refinanciamento.Status.PENDENTE_APTO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.SOLICITADO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.EM_ANALISE: Refinanciamento.Status.EM_ANALISE_RENOVACAO,
        Refinanciamento.Status.APROVADO: Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
        Refinanciamento.Status.CONCLUIDO: Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
    }
    return mapping.get(status, status)


def _effective_refinanciamento_queryset(contrato: Contrato):
    return Refinanciamento.objects.filter(
        contrato_origem=contrato,
        deleted_at__isnull=True,
    ).order_by("data_ativacao_ciclo", "executado_em", "created_at", "id")


def _active_operational_refis(contrato: Contrato) -> list[Refinanciamento]:
    return list(
        _effective_refinanciamento_queryset(contrato).filter(
            legacy_refinanciamento_id__isnull=True,
            origem=Refinanciamento.Origem.OPERACIONAL,
            status__in=[
                Refinanciamento.Status.APTO_A_RENOVAR,
                Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
                Refinanciamento.Status.EM_ANALISE_RENOVACAO,
                Refinanciamento.Status.PENDENTE_TERMO_ANALISTA,
                Refinanciamento.Status.PENDENTE_TERMO_AGENTE,
                Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
                Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                Refinanciamento.Status.PENDENTE_APTO,
                Refinanciamento.Status.SOLICITADO,
                Refinanciamento.Status.EM_ANALISE,
                Refinanciamento.Status.APROVADO,
                Refinanciamento.Status.CONCLUIDO,
            ]
        )
    )


def _reusable_soft_deleted_operational_refi(
    contrato: Contrato,
    *,
    preferred_status: str | None = None,
) -> Refinanciamento | None:
    candidates = list(
        Refinanciamento.all_objects.filter(
            contrato_origem=contrato,
            deleted_at__isnull=False,
            legacy_refinanciamento_id__isnull=True,
            origem=Refinanciamento.Origem.OPERACIONAL,
            ciclo_destino__isnull=True,
        )
        .prefetch_related("comprovantes")
        .order_by("-updated_at", "-created_at", "-id")
    )
    if not candidates:
        return None

    def priority(item: Refinanciamento) -> tuple[int, int, datetime, int]:
        has_comprovantes = 1 if any(comp.deleted_at is None for comp in item.comprovantes.all()) else 0
        preferred = 1 if preferred_status and item.status == preferred_status else 0
        return (
            preferred,
            has_comprovantes,
            item.updated_at or item.created_at,
            item.id,
        )

    return max(candidates, key=priority)


def _fallback_request_user(contrato: Contrato) -> User | None:
    if contrato.agente_id:
        return contrato.agente
    agente_responsavel = getattr(contrato.associado, "agente_responsavel", None)
    if agente_responsavel is not None:
        return agente_responsavel
    return User.objects.filter(is_active=True).order_by("id").first()


@dataclass
class ContractRebuildReport:
    contrato_id: int
    contrato_codigo: str
    associado_id: int
    ciclos_materializados: int
    ciclos_invalidos_soft_deleted: int = 0
    parcelas_invalidas_soft_deleted: int = 0
    itens_retorno_reassociados: int = 0
    itens_retorno_orfaos: int = 0
    baixas_reassociadas: int = 0
    refinanciamentos_ajustados: int = 0
    refinanciamentos_soft_deleted: int = 0

    def as_dict(self) -> dict[str, object]:
        return self.__dict__.copy()


def _now() -> datetime:
    return timezone.now()


def _ensure_cycle(
    contrato: Contrato,
    desired_cycle: dict[str, object],
    existing_cycle: Ciclo | None,
) -> Ciclo:
    if existing_cycle is None:
        return Ciclo.objects.create(
            contrato=contrato,
            numero=desired_cycle["numero"],
            data_inicio=desired_cycle["data_inicio"],
            data_fim=desired_cycle["data_fim"],
            status=desired_cycle["status"],
            valor_total=desired_cycle["valor_total"],
        )

    changed_fields: list[str] = []
    if existing_cycle.deleted_at is not None:
        existing_cycle.deleted_at = None
        changed_fields.append("deleted_at")
    for field in ("data_inicio", "data_fim", "status", "valor_total"):
        new_value = desired_cycle[field]
        if getattr(existing_cycle, field) != new_value:
            setattr(existing_cycle, field, new_value)
            changed_fields.append(field)
    if changed_fields:
        existing_cycle.save(update_fields=[*changed_fields, "updated_at"])
    return existing_cycle


def _ensure_parcela(
    ciclo: Ciclo,
    contrato: Contrato,
    desired_parcela: dict[str, object],
    existing_parcela: Parcela | None,
) -> Parcela:
    defaults = {
        "associado": contrato.associado,
        "numero": desired_parcela["numero"],
        "referencia_mes": desired_parcela["referencia_mes"],
        "valor": desired_parcela["valor"],
        "data_vencimento": desired_parcela["data_vencimento"],
        "status": desired_parcela["status"],
        "data_pagamento": desired_parcela["data_pagamento"],
        "observacao": desired_parcela["observacao"],
        "deleted_at": None,
    }
    if existing_parcela is None:
        return Parcela.all_objects.create(ciclo=ciclo, **defaults)

    changed_fields: list[str] = []
    for field, value in defaults.items():
        if getattr(existing_parcela, field) != value:
            setattr(existing_parcela, field, value)
            changed_fields.append(field)
    if changed_fields:
        existing_parcela.save(update_fields=[*changed_fields, "updated_at"])
    return existing_parcela


def _soft_delete_extra_parcelas(parcelas: list[Parcela], report: ContractRebuildReport) -> None:
    for parcela in parcelas:
        if parcela.deleted_at is None:
            parcela.soft_delete()
            report.parcelas_invalidas_soft_deleted += 1


def _soft_delete_extra_cycles(ciclos: list[Ciclo], report: ContractRebuildReport) -> None:
    for ciclo in ciclos:
        active_parcelas = list(
            Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        )
        _soft_delete_extra_parcelas(active_parcelas, report)
        if ciclo.deleted_at is None:
            ciclo.soft_delete()
            report.ciclos_invalidos_soft_deleted += 1


def _rebind_financial_links(
    old_reference_by_parcela_id: dict[int, object],
    new_parcela_by_reference: dict[object, Parcela],
    report: ContractRebuildReport,
) -> None:
    for parcela_id, referencia in old_reference_by_parcela_id.items():
        target = new_parcela_by_reference.get(referencia)
        if target is None:
            report.itens_retorno_orfaos += ArquivoRetornoItem.objects.filter(
                parcela_id=parcela_id
            ).update(parcela=None)
            continue

        if parcela_id != target.id:
            report.itens_retorno_reassociados += ArquivoRetornoItem.objects.filter(
                parcela_id=parcela_id
            ).update(parcela=target)

            baixa = BaixaManual.objects.filter(parcela_id=parcela_id).first()
            target_has_baixa = BaixaManual.objects.filter(parcela=target).exists()
            if baixa and baixa.parcela_id != target.id and not target_has_baixa:
                baixa.parcela = target
                baixa.save(update_fields=["parcela", "updated_at"])
                report.baixas_reassociadas += 1


def rebind_financial_links_by_reference(
    old_reference_by_parcela_id: dict[int, object],
    new_parcela_by_reference: dict[object, Parcela],
) -> dict[str, int]:
    report = ContractRebuildReport(
        contrato_id=0,
        contrato_codigo="",
        associado_id=0,
        ciclos_materializados=0,
    )
    _rebind_financial_links(old_reference_by_parcela_id, new_parcela_by_reference, report)
    return {
        "itens_retorno_reassociados": report.itens_retorno_reassociados,
        "itens_retorno_orfaos": report.itens_retorno_orfaos,
        "baixas_reassociadas": report.baixas_reassociadas,
    }


def _sync_refi_items(refinanciamento: Refinanciamento, current_cycle: dict[str, object]) -> None:
    paid_parcelas = [
        parcela
        for parcela in current_cycle["parcelas"]
        if parcela["status"] == Parcela.Status.DESCONTADO
    ]
    Item.objects.filter(refinanciamento=refinanciamento).exclude(
        referencia_month__in=[parcela["referencia_mes"] for parcela in paid_parcelas]
    ).delete()

    for parcela in paid_parcelas:
        Item.objects.update_or_create(
            refinanciamento=refinanciamento,
            referencia_month=parcela["referencia_mes"],
            defaults={
                "pagamento_mensalidade": None,
                "status_code": "1",
                "valor": parcela["valor"],
                "import_uuid": "",
                "source_file_path": "",
            },
        )


def _sync_refinanciamentos(
    contrato: Contrato,
    desired_cycles: list[dict[str, object]],
    cycle_by_number: dict[int, Ciclo],
    report: ContractRebuildReport,
    *,
    force_active_operational_status: str | None = None,
) -> None:
    cycle_size = get_contract_cycle_size(contrato)
    current_cycle = next(
        (item for item in desired_cycles if item["numero"] == max(cycle_by_number)),
        None,
    ) if cycle_by_number else None
    if current_cycle is None:
        current_cycle = desired_cycles[0] if desired_cycles else None

    effective_refis = list(
        (
            _effective_refinanciamento_queryset(contrato).filter(
                status=Refinanciamento.Status.EFETIVADO
            )
            | _effective_refinanciamento_queryset(contrato).exclude(
                data_ativacao_ciclo__isnull=True,
                executado_em__isnull=True,
            )
        ).distinct()
    )
    effective_refis = sorted(
        {item.id: item for item in effective_refis}.values(),
        key=lambda item: (
            item.data_ativacao_ciclo or item.executado_em or item.created_at,
            item.id,
        ),
    )
    valid_effective_refis: list[Refinanciamento] = []
    for refinanciamento in effective_refis:
        if refinanciamento_matches_contract_timeline(contrato, refinanciamento):
            valid_effective_refis.append(refinanciamento)
            continue
        refinanciamento.soft_delete()
        report.refinanciamentos_soft_deleted += 1

    for index, refinanciamento in enumerate(valid_effective_refis, start=2):
        destino = cycle_by_number.get(index)
        changed_fields: list[str] = []
        if refinanciamento.status != Refinanciamento.Status.EFETIVADO:
            refinanciamento.status = Refinanciamento.Status.EFETIVADO
            changed_fields.append("status")
        if refinanciamento.ciclo_destino_id != getattr(destino, "id", None):
            refinanciamento.ciclo_destino = destino
            changed_fields.append("ciclo_destino")
        if refinanciamento.ciclo_origem_id != getattr(cycle_by_number.get(index - 1), "id", None):
            refinanciamento.ciclo_origem = cycle_by_number.get(index - 1)
            changed_fields.append("ciclo_origem")
        if changed_fields:
            refinanciamento.save(update_fields=[*changed_fields, "updated_at"])
            report.refinanciamentos_ajustados += 1

    threshold = max(cycle_size - 1, 1)
    should_have_operational_refi = False
    block_small_value_renewal = is_return_imported_small_value_contract(contrato)
    if current_cycle is not None and cycle_by_number:
        if force_active_operational_status is not None and not block_small_value_renewal:
            should_have_operational_refi = True
        else:
            paid_count = sum(
                1 for parcela in current_cycle["parcelas"] if parcela["status"] == Parcela.Status.DESCONTADO
            )
            should_have_operational_refi = (
                not block_small_value_renewal
                and paid_count >= threshold
                and len(cycle_by_number) == len(desired_cycles)
            )

    active_refis = _active_operational_refis(contrato)
    chosen = active_refis[0] if active_refis else None
    if should_have_operational_refi and current_cycle is not None:
        current_number = current_cycle["numero"]
        current_ciclo = cycle_by_number[current_number]
        referencias = [parcela["referencia_mes"] for parcela in current_cycle["parcelas"]]
        cycle_key = "|".join(referencia.strftime("%Y-%m") for referencia in referencias)
        competencia_solicitada = current_cycle["data_fim"].replace(day=1)
        paid_count = sum(
            1 for parcela in current_cycle["parcelas"] if parcela["status"] == Parcela.Status.DESCONTADO
        )
        value_defaults = {
            "associado": contrato.associado,
            "contrato_origem": contrato,
            "solicitado_por": (
                chosen.solicitado_por if chosen else _fallback_request_user(contrato)
            ),
            "competencia_solicitada": competencia_solicitada,
            "status": (
                force_active_operational_status
                if force_active_operational_status
                else _normalize_status(chosen.status)
                if chosen
                else Refinanciamento.Status.APTO_A_RENOVAR
            ),
            "ciclo_origem": current_ciclo,
            "ciclo_destino": None,
            "valor_refinanciamento": contrato.valor_liquido or contrato.valor_total_antecipacao,
            "repasse_agente": contrato.comissao_agente,
            "mode": chosen.mode if chosen else "tesouraria_auto",
            "origem": Refinanciamento.Origem.OPERACIONAL,
            "cycle_key": cycle_key,
            "ref1": referencias[0] if referencias else None,
            "ref2": referencias[1] if len(referencias) > 1 else None,
            "ref3": referencias[2] if len(referencias) > 2 else None,
            "ref4": referencias[3] if len(referencias) > 3 else None,
            "cpf_cnpj_snapshot": contrato.associado.cpf_cnpj,
            "nome_snapshot": contrato.associado.nome_completo,
            "agente_snapshot": (
                contrato.agente.full_name if contrato.agente else ""
            ),
            "contrato_codigo_origem": contrato.codigo,
            "contrato_codigo_novo": "",
            "parcelas_ok": paid_count,
            "parcelas_json": [
                {
                    "referencia_month": referencia.isoformat(),
                    "status_code": "1",
                    "valor": str(contrato.valor_mensalidade),
                }
                for referencia in referencias[:paid_count]
            ],
            "data_ativacao_ciclo": None,
        }
        if chosen is None:
            user = value_defaults["solicitado_por"]
            if user is None:
                raise ValueError(
                    "Não foi possível determinar usuário solicitante para o refinanciamento."
                )
            reusable = _reusable_soft_deleted_operational_refi(
                contrato,
                preferred_status=force_active_operational_status,
            )
            if reusable is None:
                chosen = Refinanciamento.objects.create(**value_defaults)
            else:
                chosen = reusable
                changed_fields = ["deleted_at"]
                chosen.deleted_at = None
                for field, value in value_defaults.items():
                    if getattr(chosen, field) != value:
                        setattr(chosen, field, value)
                        changed_fields.append(field)
                chosen.save(update_fields=[*changed_fields, "updated_at"])
            report.refinanciamentos_ajustados += 1
        else:
            changed_fields: list[str] = []
            for field, value in value_defaults.items():
                if getattr(chosen, field) != value:
                    setattr(chosen, field, value)
                    changed_fields.append(field)
            if changed_fields:
                chosen.save(update_fields=[*changed_fields, "updated_at"])
                report.refinanciamentos_ajustados += 1

        _sync_refi_items(chosen, current_cycle)
        Assumption.objects.update_or_create(
            cadastro=contrato.associado,
            request_key=cycle_key,
            defaults={
                "cpf_cnpj": contrato.associado.cpf_cnpj,
                "refs_json": [referencia.isoformat() for referencia in referencias],
                "solicitado_por": chosen.solicitado_por,
                "status": (
                    Assumption.Status.ASSUMIDO
                    if chosen.status == Refinanciamento.Status.EM_ANALISE_RENOVACAO
                    else Assumption.Status.FINALIZADO
                    if chosen.status
                    in {
                        Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
                        Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                    }
                    else Assumption.Status.LIBERADO
                ),
                "solicitado_em": chosen.created_at,
                "liberado_em": chosen.created_at,
                "assumido_em": chosen.reviewed_at
                if chosen.status == Refinanciamento.Status.EM_ANALISE_RENOVACAO
                else None,
                "finalizado_em": chosen.reviewed_at
                if chosen.status
                in {
                    Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
                    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                }
                else None,
            },
        )

    for extra in active_refis[1 if chosen else 0 :]:
        extra.soft_delete()
        report.refinanciamentos_soft_deleted += 1
        Assumption.objects.filter(cadastro=contrato.associado, request_key=extra.cycle_key).update(
            status=Assumption.Status.FINALIZADO,
            finalizado_em=_now(),
            updated_at=_now(),
        )

    if not should_have_operational_refi:
        for refi in active_refis:
            refi.soft_delete()
            report.refinanciamentos_soft_deleted += 1
        Assumption.objects.filter(cadastro=contrato.associado).exclude(
            status=Assumption.Status.FINALIZADO
        ).update(
            status=Assumption.Status.FINALIZADO,
            finalizado_em=_now(),
            updated_at=_now(),
        )


@transaction.atomic
def rebuild_contract_cycle_state(
    contrato: Contrato,
    *,
    execute: bool = True,
    extra_reference_by_parcela_id: dict[int, object] | None = None,
    force_active_operational_status: str | None = None,
) -> ContractRebuildReport:
    projection = build_contract_cycle_projection(contrato)
    desired_cycles = list(sorted(projection["cycles"], key=lambda item: item["numero"]))
    report = ContractRebuildReport(
        contrato_id=contrato.id,
        contrato_codigo=contrato.codigo,
        associado_id=contrato.associado_id,
        ciclos_materializados=len(desired_cycles),
    )

    if not execute:
        return report

    if contrato.admin_manual_layout_enabled:
        # Admin overrides write the canonical layout directly to Ciclo/Parcela.
        # Rebuild must not rematerialize from the automatic engine and undo manual edits,
        # but it still needs to sync the operational renewal/liquidation queue.
        cycle_by_number = {
            ciclo.numero: ciclo
            for ciclo in Ciclo.objects.filter(
                contrato=contrato,
                deleted_at__isnull=True,
            ).order_by("numero", "id")
        }
        _sync_refinanciamentos(
            contrato,
            desired_cycles,
            cycle_by_number,
            report,
            force_active_operational_status=force_active_operational_status,
        )
        return report

    existing_cycles: dict[int, Ciclo] = {}
    for ciclo in (
        Ciclo.all_objects.filter(contrato=contrato)
        .prefetch_related("parcelas")
        .order_by("numero", "deleted_at", "id")
    ):
        existing_cycles.setdefault(ciclo.numero, ciclo)
    old_reference_by_parcela_id = {
        parcela.id: parcela.referencia_mes
        for parcela in Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
    }
    if extra_reference_by_parcela_id:
        old_reference_by_parcela_id.update(extra_reference_by_parcela_id)

    # Months with an active BaixaManual are managed outside the cycle — skip their parcelas.
    baixa_manual_refs: set[object] = set(
        BaixaManual.objects.filter(
            parcela__associado=contrato.associado,
            deleted_at__isnull=True,
        ).values_list("parcela__referencia_mes", flat=True)
    )

    cycle_by_number: dict[int, Ciclo] = {}
    new_parcela_by_reference: dict[object, Parcela] = {}
    for desired_cycle in desired_cycles:
        existing_cycle = existing_cycles.pop(desired_cycle["numero"], None)
        cycle = _ensure_cycle(contrato, desired_cycle, existing_cycle)
        cycle_by_number[cycle.numero] = cycle

        current_parcelas = {
            parcela.numero: parcela
            for parcela in Parcela.all_objects.filter(
                ciclo=cycle,
            ).order_by("numero", "deleted_at", "id")
        }
        for desired_parcela in desired_cycle["parcelas"]:
            ref = desired_parcela["referencia_mes"]
            existing = current_parcelas.pop(desired_parcela["numero"], None)
            if ref in baixa_manual_refs:
                # The BaixaManual owns this month; soft-delete the parcela if it exists.
                if existing is not None and existing.deleted_at is None:
                    existing.soft_delete()
                    report.parcelas_invalidas_soft_deleted += 1
                continue
            parcela = _ensure_parcela(
                cycle,
                contrato,
                desired_parcela,
                existing,
            )
            new_parcela_by_reference[parcela.referencia_mes] = parcela
        _soft_delete_extra_parcelas(list(current_parcelas.values()), report)

    _soft_delete_extra_cycles(list(existing_cycles.values()), report)
    _rebind_financial_links(old_reference_by_parcela_id, new_parcela_by_reference, report)
    _sync_refinanciamentos(
        contrato,
        desired_cycles,
        cycle_by_number,
        report,
        force_active_operational_status=force_active_operational_status,
    )
    return report


def rebuild_all_contracts(*, contratos: list[Contrato]) -> list[dict[str, object]]:
    return [rebuild_contract_cycle_state(contrato).as_dict() for contrato in contratos]


def relink_contract_documents(contract_ids: set[int] | list[int]) -> None:
    contract_id_set = {int(contract_id) for contract_id in contract_ids if contract_id}
    if not contract_id_set:
        return

    for refinanciamento in (
        Refinanciamento.objects.filter(contrato_origem_id__in=sorted(contract_id_set))
        .select_related("ciclo_destino", "contrato_origem")
        .order_by("id")
    ):
        if refinanciamento.ciclo_destino_id is None:
            continue
        Comprovante.objects.filter(refinanciamento=refinanciamento).update(
            contrato=refinanciamento.contrato_origem,
            ciclo=refinanciamento.ciclo_destino,
        )
