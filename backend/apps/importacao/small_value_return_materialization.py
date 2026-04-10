from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.associados.models import Associado, only_digits
from apps.contratos.canonicalization import (
    get_operational_contracts_for_associado,
    is_shadow_duplicate_contract,
)
from apps.contratos.models import Ciclo, Contrato, Parcela

from .matching import find_associado
from .models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from .return_auto_enrollment import resolve_or_create_imported_associado

SMALL_VALUE_RETURN_AMOUNTS = {Decimal("30.00"), Decimal("50.00")}
SMALL_VALUE_PAID_STATUS_CODES = {"1", "4"}
SMALL_VALUE_UNPAID_STATUS_CODES = {"2", "3", "S"}


def parse_competencia_text(value: str) -> date:
    month, year = str(value).split("/", 1)
    return date(int(year), int(month), 1)


def is_small_value_return_amount(value: Decimal | None) -> bool:
    if value is None:
        return False
    return Decimal(str(value)).quantize(Decimal("0.01")) in SMALL_VALUE_RETURN_AMOUNTS


def map_status_code_to_parcela_status(status_code: str) -> str:
    if status_code in SMALL_VALUE_PAID_STATUS_CODES:
        return Parcela.Status.DESCONTADO
    if status_code in SMALL_VALUE_UNPAID_STATUS_CODES:
        return Parcela.Status.NAO_DESCONTADO
    return Parcela.Status.EM_ABERTO


def derive_cycle_status(parcelas: list[dict[str, object]]) -> str:
    statuses = {str(parcela["status"]) for parcela in parcelas}
    if statuses and statuses.issubset({Parcela.Status.DESCONTADO, Parcela.Status.LIQUIDADA}):
        return Ciclo.Status.FECHADO
    if Parcela.Status.NAO_DESCONTADO in statuses:
        return Ciclo.Status.PENDENCIA
    return Ciclo.Status.ABERTO


def resolve_default_small_value_agent() -> User | None:
    direct = (
        User.objects.filter(
            deleted_at__isnull=True,
            is_active=True,
            email__iexact="agente@abase.com",
        )
        .order_by("id")
        .first()
    )
    if direct is not None:
        return direct

    by_name = (
        User.objects.filter(
            deleted_at__isnull=True,
            is_active=True,
            first_name__iexact="Agente",
        )
        .order_by("id")
        .first()
    )
    if by_name is not None:
        return by_name

    return (
        User.objects.filter(
            deleted_at__isnull=True,
            is_active=True,
            user_roles__deleted_at__isnull=True,
            user_roles__role__codigo="AGENTE",
        )
        .distinct()
        .order_by("id")
        .first()
    )


def _active_contract_parcelas(contrato: Contrato) -> list[Parcela]:
    return list(
        Parcela.all_objects.filter(
            ciclo__contrato=contrato,
            deleted_at__isnull=True,
        )
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo", "ciclo__contrato")
        .order_by("ciclo__numero", "numero", "id")
    )


def _is_dedicated_small_value_contract(
    contrato: Contrato,
    *,
    value: Decimal,
) -> bool:
    if is_shadow_duplicate_contract(contrato):
        return False

    active_parcelas = _active_contract_parcelas(contrato)
    if not active_parcelas:
        return (
            Decimal(str(contrato.valor_mensalidade or Decimal("0.00"))).quantize(Decimal("0.01"))
            == value
            and contrato.admin_manual_layout_enabled
        )

    return all(
        Decimal(str(parcela.valor or Decimal("0.00"))).quantize(Decimal("0.01")) == value
        for parcela in active_parcelas
    )


def _choose_snapshot_contract_before_small_value_creation(
    associado: Associado,
    *,
    value: Decimal,
) -> Contrato | None:
    for contrato in get_operational_contracts_for_associado(associado):
        if _is_dedicated_small_value_contract(contrato, value=value):
            continue
        return contrato
    return None


def _choose_or_create_small_value_contract(
    *,
    associado: Associado,
    value: Decimal,
    first_reference: date,
    total_parcelas: int,
    default_agent: User | None,
) -> tuple[Contrato, bool]:
    contracts = get_operational_contracts_for_associado(associado)
    dedicated = [
        contrato
        for contrato in contracts
        if _is_dedicated_small_value_contract(contrato, value=value)
    ]
    if dedicated:
        dedicated.sort(key=lambda contrato: (contrato.created_at, contrato.id))
        return dedicated[0], False

    snapshot_contract = _choose_snapshot_contract_before_small_value_creation(
        associado,
        value=value,
    )
    prazo = max(total_parcelas, 1)
    total_value = (value * Decimal(str(prazo))).quantize(Decimal("0.01"))

    contrato = Contrato.objects.create(
        associado=associado,
        agente=default_agent or associado.agente_responsavel,
        valor_bruto=total_value,
        valor_liquido=total_value,
        valor_mensalidade=value,
        prazo_meses=prazo,
        taxa_antecipacao=Decimal("0.00"),
        margem_disponivel=value,
        valor_total_antecipacao=total_value,
        doacao_associado=Decimal("0.00"),
        status=Contrato.Status.ATIVO,
        data_contrato=first_reference,
        data_aprovacao=first_reference,
        data_primeira_mensalidade=first_reference,
        mes_averbacao=first_reference,
        contato_web=False,
        termos_web=False,
        admin_manual_layout_enabled=True,
        admin_manual_layout_updated_at=timezone.now(),
    )

    if snapshot_contract is not None and snapshot_contract.id != contrato.id:
        associado.sync_contrato_snapshot(snapshot_contract)

    return contrato, True


def _update_small_value_contract_metadata(
    contrato: Contrato,
    *,
    value: Decimal,
    first_reference: date,
    total_parcelas: int,
    default_agent: User | None,
) -> int:
    prazo = max(total_parcelas, 1)
    total_value = (value * Decimal(str(prazo))).quantize(Decimal("0.01"))
    changed_fields: list[str] = []
    desired_values = {
        "agente": default_agent or contrato.agente or getattr(contrato.associado, "agente_responsavel", None),
        "valor_bruto": total_value,
        "valor_liquido": total_value,
        "valor_mensalidade": value,
        "prazo_meses": prazo,
        "taxa_antecipacao": Decimal("0.00"),
        "margem_disponivel": value,
        "valor_total_antecipacao": total_value,
        "doacao_associado": Decimal("0.00"),
        "status": Contrato.Status.ATIVO,
        "data_contrato": first_reference,
        "data_aprovacao": first_reference,
        "data_primeira_mensalidade": first_reference,
        "mes_averbacao": first_reference,
        "contato_web": False,
        "termos_web": False,
        "admin_manual_layout_enabled": True,
        "admin_manual_layout_updated_at": timezone.now(),
    }
    for field, new_value in desired_values.items():
        if getattr(contrato, field) != new_value:
            setattr(contrato, field, new_value)
            changed_fields.append(field)

    if changed_fields:
        contrato.save(update_fields=[*changed_fields, "updated_at"])
    return len(changed_fields)


def _ensure_cycle(
    contrato: Contrato,
    desired: dict[str, object],
    existing: Ciclo | None,
) -> tuple[Ciclo, bool]:
    if existing is None:
        return (
            Ciclo.objects.create(
                contrato=contrato,
                numero=int(desired["numero"]),
                data_inicio=desired["data_inicio"],
                data_fim=desired["data_fim"],
                status=str(desired["status"]),
                valor_total=desired["valor_total"],
            ),
            True,
        )

    changed_fields: list[str] = []
    if existing.deleted_at is not None:
        existing.deleted_at = None
        changed_fields.append("deleted_at")
    for field in ("data_inicio", "data_fim", "status", "valor_total"):
        new_value = desired[field]
        if getattr(existing, field) != new_value:
            setattr(existing, field, new_value)
            changed_fields.append(field)
    if changed_fields:
        existing.save(update_fields=[*changed_fields, "updated_at"])
    return existing, bool(changed_fields)


def _ensure_parcela(
    ciclo: Ciclo,
    contrato: Contrato,
    desired: dict[str, object],
    existing: Parcela | None,
) -> tuple[Parcela, bool]:
    defaults = {
        "associado": contrato.associado,
        "numero": int(desired["numero"]),
        "referencia_mes": desired["referencia_mes"],
        "valor": desired["valor"],
        "data_vencimento": desired["data_vencimento"],
        "status": str(desired["status"]),
        "data_pagamento": desired["data_pagamento"],
        "observacao": str(desired["observacao"]),
        "layout_bucket": Parcela.LayoutBucket.CYCLE,
        "deleted_at": None,
    }
    if existing is None:
        return Parcela.all_objects.create(ciclo=ciclo, **defaults), True

    changed_fields: list[str] = []
    for field, value in defaults.items():
        if getattr(existing, field) != value:
            setattr(existing, field, value)
            changed_fields.append(field)
    if changed_fields:
        existing.save(update_fields=[*changed_fields, "updated_at"])
    return existing, bool(changed_fields)


def _soft_delete_cycle(ciclo: Ciclo) -> tuple[int, int]:
    parcelas_deleted = 0
    for parcela in (
        Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("numero", "id")
    ):
        parcela.soft_delete()
        parcelas_deleted += 1
    if ciclo.deleted_at is None:
        ciclo.soft_delete()
        return 1, parcelas_deleted
    return 0, parcelas_deleted


def _reserve_cycle_parcela_numbers(parcelas: list[Parcela]) -> None:
    if not parcelas:
        return
    max_existing_number = max((parcela.numero or 0) for parcela in parcelas)
    reserved_base = max_existing_number + 100
    for index, parcela in enumerate(parcelas, start=1):
        reserved_number = reserved_base + index
        if parcela.numero == reserved_number:
            continue
        parcela.numero = reserved_number
        parcela.save(update_fields=["numero", "updated_at"])


def _build_canonical_items(items: list[ArquivoRetornoItem]) -> list[ArquivoRetornoItem]:
    by_reference: dict[date, ArquivoRetornoItem] = {}
    for item in items:
        referencia = parse_competencia_text(item.competencia)
        current = by_reference.get(referencia)
        item_key = (
            item.arquivo_retorno.processado_em or item.arquivo_retorno.created_at,
            item.arquivo_retorno.created_at,
            item.updated_at,
            item.id,
        )
        if current is None:
            by_reference[referencia] = item
            continue
        current_key = (
            current.arquivo_retorno.processado_em or current.arquivo_retorno.created_at,
            current.arquivo_retorno.created_at,
            current.updated_at,
            current.id,
        )
        if item_key >= current_key:
            by_reference[referencia] = item
    return [by_reference[reference] for reference in sorted(by_reference)]


def _build_desired_cycles(
    *,
    canonical_items: list[ArquivoRetornoItem],
    value: Decimal,
) -> list[dict[str, object]]:
    desired_cycles: list[dict[str, object]] = []
    for offset in range(0, len(canonical_items), 3):
        chunk = canonical_items[offset : offset + 3]
        parcelas: list[dict[str, object]] = []
        for index, item in enumerate(chunk, start=1):
            referencia = parse_competencia_text(item.competencia)
            parcela_status = map_status_code_to_parcela_status(item.status_codigo)
            parcelas.append(
                {
                    "numero": index,
                    "referencia_mes": referencia,
                    "valor": value,
                    "data_vencimento": referencia,
                    "status": parcela_status,
                    "data_pagamento": referencia
                    if parcela_status == Parcela.Status.DESCONTADO
                    else None,
                    "observacao": (
                        "Materializada automaticamente a partir do arquivo retorno "
                        f"{item.arquivo_retorno.arquivo_nome}."
                    ),
                }
            )

        desired_cycles.append(
            {
                "numero": len(desired_cycles) + 1,
                "data_inicio": parcelas[0]["referencia_mes"],
                "data_fim": parcelas[-1]["referencia_mes"],
                "status": derive_cycle_status(parcelas),
                "valor_total": (value * Decimal(str(len(parcelas)))).quantize(Decimal("0.01")),
                "parcelas": parcelas,
            }
        )
    return desired_cycles


def _update_associado_agent(
    *,
    associado: Associado,
    default_agent: User | None,
) -> bool:
    if default_agent is None or associado.agente_responsavel_id:
        return False
    associado.agente_responsavel = default_agent
    associado.save(update_fields=["agente_responsavel", "updated_at"])
    return True


def _resolve_associado_for_small_value_items(
    *,
    canonical_items: list[ArquivoRetornoItem],
    default_agent: User | None,
) -> tuple[Associado, bool, bool]:
    seed = canonical_items[-1]
    cpf = only_digits(seed.cpf_cnpj)
    associado = seed.associado or find_associado(
        cpf=cpf,
        matricula=seed.matricula_servidor,
        nome=seed.nome_servidor,
        orgao=seed.orgao_pagto_nome,
        orgao_alternativo=seed.orgao_pagto_codigo,
        orgao_codigo=seed.orgao_codigo,
    )
    created = False
    if associado is None or associado.status == Associado.Status.IMPORTADO:
        associado, created = resolve_or_create_imported_associado(
            arquivo_nome=seed.arquivo_retorno.arquivo_nome,
            competencia=parse_competencia_text(seed.competencia),
            data_geracao=seed.arquivo_retorno.resultado_resumo.get("data_geracao"),
            cpf_cnpj=cpf,
            nome_completo=seed.nome_servidor,
            matricula_orgao=seed.matricula_servidor,
            orgao_publico=seed.orgao_pagto_nome,
            cargo=seed.cargo,
            existing=associado,
        )
    if associado is None:
        raise ValueError(f"Não foi possível materializar associado para CPF {cpf}.")
    agent_updated = _update_associado_agent(
        associado=associado,
        default_agent=default_agent,
    )
    return associado, created, agent_updated


def _link_pagamentos_to_associado(
    *,
    associado: Associado,
    canonical_items: list[ArquivoRetornoItem],
    value: Decimal,
) -> int:
    referencias = [parse_competencia_text(item.competencia) for item in canonical_items]
    return PagamentoMensalidade.objects.filter(
        cpf_cnpj=associado.cpf_cnpj,
        referencia_month__in=referencias,
        valor=value,
    ).exclude(associado=associado).update(associado=associado)


def _rebuild_small_value_contract(
    *,
    contrato: Contrato,
    desired_cycles: list[dict[str, object]],
) -> tuple[dict[date, Parcela], dict[str, int]]:
    stats = {
        "cycles_created": 0,
        "cycles_updated": 0,
        "cycles_soft_deleted": 0,
        "parcelas_created": 0,
        "parcelas_updated": 0,
        "parcelas_soft_deleted": 0,
    }
    existing_cycles: dict[int, Ciclo] = {}
    for ciclo in (
        Ciclo.all_objects.filter(contrato=contrato)
        .prefetch_related("parcelas")
        .order_by("numero", "deleted_at", "id")
    ):
        existing_cycles.setdefault(ciclo.numero, ciclo)

    parcela_by_reference: dict[date, Parcela] = {}
    for desired_cycle in desired_cycles:
        cycle_number = int(desired_cycle["numero"])
        existing_cycle = existing_cycles.pop(cycle_number, None)
        ciclo, changed = _ensure_cycle(contrato, desired_cycle, existing_cycle)
        if existing_cycle is None:
            stats["cycles_created"] += 1
        elif changed:
            stats["cycles_updated"] += 1

        active_parcelas = list(
            Parcela.all_objects.filter(ciclo=ciclo)
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("numero", "deleted_at", "id")
        )
        parcelas_by_reference: dict[date, Parcela] = {}
        parcelas_by_number: dict[int, Parcela] = {}
        for parcela in active_parcelas:
            parcelas_by_number.setdefault(parcela.numero, parcela)
            if parcela.deleted_at is None:
                parcelas_by_reference.setdefault(parcela.referencia_mes, parcela)
        _reserve_cycle_parcela_numbers(active_parcelas)
        touched_ids: set[int] = set()
        for desired_parcela in desired_cycle["parcelas"]:
            referencia = desired_parcela["referencia_mes"]
            existing_parcela = parcelas_by_reference.get(referencia)
            if existing_parcela is None:
                existing_parcela = parcelas_by_number.get(int(desired_parcela["numero"]))
            parcela, parcela_changed = _ensure_parcela(
                ciclo,
                contrato,
                desired_parcela,
                existing_parcela,
            )
            touched_ids.add(parcela.id)
            if existing_parcela is None:
                stats["parcelas_created"] += 1
            elif parcela_changed:
                stats["parcelas_updated"] += 1
            parcela_by_reference[parcela.referencia_mes] = parcela

        for parcela in active_parcelas:
            if parcela.id in touched_ids or parcela.deleted_at is not None:
                continue
            parcela.soft_delete()
            stats["parcelas_soft_deleted"] += 1

    for ciclo in existing_cycles.values():
        deleted_cycles, deleted_parcelas = _soft_delete_cycle(ciclo)
        stats["cycles_soft_deleted"] += deleted_cycles
        stats["parcelas_soft_deleted"] += deleted_parcelas

    return parcela_by_reference, stats


@dataclass
class SmallValueCpfResult:
    cpf_cnpj: str
    associado_id: int
    contrato_id: int
    contrato_codigo: str
    associated_created: bool
    contract_created: bool
    references: list[str]
    item_ids: list[int]
    stats: dict[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "cpf_cnpj": self.cpf_cnpj,
            "associado_id": self.associado_id,
            "contrato_id": self.contrato_id,
            "contrato_codigo": self.contrato_codigo,
            "associated_created": self.associated_created,
            "contract_created": self.contract_created,
            "references": self.references,
            "item_ids": self.item_ids,
            "stats": self.stats,
        }


@transaction.atomic
def materialize_small_value_items_for_cpf(
    *,
    cpf_cnpj: str,
    items: list[ArquivoRetornoItem],
    default_agent: User | None = None,
    apply: bool = False,
) -> SmallValueCpfResult:
    canonical_items = _build_canonical_items(items)
    if not canonical_items:
        raise ValueError("Nenhum item 30/50 encontrado para materialização.")

    value = Decimal(str(canonical_items[0].valor_descontado)).quantize(Decimal("0.01"))
    references = [parse_competencia_text(item.competencia) for item in canonical_items]
    stats: dict[str, int] = defaultdict(int)

    if not apply:
        simulated_associado = canonical_items[-1].associado
        simulated_contract = (
            canonical_items[-1].parcela.ciclo.contrato
            if canonical_items[-1].parcela_id
            else None
        )
        return SmallValueCpfResult(
            cpf_cnpj=cpf_cnpj,
            associado_id=getattr(simulated_associado, "id", 0) or 0,
            contrato_id=getattr(simulated_contract, "id", 0) or 0,
            contrato_codigo=getattr(simulated_contract, "codigo", ""),
            associated_created=False,
            contract_created=False,
            references=[reference.isoformat() for reference in references],
            item_ids=[item.id for item in items],
            stats=dict(stats),
        )

    associado, associated_created, agent_updated = _resolve_associado_for_small_value_items(
        canonical_items=canonical_items,
        default_agent=default_agent,
    )
    if agent_updated:
        stats["associados_agente_atualizado"] += 1

    contract, contract_created = _choose_or_create_small_value_contract(
        associado=associado,
        value=value,
        first_reference=references[0],
        total_parcelas=len(references),
        default_agent=default_agent,
    )
    if contract_created:
        stats["contracts_created"] += 1
    else:
        stats["contracts_reused"] += 1

    stats["contracts_updated"] += _update_small_value_contract_metadata(
        contract,
        value=value,
        first_reference=references[0],
        total_parcelas=len(references),
        default_agent=default_agent,
    )

    desired_cycles = _build_desired_cycles(
        canonical_items=canonical_items,
        value=value,
    )
    parcela_by_reference, rebuild_stats = _rebuild_small_value_contract(
        contrato=contract,
        desired_cycles=desired_cycles,
    )
    for key, count in rebuild_stats.items():
        stats[key] += count

    affected_item_ids: list[int] = []
    for item in items:
        referencia = parse_competencia_text(item.competencia)
        parcela = parcela_by_reference.get(referencia)
        changed_fields: list[str] = []
        if item.associado_id != associado.id:
            item.associado = associado
            changed_fields.append("associado")
        if parcela is not None and item.parcela_id != parcela.id:
            item.parcela = parcela
            changed_fields.append("parcela")
        if changed_fields:
            item.save(update_fields=[*changed_fields, "updated_at"])
            stats["items_linked"] += 1
            affected_item_ids.append(item.id)
        elif item.parcela_id or item.associado_id:
            affected_item_ids.append(item.id)

    stats["payments_linked"] += _link_pagamentos_to_associado(
        associado=associado,
        canonical_items=canonical_items,
        value=value,
    )

    return SmallValueCpfResult(
        cpf_cnpj=cpf_cnpj,
        associado_id=associado.id,
        contrato_id=contract.id,
        contrato_codigo=contract.codigo,
        associated_created=associated_created,
        contract_created=contract_created,
        references=[reference.isoformat() for reference in references],
        item_ids=sorted(set(affected_item_ids)),
        stats=dict(stats),
    )


def build_small_value_items_queryset(
    *,
    arquivo_retorno: ArquivoRetorno | None = None,
    cpf_cnpj: str | None = None,
    competencia_inicial: date | None = None,
    competencia_final: date | None = None,
):
    queryset = ArquivoRetornoItem.objects.filter(
        valor_descontado__in=sorted(SMALL_VALUE_RETURN_AMOUNTS),
    ).select_related(
        "arquivo_retorno",
        "associado",
        "parcela",
        "parcela__ciclo",
        "parcela__ciclo__contrato",
    )
    if arquivo_retorno is not None:
        queryset = queryset.filter(arquivo_retorno=arquivo_retorno)
    if cpf_cnpj:
        queryset = queryset.filter(cpf_cnpj=only_digits(cpf_cnpj))
    if competencia_inicial:
        queryset = queryset.filter(arquivo_retorno__competencia__gte=competencia_inicial)
    if competencia_final:
        queryset = queryset.filter(arquivo_retorno__competencia__lte=competencia_final)
    return queryset.order_by(
        "cpf_cnpj",
        "arquivo_retorno__competencia",
        "arquivo_retorno__processado_em",
        "linha_numero",
        "id",
    )


def materialize_small_value_return_items(
    *,
    arquivo_retorno: ArquivoRetorno | None = None,
    cpf_cnpj: str | None = None,
    competencia_inicial: date | None = None,
    competencia_final: date | None = None,
    apply: bool = False,
) -> dict[str, object]:
    queryset = build_small_value_items_queryset(
        arquivo_retorno=arquivo_retorno,
        cpf_cnpj=cpf_cnpj,
        competencia_inicial=competencia_inicial,
        competencia_final=competencia_final,
    )
    items = list(queryset)
    grouped: dict[str, list[ArquivoRetornoItem]] = defaultdict(list)
    for item in items:
        grouped[only_digits(item.cpf_cnpj)].append(item)

    default_agent = resolve_default_small_value_agent()
    summary: dict[str, int] = defaultdict(int)
    results: list[dict[str, object]] = []
    affected_item_ids: set[int] = set()
    affected_arquivo_ids: set[int] = set()

    for cpf, cpf_items in grouped.items():
        result = materialize_small_value_items_for_cpf(
            cpf_cnpj=cpf,
            items=cpf_items,
            default_agent=default_agent,
            apply=apply,
        )
        results.append(result.as_dict())
        summary["cpf_total"] += 1
        summary["item_total"] += len(cpf_items)
        if result.associated_created:
            summary["associados_criados"] += 1
        if result.contract_created:
            summary["contratos_criados"] += 1
        for key, value in result.stats.items():
            summary[key] += value
        affected_item_ids.update(result.item_ids)
        affected_arquivo_ids.update(item.arquivo_retorno_id for item in cpf_items)

    return {
        "mode": "apply" if apply else "dry-run",
        "summary": dict(summary),
        "results": results,
        "affected_item_ids": sorted(affected_item_ids),
        "affected_arquivo_ids": sorted(affected_arquivo_ids),
    }
