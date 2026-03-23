from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.contratos.cycle_projection import (
    ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES,
    STATUS_VISUAL_FINANCIAL_LABELS,
    STATUS_VISUAL_PHASE_LABELS,
    build_contract_cycle_projection,
)
from apps.contratos.cycle_rebuild import rebind_financial_links_by_reference
from apps.contratos.cycle_timeline import get_cycle_activation_payload
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao
from apps.importacao.models import ArquivoRetornoItem
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import BaixaManual, LiquidacaoContratoItem
from core.file_references import build_filefield_reference

from .models import (
    AdminOverrideChange,
    AdminOverrideEvent,
    Associado,
    Documento,
)


class AdminOverrideConflict(Exception):
    """Raised when the admin is editing stale data."""


@dataclass
class _OverrideContext:
    associado: Associado
    contrato: Contrato | None = None
    ciclo: Ciclo | None = None
    parcela: Parcela | None = None
    refinanciamento: Refinanciamento | None = None
    documento: Documento | None = None
    comprovante: Comprovante | None = None


def _parse_decimal(value: Any, default: Decimal = Decimal("0.00")) -> Decimal:
    if value in (None, ""):
        return default
    return Decimal(str(value))


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _parse_optional_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        raise ValidationError("Data inválida.")
    return parsed


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "isoformat") and callable(value.isoformat):
        return value.isoformat()
    return value


def _normalize_dt(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value.astimezone(timezone.get_current_timezone())


def _assert_version(obj, provided_updated_at: str | None) -> None:
    if not provided_updated_at:
        return
    current = _normalize_dt(getattr(obj, "updated_at", None))
    provided = _normalize_dt(parse_datetime(str(provided_updated_at)))
    if current is None or provided is None:
        return
    if current.replace(microsecond=0) != provided.replace(microsecond=0):
        raise AdminOverrideConflict(
            "Os dados foram alterados por outro usuário. Recarregue a página antes de salvar."
        )


def _file_reference_payload(filefield, *, request=None) -> dict[str, Any]:
    stored_path = str(getattr(filefield, "name", "") or "")
    reference = build_filefield_reference(
        filefield,
        request=request,
        missing_type="legado_sem_arquivo",
    )
    return {
        "url": reference.url,
        "arquivo_referencia": reference.arquivo_referencia or stored_path,
        "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
        "tipo_referencia": reference.tipo_referencia,
    }


def _serialize_documento(documento: Documento, *, request=None) -> dict[str, Any]:
    file_payload = _file_reference_payload(documento.arquivo, request=request)
    return {
        "id": documento.id,
        "tipo": documento.tipo,
        "status": documento.status,
        "observacao": documento.observacao,
        "origem": documento.origem,
        "nome_original": documento.nome_original,
        "created_at": documento.created_at.isoformat() if documento.created_at else None,
        "updated_at": documento.updated_at.isoformat() if documento.updated_at else None,
        "deleted_at": documento.deleted_at.isoformat() if documento.deleted_at else None,
        **file_payload,
    }


def _serialize_comprovante(comprovante: Comprovante, *, request=None) -> dict[str, Any]:
    file_payload = _file_reference_payload(comprovante.arquivo, request=request)
    return {
        "id": comprovante.id,
        "tipo": comprovante.tipo,
        "papel": comprovante.papel,
        "origem": comprovante.origem,
        "status_validacao": comprovante.status_validacao,
        "nome_original": comprovante.nome_original,
        "data_pagamento": (
            comprovante.data_pagamento.isoformat()
            if comprovante.data_pagamento
            else None
        ),
        "created_at": comprovante.created_at.isoformat() if comprovante.created_at else None,
        "updated_at": comprovante.updated_at.isoformat() if comprovante.updated_at else None,
        "deleted_at": comprovante.deleted_at.isoformat() if comprovante.deleted_at else None,
        "contrato_id": comprovante.contrato_id,
        "ciclo_id": comprovante.ciclo_id,
        "refinanciamento_id": comprovante.refinanciamento_id,
        **file_payload,
    }


def _serialize_parcela(parcela: Parcela) -> dict[str, Any]:
    return {
        "id": parcela.id,
        "ciclo_id": parcela.ciclo_id,
        "numero": parcela.numero,
        "referencia_mes": parcela.referencia_mes.isoformat(),
        "valor": str(parcela.valor),
        "data_vencimento": parcela.data_vencimento.isoformat(),
        "status": parcela.status,
        "layout_bucket": parcela.layout_bucket,
        "data_pagamento": (
            parcela.data_pagamento.isoformat() if parcela.data_pagamento else None
        ),
        "observacao": parcela.observacao,
        "updated_at": parcela.updated_at.isoformat() if parcela.updated_at else None,
        "deleted_at": parcela.deleted_at.isoformat() if parcela.deleted_at else None,
    }


def _serialize_ciclo(ciclo: Ciclo, *, include_parcelas: bool = True) -> dict[str, Any]:
    payload = {
        "id": ciclo.id,
        "numero": ciclo.numero,
        "data_inicio": ciclo.data_inicio.isoformat(),
        "data_fim": ciclo.data_fim.isoformat(),
        "status": ciclo.status,
        "valor_total": str(ciclo.valor_total),
        "updated_at": ciclo.updated_at.isoformat() if ciclo.updated_at else None,
        "deleted_at": ciclo.deleted_at.isoformat() if ciclo.deleted_at else None,
    }
    if include_parcelas:
        payload["parcelas"] = [
            _serialize_parcela(parcela)
            for parcela in Parcela.all_objects.filter(
                ciclo=ciclo,
                deleted_at__isnull=True,
            )
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("numero", "id")
        ]
    return payload


def _serialize_contrato(contrato: Contrato, *, include_ciclos: bool = True) -> dict[str, Any]:
    payload = {
        "id": contrato.id,
        "codigo": contrato.codigo,
        "status": contrato.status,
        "valor_bruto": str(contrato.valor_bruto),
        "valor_liquido": str(contrato.valor_liquido),
        "valor_mensalidade": str(contrato.valor_mensalidade),
        "prazo_meses": contrato.prazo_meses,
        "taxa_antecipacao": str(contrato.taxa_antecipacao),
        "margem_disponivel": str(contrato.margem_disponivel),
        "valor_total_antecipacao": str(contrato.valor_total_antecipacao),
        "doacao_associado": str(contrato.doacao_associado),
        "comissao_agente": str(contrato.comissao_agente),
        "data_contrato": contrato.data_contrato.isoformat() if contrato.data_contrato else None,
        "data_aprovacao": contrato.data_aprovacao.isoformat() if contrato.data_aprovacao else None,
        "data_primeira_mensalidade": (
            contrato.data_primeira_mensalidade.isoformat()
            if contrato.data_primeira_mensalidade
            else None
        ),
        "mes_averbacao": contrato.mes_averbacao.isoformat() if contrato.mes_averbacao else None,
        "auxilio_liberado_em": (
            contrato.auxilio_liberado_em.isoformat() if contrato.auxilio_liberado_em else None
        ),
        "agente_id": contrato.agente_id,
        "admin_manual_layout_enabled": contrato.admin_manual_layout_enabled,
        "updated_at": contrato.updated_at.isoformat() if contrato.updated_at else None,
    }
    if include_ciclos:
        payload["ciclos"] = [
            _serialize_ciclo(ciclo)
            for ciclo in contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id")
        ]
    return payload


def _serialize_associado(associado: Associado) -> dict[str, Any]:
    return {
        "id": associado.id,
        "matricula": associado.matricula,
        "tipo_documento": associado.tipo_documento,
        "nome_completo": associado.nome_completo,
        "cpf_cnpj": associado.cpf_cnpj,
        "rg": associado.rg,
        "orgao_expedidor": associado.orgao_expedidor,
        "email": associado.email,
        "telefone": associado.telefone,
        "data_nascimento": (
            associado.data_nascimento.isoformat() if associado.data_nascimento else None
        ),
        "profissao": associado.profissao,
        "estado_civil": associado.estado_civil,
        "orgao_publico": associado.orgao_publico,
        "matricula_orgao": associado.matricula_orgao,
        "cargo": associado.cargo,
        "status": associado.status,
        "observacao": associado.observacao,
        "agente_responsavel_id": associado.agente_responsavel_id,
        "percentual_repasse": str(associado.auxilio_taxa),
        "endereco": associado.build_endereco_payload(),
        "dados_bancarios": associado.build_dados_bancarios_payload(),
        "contato": associado.build_contato_payload(),
        "updated_at": associado.updated_at.isoformat() if associado.updated_at else None,
    }


def _serialize_refinanciamento(refinanciamento: Refinanciamento) -> dict[str, Any]:
    return {
        "id": refinanciamento.id,
        "status": refinanciamento.status,
        "competencia_solicitada": refinanciamento.competencia_solicitada.isoformat(),
        "valor_refinanciamento": str(refinanciamento.valor_refinanciamento),
        "repasse_agente": str(refinanciamento.repasse_agente),
        "executado_em": refinanciamento.executado_em.isoformat() if refinanciamento.executado_em else None,
        "data_ativacao_ciclo": (
            refinanciamento.data_ativacao_ciclo.isoformat()
            if refinanciamento.data_ativacao_ciclo
            else None
        ),
        "motivo_bloqueio": refinanciamento.motivo_bloqueio,
        "observacao": refinanciamento.observacao,
        "analista_note": refinanciamento.analista_note,
        "coordenador_note": refinanciamento.coordenador_note,
        "reviewed_by_id": refinanciamento.reviewed_by_id,
        "updated_at": refinanciamento.updated_at.isoformat() if refinanciamento.updated_at else None,
    }


def _serialize_esteira(esteira: EsteiraItem | None) -> dict[str, Any]:
    if esteira is None:
        return {}
    return {
        "id": esteira.id,
        "etapa_atual": esteira.etapa_atual,
        "status": esteira.status,
        "prioridade": esteira.prioridade,
        "observacao": esteira.observacao,
        "analista_responsavel_id": esteira.analista_responsavel_id,
        "coordenador_responsavel_id": esteira.coordenador_responsavel_id,
        "tesoureiro_responsavel_id": esteira.tesoureiro_responsavel_id,
        "updated_at": esteira.updated_at.isoformat() if esteira.updated_at else None,
    }


def _parcel_financial_flags(parcela: Parcela | None) -> dict[str, bool]:
    if parcela is None:
        return {
            "tem_retorno": False,
            "tem_baixa_manual": False,
            "tem_liquidacao": False,
        }
    return {
        "tem_retorno": ArquivoRetornoItem.objects.filter(parcela=parcela).exists(),
        "tem_baixa_manual": BaixaManual.objects.filter(parcela=parcela).exists(),
        "tem_liquidacao": LiquidacaoContratoItem.objects.filter(parcela=parcela).exists(),
    }


def _build_editor_item(
    item: dict[str, Any],
    *,
    actual_parcela: Parcela | None,
    bucket: str,
) -> dict[str, Any]:
    return {
        "id": actual_parcela.id if actual_parcela else None,
        "numero": int(item.get("numero") or 0),
        "referencia_mes": str(item["referencia_mes"]),
        "valor": str(item.get("valor") or "0.00"),
        "data_vencimento": str(item.get("data_vencimento") or item["referencia_mes"]),
        "status": str(item.get("status") or Parcela.Status.EM_PREVISAO),
        "data_pagamento": item.get("data_pagamento"),
        "observacao": str(item.get("observacao") or ""),
        "layout_bucket": actual_parcela.layout_bucket if actual_parcela else bucket,
        "updated_at": (
            actual_parcela.updated_at.isoformat() if actual_parcela and actual_parcela.updated_at else None
        ),
        "financial_flags": _parcel_financial_flags(actual_parcela),
    }


def _active_operational_refinanciamento(contrato: Contrato) -> Refinanciamento | None:
    return (
        Refinanciamento.objects.filter(
            contrato_origem=contrato,
            deleted_at__isnull=True,
            status__in=ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES,
        )
        .order_by("-created_at", "-id")
        .first()
    )


def _manual_phase_slug(
    *,
    contrato: Contrato,
    ciclo: Ciclo,
    is_latest_cycle: bool,
) -> str:
    associado_status = getattr(contrato.associado, "status", "")
    if associado_status == Associado.Status.INATIVO or contrato.status == Contrato.Status.CANCELADO:
        return "contrato_desativado"
    if contrato.status == Contrato.Status.ENCERRADO:
        return "contrato_encerrado"
    if is_latest_cycle:
        refinanciamento = _active_operational_refinanciamento(contrato)
        if refinanciamento is not None:
            mapping = {
                Refinanciamento.Status.APTO_A_RENOVAR: "apto_a_renovar",
                Refinanciamento.Status.EM_ANALISE_RENOVACAO: "renovacao_em_analise",
                Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO: "aguardando_coordenacao",
                Refinanciamento.Status.APROVADO_PARA_RENOVACAO: "aprovado_para_renovacao",
            }
            normalized = refinanciamento.status
            if normalized in mapping:
                return mapping[normalized]
    if ciclo.status == Ciclo.Status.CICLO_RENOVADO:
        return "ciclo_renovado"
    if ciclo.status == Ciclo.Status.APTO_A_RENOVAR:
        return "apto_a_renovar"
    return "ciclo_aberto"


def _manual_financial_slug(
    *,
    contrato: Contrato,
    has_unpaid: bool,
) -> str:
    associado_status = getattr(contrato.associado, "status", "")
    if associado_status == Associado.Status.INATIVO or contrato.status == Contrato.Status.CANCELADO:
        return "ciclo_desativado"
    if has_unpaid and associado_status == Associado.Status.INADIMPLENTE:
        return "ciclo_inadimplente"
    if has_unpaid:
        return "ciclo_com_pendencia"
    return "ciclo_em_dia"


def _build_manual_contract_projection(
    contrato: Contrato,
    *,
    include_documents: bool = False,
) -> dict[str, Any]:
    ciclos = list(
        contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id")
    )
    parcelas = list(
        Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
        .exclude(status=Parcela.Status.CANCELADO)
        .select_related("ciclo")
        .order_by("ciclo__numero", "numero", "id")
    )
    by_cycle: dict[int, list[Parcela]] = defaultdict(list)
    unpaid_rows: list[dict[str, Any]] = []
    movement_rows: list[dict[str, Any]] = []

    for parcela in parcelas:
        if parcela.layout_bucket == Parcela.LayoutBucket.UNPAID:
            unpaid_rows.append(
                {
                    "id": parcela.id,
                    "contrato_id": contrato.id,
                    "contrato_codigo": contrato.codigo,
                    "referencia_mes": parcela.referencia_mes,
                    "valor": parcela.valor,
                    "status": parcela.status,
                    "data_pagamento": parcela.data_pagamento,
                    "observacao": parcela.observacao,
                    "source": "admin_override",
                }
            )
            continue
        if parcela.layout_bucket == Parcela.LayoutBucket.MOVEMENT:
            movement_rows.append(
                {
                    "id": parcela.id,
                    "contrato_id": contrato.id,
                    "contrato_codigo": contrato.codigo,
                    "referencia_mes": parcela.referencia_mes,
                    "valor": parcela.valor,
                    "status": parcela.status,
                    "data_pagamento": parcela.data_pagamento,
                    "observacao": parcela.observacao,
                    "source": "admin_override",
                }
            )
            continue
        by_cycle[parcela.ciclo_id].append(parcela)

    has_unpaid = bool(unpaid_rows)
    projected_cycles: list[dict[str, Any]] = []
    latest_cycle_number = max((ciclo.numero for ciclo in ciclos), default=0)
    for ciclo in ciclos:
        cycle_parcelas = by_cycle.get(ciclo.id, [])
        activation = get_cycle_activation_payload(ciclo)
        phase_slug = _manual_phase_slug(
            contrato=contrato,
            ciclo=ciclo,
            is_latest_cycle=ciclo.numero == latest_cycle_number,
        )
        financial_slug = _manual_financial_slug(contrato=contrato, has_unpaid=has_unpaid)
        refinanciamento_operacional = (
            _active_operational_refinanciamento(contrato)
            if ciclo.numero == latest_cycle_number
            else None
        )
        comprovantes_ciclo = []
        termo_antecipacao = None
        if include_documents:
            filtered = list(
                Comprovante.objects.filter(ciclo=ciclo, deleted_at__isnull=True)
                .order_by("created_at", "id")
            )
            termo = next(
                (item for item in filtered if item.tipo == Comprovante.Tipo.TERMO_ANTECIPACAO),
                None,
            )
            termo_antecipacao = _serialize_comprovante(termo) if termo else None
            comprovantes_ciclo = [
                _serialize_comprovante(item)
                for item in filtered
                if item.tipo != Comprovante.Tipo.TERMO_ANTECIPACAO
            ]
        projected_cycles.append(
            {
                "id": ciclo.id,
                "contrato_id": contrato.id,
                "contrato_codigo": contrato.codigo,
                "contrato_status": contrato.status,
                "numero": ciclo.numero,
                "data_inicio": ciclo.data_inicio,
                "data_fim": ciclo.data_fim,
                "status": ciclo.status,
                "fase_ciclo": phase_slug,
                "situacao_financeira": financial_slug,
                "status_visual_slug": phase_slug,
                "status_visual_label": STATUS_VISUAL_PHASE_LABELS[phase_slug],
                "valor_total": ciclo.valor_total,
                "data_ativacao_ciclo": activation["data_ativacao_ciclo"],
                "origem_data_ativacao": activation["origem_data_ativacao"],
                "ativacao_inferida": activation["ativacao_inferida"],
                "data_solicitacao_renovacao": activation["data_solicitacao_renovacao"],
                "data_renovacao": None,
                "origem_renovacao": "",
                "primeira_competencia_ciclo": (
                    cycle_parcelas[0].referencia_mes if cycle_parcelas else ciclo.data_inicio
                ),
                "ultima_competencia_ciclo": (
                    cycle_parcelas[-1].referencia_mes if cycle_parcelas else ciclo.data_fim
                ),
                "resumo_referencias": ", ".join(
                    parcela.referencia_mes.strftime("%m/%Y") for parcela in cycle_parcelas
                ),
                "refinanciamento_id": refinanciamento_operacional.id if refinanciamento_operacional else None,
                "legacy_refinanciamento_id": None,
                "comprovantes_ciclo": comprovantes_ciclo,
                "termo_antecipacao": termo_antecipacao,
                "parcelas": [
                    {
                        "id": parcela.id,
                        "numero": parcela.numero,
                        "referencia_mes": parcela.referencia_mes,
                        "valor": parcela.valor,
                        "data_vencimento": parcela.data_vencimento,
                        "status": parcela.status,
                        "data_pagamento": parcela.data_pagamento,
                        "observacao": parcela.observacao,
                    }
                    for parcela in cycle_parcelas
                ],
            }
        )

    refinanciamento_ativo = _active_operational_refinanciamento(contrato)
    status_renovacao = ""
    refinanciamento_id = None
    if refinanciamento_ativo is not None:
        status_renovacao = refinanciamento_ativo.status
        refinanciamento_id = refinanciamento_ativo.id
    elif ciclos and ciclos[-1].status == Ciclo.Status.APTO_A_RENOVAR:
        status_renovacao = Refinanciamento.Status.APTO_A_RENOVAR

    return {
        "cycle_size": max(int(contrato.prazo_meses or 3), 1),
        "cycles": list(sorted(projected_cycles, key=lambda item: item["numero"], reverse=True)),
        "unpaid_months": sorted(unpaid_rows, key=lambda item: item["referencia_mes"], reverse=True),
        "possui_meses_nao_descontados": bool(unpaid_rows),
        "meses_nao_descontados_count": len(unpaid_rows),
        "status_renovacao": status_renovacao,
        "refinanciamento_id": refinanciamento_id,
        "movimentos_financeiros_avulsos": sorted(
            movement_rows,
            key=lambda item: item["referencia_mes"],
        ),
    }


class AdminOverrideService:
    @staticmethod
    def build_associado_history_payload(associado: Associado, *, request=None) -> list[dict[str, Any]]:
        events = (
            AdminOverrideEvent.objects.filter(associado=associado)
            .select_related(
                "realizado_por",
                "revertida_por",
                "contrato",
                "ciclo",
                "parcela",
                "refinanciamento",
                "documento",
                "comprovante",
            )
            .prefetch_related("changes")
            .order_by("-created_at", "-id")
        )
        payload: list[dict[str, Any]] = []
        for event in events:
            payload.append(
                {
                    "id": event.id,
                    "escopo": event.escopo,
                    "resumo": event.resumo,
                    "motivo": event.motivo,
                    "confirmacao_dupla": event.confirmacao_dupla,
                    "created_at": event.created_at,
                    "realizado_por": {
                        "id": event.realizado_por_id,
                        "full_name": event.realizado_por.full_name,
                    },
                    "revertida_em": event.revertida_em,
                    "revertida_por": (
                        {
                            "id": event.revertida_por_id,
                            "full_name": event.revertida_por.full_name,
                        }
                        if event.revertida_por_id
                        else None
                    ),
                    "motivo_reversao": event.motivo_reversao,
                    "before_snapshot": event.before_snapshot,
                    "after_snapshot": event.after_snapshot,
                    "changes": [
                        {
                            "id": change.id,
                            "entity_type": change.entity_type,
                            "entity_id": change.entity_id,
                            "competencia_referencia": change.competencia_referencia,
                            "resumo": change.resumo,
                            "before_snapshot": change.before_snapshot,
                            "after_snapshot": change.after_snapshot,
                        }
                        for change in event.changes.all()
                    ],
                }
            )
        return payload

    @staticmethod
    def build_associado_editor_payload(associado: Associado) -> dict[str, Any]:
        contratos = list(
            associado.contratos.exclude(status=Contrato.Status.CANCELADO).order_by("-created_at")
        )
        payload_contracts: list[dict[str, Any]] = []
        for contrato in contratos:
            projection = build_contract_cycle_projection(contrato, include_documents=True)
            current_cycles = {
                ciclo.numero: ciclo
                for ciclo in contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id")
            }
            current_parcelas_by_ref: dict[date, Parcela] = {}
            for parcela in (
                Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
                .exclude(status=Parcela.Status.CANCELADO)
                .order_by("updated_at", "id")
            ):
                current_parcelas_by_ref[parcela.referencia_mes] = parcela

            cycles_payload = []
            for cycle in sorted(projection["cycles"], key=lambda item: item["numero"]):
                actual_cycle = current_cycles.get(int(cycle["numero"]))
                cycles_payload.append(
                    {
                        "id": actual_cycle.id if actual_cycle else None,
                        "numero": cycle["numero"],
                        "data_inicio": str(cycle["data_inicio"]),
                        "data_fim": str(cycle["data_fim"]),
                        "status": cycle["status"],
                        "valor_total": str(cycle["valor_total"]),
                        "updated_at": (
                            actual_cycle.updated_at.isoformat()
                            if actual_cycle and actual_cycle.updated_at
                            else None
                        ),
                        "comprovantes_ciclo": cycle.get("comprovantes_ciclo", []),
                        "termo_antecipacao": cycle.get("termo_antecipacao"),
                        "parcelas": [
                            _build_editor_item(
                                parcela,
                                actual_parcela=current_parcelas_by_ref.get(parcela["referencia_mes"]),
                                bucket=Parcela.LayoutBucket.CYCLE,
                            )
                            for parcela in cycle["parcelas"]
                        ],
                    }
                )

            unpaid_payload = [
                _build_editor_item(
                    item,
                    actual_parcela=current_parcelas_by_ref.get(item["referencia_mes"]),
                    bucket=Parcela.LayoutBucket.UNPAID,
                )
                for item in projection["unpaid_months"]
            ]
            movement_payload = [
                _build_editor_item(
                    item,
                    actual_parcela=current_parcelas_by_ref.get(item["referencia_mes"]),
                    bucket=Parcela.LayoutBucket.MOVEMENT,
                )
                for item in projection["movimentos_financeiros_avulsos"]
            ]
            payload_contracts.append(
                {
                    "id": contrato.id,
                    "updated_at": contrato.updated_at.isoformat() if contrato.updated_at else None,
                    "codigo": contrato.codigo,
                    "status": contrato.status,
                    "valor_bruto": str(contrato.valor_bruto),
                    "valor_liquido": str(contrato.valor_liquido),
                    "valor_mensalidade": str(contrato.valor_mensalidade),
                    "prazo_meses": contrato.prazo_meses,
                    "taxa_antecipacao": str(contrato.taxa_antecipacao),
                    "margem_disponivel": str(contrato.margem_disponivel),
                    "valor_total_antecipacao": str(contrato.valor_total_antecipacao),
                    "doacao_associado": str(contrato.doacao_associado),
                    "comissao_agente": str(contrato.comissao_agente),
                    "data_contrato": (
                        contrato.data_contrato.isoformat() if contrato.data_contrato else None
                    ),
                    "data_aprovacao": contrato.data_aprovacao.isoformat() if contrato.data_aprovacao else None,
                    "data_primeira_mensalidade": (
                        contrato.data_primeira_mensalidade.isoformat()
                        if contrato.data_primeira_mensalidade
                        else None
                    ),
                    "mes_averbacao": contrato.mes_averbacao.isoformat() if contrato.mes_averbacao else None,
                    "auxilio_liberado_em": (
                        contrato.auxilio_liberado_em.isoformat()
                        if contrato.auxilio_liberado_em
                        else None
                    ),
                    "ciclos": cycles_payload,
                    "meses_nao_pagos": unpaid_payload,
                    "movimentos_financeiros_avulsos": movement_payload,
                    "refinanciamento_ativo": (
                        _serialize_refinanciamento(_active_operational_refinanciamento(contrato))
                        if _active_operational_refinanciamento(contrato)
                        else None
                    ),
                }
            )
        return {
            "associado": _serialize_associado(associado),
            "contratos": payload_contracts,
            "esteira": _serialize_esteira(getattr(associado, "esteira_item", None)),
            "documentos": [
                _serialize_documento(documento)
                for documento in associado.documentos.filter(deleted_at__isnull=True).order_by("tipo", "id")
            ],
        }

    @staticmethod
    def build_contract_projection_for_response(contrato: Contrato, *, include_documents: bool = True) -> dict[str, Any]:
        if contrato.admin_manual_layout_enabled:
            return _build_manual_contract_projection(contrato, include_documents=include_documents)
        return build_contract_cycle_projection(contrato, include_documents=include_documents)

    @staticmethod
    def _record_event(
        *,
        context: _OverrideContext,
        user,
        escopo: str,
        resumo: str,
        motivo: str,
        before_snapshot: dict[str, Any],
        after_snapshot: dict[str, Any],
        changes: list[dict[str, Any]],
    ) -> AdminOverrideEvent:
        event = AdminOverrideEvent.objects.create(
            associado=context.associado,
            contrato=context.contrato,
            ciclo=context.ciclo,
            parcela=context.parcela,
            refinanciamento=context.refinanciamento,
            documento=context.documento,
            comprovante=context.comprovante,
            realizado_por=user,
            escopo=escopo,
            resumo=resumo,
            motivo=motivo,
            before_snapshot=_json_safe(before_snapshot),
            after_snapshot=_json_safe(after_snapshot),
            confirmacao_dupla=True,
        )
        for change in changes:
            AdminOverrideChange.objects.create(
                evento=event,
                entity_type=change["entity_type"],
                entity_id=change["entity_id"],
                competencia_referencia=change.get("competencia_referencia"),
                resumo=change["resumo"],
                before_snapshot=_json_safe(change.get("before_snapshot") or {}),
                after_snapshot=_json_safe(change.get("after_snapshot") or {}),
            )
        return event

    @staticmethod
    def apply_associado_core_override(
        *,
        associado: Associado,
        payload: dict[str, Any],
        user,
    ) -> Associado:
        with transaction.atomic():
            _assert_version(associado, payload.get("updated_at"))
            contrato = (
                associado.contratos.exclude(status=Contrato.Status.CANCELADO)
                .order_by("-created_at")
                .first()
            )
            if contrato is not None:
                _assert_version(contrato, payload.get("contrato_updated_at"))
            motivo = str(payload.get("motivo") or "").strip()
            if not motivo:
                raise ValidationError("O motivo da alteração é obrigatório.")

            before_associado = _serialize_associado(associado)
            before_contrato = (
                _serialize_contrato(contrato, include_ciclos=False) if contrato else {}
            )

            simple_fields = [
                "nome_completo",
                "rg",
                "orgao_expedidor",
                "profissao",
                "estado_civil",
                "cargo",
                "status",
                "observacao",
            ]
            for field in simple_fields:
                if field in payload:
                    setattr(associado, field, payload.get(field) or "")
            if "data_nascimento" in payload:
                associado.data_nascimento = _parse_optional_date(
                    payload.get("data_nascimento")
                )
            if "agente_responsavel_id" in payload:
                associado.agente_responsavel_id = payload.get("agente_responsavel_id")
            if (
                "percentual_repasse" in payload
                and payload.get("percentual_repasse") not in (None, "")
            ):
                associado.auxilio_taxa = _parse_decimal(payload.get("percentual_repasse"))

            endereco = payload.get("endereco") or {}
            if endereco:
                associado.cep = str(endereco.get("cep") or associado.cep)
                associado.logradouro = str(
                    endereco.get("logradouro")
                    or endereco.get("endereco")
                    or associado.logradouro
                )
                associado.numero = str(endereco.get("numero") or associado.numero)
                associado.complemento = str(
                    endereco.get("complemento") or associado.complemento
                )
                associado.bairro = str(endereco.get("bairro") or associado.bairro)
                associado.cidade = str(endereco.get("cidade") or associado.cidade)
                associado.uf = str(endereco.get("uf") or associado.uf)

            dados_bancarios = payload.get("dados_bancarios") or {}
            if dados_bancarios:
                associado.banco = str(dados_bancarios.get("banco") or associado.banco)
                associado.agencia = str(
                    dados_bancarios.get("agencia") or associado.agencia
                )
                associado.conta = str(dados_bancarios.get("conta") or associado.conta)
                associado.tipo_conta = str(
                    dados_bancarios.get("tipo_conta") or associado.tipo_conta
                )
                associado.chave_pix = str(
                    dados_bancarios.get("chave_pix") or associado.chave_pix
                )

            contato = payload.get("contato") or {}
            if contato:
                associado.telefone = str(contato.get("celular") or associado.telefone)
                associado.email = str(contato.get("email") or associado.email)
                associado.orgao_publico = str(
                    contato.get("orgao_publico") or associado.orgao_publico
                )
                associado.situacao_servidor = str(
                    contato.get("situacao_servidor") or associado.situacao_servidor
                )
                associado.matricula_orgao = str(
                    contato.get("matricula_servidor") or associado.matricula_orgao
                )

            associado.save()

            if contrato is not None:
                contract_fields = {
                    "valor_bruto": "valor_bruto_total",
                    "valor_liquido": "valor_liquido",
                    "prazo_meses": "prazo_meses",
                    "taxa_antecipacao": "taxa_antecipacao",
                    "valor_mensalidade": "mensalidade",
                    "margem_disponivel": "margem_disponivel",
                }
                for field, source_key in contract_fields.items():
                    if source_key not in payload or payload.get(source_key) in (None, ""):
                        continue
                    value = payload.get(source_key)
                    setattr(
                        contrato,
                        field,
                        int(value) if field == "prazo_meses" else _parse_decimal(value),
                    )
                if "status_contrato" in payload:
                    contrato.status = str(payload.get("status_contrato") or contrato.status)
                if "agente_responsavel_id" in payload:
                    contrato.agente_id = payload.get("agente_responsavel_id")
                contrato.save()

            after_associado = _serialize_associado(associado)
            after_contrato = (
                _serialize_contrato(contrato, include_ciclos=False) if contrato else {}
            )
            AdminOverrideService._record_event(
                context=_OverrideContext(associado=associado, contrato=contrato),
                user=user,
                escopo=AdminOverrideEvent.Scope.ASSOCIADO,
                resumo="Atualização administrativa do cadastro do associado",
                motivo=motivo,
                before_snapshot={
                    "associado": before_associado,
                    "contrato": before_contrato,
                },
                after_snapshot={
                    "associado": after_associado,
                    "contrato": after_contrato,
                },
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.ASSOCIADO,
                        "entity_id": associado.id,
                        "resumo": "Dados do associado atualizados",
                        "before_snapshot": before_associado,
                        "after_snapshot": after_associado,
                    },
                    *(
                        [
                            {
                                "entity_type": AdminOverrideChange.EntityType.CONTRATO,
                                "entity_id": contrato.id,
                                "resumo": "Dados do contrato atualizados via cadastro do associado",
                                "before_snapshot": before_contrato,
                                "after_snapshot": after_contrato,
                            }
                        ]
                        if contrato is not None
                        else []
                    ),
                ],
            )
            return associado

    @staticmethod
    def apply_contract_core_override(
        *,
        contrato: Contrato,
        payload: dict[str, Any],
        user,
    ) -> Contrato:
        with transaction.atomic():
            _assert_version(contrato, payload.get("updated_at"))
            motivo = str(payload.get("motivo") or "").strip()
            if not motivo:
                raise ValidationError("O motivo da alteração é obrigatório.")
            before = _serialize_contrato(contrato, include_ciclos=False)
            numeric_fields = {
                "valor_bruto",
                "valor_liquido",
                "valor_mensalidade",
                "taxa_antecipacao",
                "margem_disponivel",
                "valor_total_antecipacao",
                "doacao_associado",
                "comissao_agente",
            }
            for field in [
                "status",
                "contato_web",
                "termos_web",
                "agente_id",
            ]:
                if field in payload:
                    setattr(contrato, field, payload.get(field))
            for field in numeric_fields:
                if field in payload and payload.get(field) not in (None, ""):
                    setattr(contrato, field, _parse_decimal(payload.get(field)))
            for field in [
                "data_contrato",
                "data_aprovacao",
                "data_primeira_mensalidade",
                "mes_averbacao",
                "auxilio_liberado_em",
            ]:
                if field in payload:
                    setattr(contrato, field, _parse_optional_date(payload.get(field)))
            contrato.save()
            after = _serialize_contrato(contrato, include_ciclos=False)
            AdminOverrideService._record_event(
                context=_OverrideContext(associado=contrato.associado, contrato=contrato),
                user=user,
                escopo=AdminOverrideEvent.Scope.CONTRATO,
                resumo=f"Atualização administrativa do contrato {contrato.codigo}",
                motivo=motivo,
                before_snapshot=before,
                after_snapshot=after,
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.CONTRATO,
                        "entity_id": contrato.id,
                        "resumo": "Dados do contrato atualizados",
                        "before_snapshot": before,
                        "after_snapshot": after,
                    }
                ],
            )
            return contrato

    @staticmethod
    def apply_refinanciamento_override(
        *,
        refinanciamento: Refinanciamento,
        payload: dict[str, Any],
        user,
    ) -> Refinanciamento:
        with transaction.atomic():
            _assert_version(refinanciamento, payload.get("updated_at"))
            motivo = str(payload.get("motivo") or "").strip()
            if not motivo:
                raise ValidationError("O motivo da alteração é obrigatório.")
            before = _serialize_refinanciamento(refinanciamento)
            for field in [
                "status",
                "motivo_bloqueio",
                "observacao",
                "analista_note",
                "coordenador_note",
            ]:
                if field in payload:
                    setattr(refinanciamento, field, payload.get(field) or "")
            for field in ["competencia_solicitada"]:
                if field in payload:
                    setattr(
                        refinanciamento,
                        field,
                        _parse_optional_date(payload.get(field)),
                    )
            for field in ["valor_refinanciamento", "repasse_agente"]:
                if field in payload and payload.get(field) not in (None, ""):
                    setattr(refinanciamento, field, _parse_decimal(payload.get(field)))
            for field in ["executado_em", "data_ativacao_ciclo"]:
                if field in payload:
                    raw = payload.get(field)
                    setattr(refinanciamento, field, parse_datetime(str(raw)) if raw else None)
            if "reviewed_by_id" in payload:
                refinanciamento.reviewed_by_id = payload.get("reviewed_by_id")
            refinanciamento.save()
            after = _serialize_refinanciamento(refinanciamento)
            AdminOverrideService._record_event(
                context=_OverrideContext(
                    associado=refinanciamento.associado,
                    contrato=refinanciamento.contrato_origem,
                    refinanciamento=refinanciamento,
                ),
                user=user,
                escopo=AdminOverrideEvent.Scope.REFINANCIAMENTO,
                resumo="Atualização administrativa da renovação",
                motivo=motivo,
                before_snapshot=before,
                after_snapshot=after,
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.REFINANCIAMENTO,
                        "entity_id": refinanciamento.id,
                        "resumo": "Dados da renovação atualizados",
                        "before_snapshot": before,
                        "after_snapshot": after,
                    }
                ],
            )
            return refinanciamento

    @staticmethod
    def apply_esteira_override(
        *,
        associado: Associado,
        payload: dict[str, Any],
        user,
    ) -> EsteiraItem:
        with transaction.atomic():
            esteira = getattr(associado, "esteira_item", None)
            if esteira is None:
                raise ValidationError("Associado sem item de esteira.")
            _assert_version(esteira, payload.get("updated_at"))
            motivo = str(payload.get("motivo") or "").strip()
            if not motivo:
                raise ValidationError("O motivo da alteração é obrigatório.")
            before = _serialize_esteira(esteira)
            previous_stage = esteira.etapa_atual
            previous_status = esteira.status
            if "etapa_atual" in payload:
                esteira.etapa_atual = str(
                    payload.get("etapa_atual") or esteira.etapa_atual
                )
            if "status" in payload:
                esteira.status = str(payload.get("status") or esteira.status)
            if "prioridade" in payload and payload.get("prioridade") not in (None, ""):
                esteira.prioridade = int(payload.get("prioridade"))
            if "observacao" in payload:
                esteira.observacao = str(payload.get("observacao") or "")
            esteira.save()
            Transicao.objects.create(
                esteira_item=esteira,
                acao="admin_override",
                de_status=previous_stage,
                para_status=esteira.etapa_atual,
                de_situacao=previous_status,
                para_situacao=esteira.status,
                realizado_por=user,
                observacao=motivo,
            )
            after = _serialize_esteira(esteira)
            AdminOverrideService._record_event(
                context=_OverrideContext(associado=associado),
                user=user,
                escopo=AdminOverrideEvent.Scope.ESTEIRA,
                resumo="Override administrativo da esteira",
                motivo=motivo,
                before_snapshot=before,
                after_snapshot=after,
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.ESTEIRA,
                        "entity_id": esteira.id,
                        "resumo": "Status da esteira atualizado",
                        "before_snapshot": before,
                        "after_snapshot": after,
                    }
                ],
            )
            return esteira

    @staticmethod
    def _create_document_version(
        *,
        documento: Documento,
        payload: dict[str, Any],
        user,
    ) -> Documento:
        new_documento = Documento.objects.create(
            associado=documento.associado,
            tipo=documento.tipo,
            arquivo=payload.get("arquivo") or documento.arquivo,
            origem=documento.origem,
            status=payload.get("status") or documento.status,
            observacao=payload.get("observacao") or documento.observacao,
        )
        documento.soft_delete()
        return new_documento

    @staticmethod
    def versionar_documento(
        *,
        documento: Documento,
        payload: dict[str, Any],
        user,
        request=None,
    ) -> Documento:
        _assert_version(documento, payload.get("updated_at"))
        motivo = str(payload.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("O motivo da alteração é obrigatório.")
        before = _serialize_documento(documento, request=request)
        with transaction.atomic():
            novo = AdminOverrideService._create_document_version(
                documento=documento,
                payload=payload,
                user=user,
            )
            after = _serialize_documento(novo, request=request)
            AdminOverrideService._record_event(
                context=_OverrideContext(
                    associado=documento.associado,
                    documento=novo,
                ),
                user=user,
                escopo=AdminOverrideEvent.Scope.DOCUMENTO,
                resumo="Nova versão de documento do associado",
                motivo=motivo,
                before_snapshot=before,
                after_snapshot=after,
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.DOCUMENTO,
                        "entity_id": novo.id,
                        "resumo": "Documento versionado pelo admin",
                        "before_snapshot": before,
                        "after_snapshot": after,
                    }
                ],
            )
            return novo

    @staticmethod
    def versionar_comprovante(
        *,
        comprovante: Comprovante,
        payload: dict[str, Any],
        user,
        request=None,
    ) -> Comprovante:
        _assert_version(comprovante, payload.get("updated_at"))
        motivo = str(payload.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("O motivo da alteração é obrigatório.")
        before = _serialize_comprovante(comprovante, request=request)
        with transaction.atomic():
            novo = Comprovante.objects.create(
                refinanciamento=comprovante.refinanciamento,
                contrato=comprovante.contrato,
                ciclo=comprovante.ciclo,
                tipo=payload.get("tipo") or comprovante.tipo,
                papel=payload.get("papel") or comprovante.papel,
                arquivo=payload.get("arquivo") or comprovante.arquivo,
                mime=getattr(payload.get("arquivo"), "content_type", "") or comprovante.mime,
                size_bytes=getattr(payload.get("arquivo"), "size", None) or comprovante.size_bytes,
                data_pagamento=(
                    parse_datetime(str(payload.get("data_pagamento")))
                    if payload.get("data_pagamento")
                    else comprovante.data_pagamento
                ),
                origem=payload.get("origem") or comprovante.origem,
                agente_snapshot=comprovante.agente_snapshot,
                filial_snapshot=comprovante.filial_snapshot,
                enviado_por=user,
                status_validacao=payload.get("status_validacao") or comprovante.status_validacao,
            )
            comprovante.soft_delete()
            after = _serialize_comprovante(novo, request=request)
            AdminOverrideService._record_event(
                context=_OverrideContext(
                    associado=novo.contrato.associado if novo.contrato_id else novo.refinanciamento.associado,
                    contrato=novo.contrato or novo.refinanciamento.contrato_origem,
                    comprovante=novo,
                    refinanciamento=novo.refinanciamento,
                ),
                user=user,
                escopo=AdminOverrideEvent.Scope.COMPROVANTE,
                resumo="Nova versão de comprovante",
                motivo=motivo,
                before_snapshot=before,
                after_snapshot=after,
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.COMPROVANTE,
                        "entity_id": novo.id,
                        "resumo": "Comprovante versionado pelo admin",
                        "before_snapshot": before,
                        "after_snapshot": after,
                    }
                ],
            )
            return novo

    @staticmethod
    def criar_comprovantes_ciclo(
        *,
        ciclo: Ciclo,
        payload: dict[str, Any],
        user,
        request=None,
    ) -> list[Comprovante]:
        motivo = str(payload.get("motivo") or "").strip()
        arquivos = [arquivo for arquivo in payload.get("arquivos", []) if arquivo]
        if not motivo:
            raise ValidationError("O motivo da alteração é obrigatório.")
        if not arquivos:
            raise ValidationError("Envie ao menos um comprovante para o ciclo.")

        before = {
            "ciclo_id": ciclo.id,
            "contrato_id": ciclo.contrato_id,
            "comprovantes_ids": list(
                Comprovante.objects.filter(ciclo=ciclo, deleted_at__isnull=True).values_list("id", flat=True)
            ),
        }

        with transaction.atomic():
            criados: list[Comprovante] = []
            for arquivo in arquivos:
                criado = Comprovante.objects.create(
                    contrato=ciclo.contrato,
                    ciclo=ciclo,
                    tipo=payload.get("tipo") or Comprovante.Tipo.OUTRO,
                    papel=payload.get("papel") or Comprovante.Papel.OPERACIONAL,
                    arquivo=arquivo,
                    mime=getattr(arquivo, "content_type", "") or "",
                    size_bytes=getattr(arquivo, "size", None),
                    data_pagamento=(
                        parse_datetime(str(payload.get("data_pagamento")))
                        if payload.get("data_pagamento")
                        else None
                    ),
                    origem=payload.get("origem") or Comprovante.Origem.OUTRO,
                    agente_snapshot=getattr(ciclo.contrato.agente, "full_name", "") or "",
                    filial_snapshot="",
                    enviado_por=user,
                    status_validacao=(
                        payload.get("status_validacao")
                        or Comprovante.StatusValidacao.PENDENTE
                    ),
                )
                criados.append(criado)

            after = [_serialize_comprovante(item, request=request) for item in criados]
            AdminOverrideService._record_event(
                context=_OverrideContext(
                    associado=ciclo.contrato.associado,
                    contrato=ciclo.contrato,
                    ciclo=ciclo,
                    comprovante=criados[-1],
                ),
                user=user,
                escopo=AdminOverrideEvent.Scope.COMPROVANTE,
                resumo=(
                    f"Inclusão de {len(criados)} comprovante(s) no ciclo {ciclo.numero}"
                ),
                motivo=motivo,
                before_snapshot=before,
                after_snapshot={"created": after},
                changes=[
                    {
                        "entity_type": AdminOverrideChange.EntityType.COMPROVANTE,
                        "entity_id": item.id,
                        "resumo": "Comprovante incluído pelo admin no ciclo",
                        "before_snapshot": {},
                        "after_snapshot": serialized,
                    }
                    for item, serialized in zip(criados, after, strict=False)
                ],
            )
            return criados

    @staticmethod
    def apply_cycle_layout_override(
        *,
        contrato: Contrato,
        payload: dict[str, Any],
        user,
    ) -> Contrato:
        _assert_version(contrato, payload.get("updated_at"))
        motivo = str(payload.get("motivo") or "").strip()
        if not motivo:
            raise ValidationError("O motivo da alteração é obrigatório.")

        before_snapshot = AdminOverrideService.build_contract_projection_for_response(
            contrato,
            include_documents=True,
        )

        current_cycles = {
            ciclo.id: ciclo
            for ciclo in contrato.ciclos.filter(deleted_at__isnull=True)
        }
        current_parcelas = {
            parcela.id: parcela
            for parcela in Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            ).exclude(status=Parcela.Status.CANCELADO)
        }
        old_reference_by_parcela_id = {
            parcela.id: parcela.referencia_mes
            for parcela in current_parcelas.values()
        }

        cycles_payload = payload.get("cycles") or []
        parcel_items = payload.get("parcelas") or []
        if not cycles_payload:
            raise ValidationError("Informe ao menos um ciclo no layout.")

        cycle_ref_map: dict[str, Ciclo] = {}
        touched_cycle_ids: set[int] = set()
        touched_parcela_ids: set[int] = set()

        with transaction.atomic():
            existing_cycle_list = list(current_cycles.values())
            for index, ciclo in enumerate(existing_cycle_list, start=1):
                temporary_number = 1000 + index
                if ciclo.numero != temporary_number:
                    ciclo.numero = temporary_number
                    ciclo.save(update_fields=["numero", "updated_at"])

            existing_parcela_list = list(current_parcelas.values())
            for index, parcela in enumerate(existing_parcela_list, start=1):
                temporary_number = 1000 + index
                if parcela.numero != temporary_number:
                    parcela.numero = temporary_number
                    parcela.save(update_fields=["numero", "updated_at"])

            for raw_cycle in cycles_payload:
                cycle_id = raw_cycle.get("id")
                cycle = current_cycles.get(cycle_id) if cycle_id else None
                if cycle is None:
                    cycle = Ciclo.objects.create(
                        contrato=contrato,
                        numero=int(raw_cycle.get("numero") or 1),
                        data_inicio=_parse_optional_date(raw_cycle.get("data_inicio")) or timezone.localdate(),
                        data_fim=_parse_optional_date(raw_cycle.get("data_fim")) or timezone.localdate(),
                        status=str(raw_cycle.get("status") or Ciclo.Status.ABERTO),
                        valor_total=_parse_decimal(raw_cycle.get("valor_total")),
                    )
                else:
                    cycle.numero = int(raw_cycle.get("numero") or cycle.numero)
                    cycle.data_inicio = _parse_optional_date(raw_cycle.get("data_inicio")) or cycle.data_inicio
                    cycle.data_fim = _parse_optional_date(raw_cycle.get("data_fim")) or cycle.data_fim
                    cycle.status = str(raw_cycle.get("status") or cycle.status)
                    cycle.valor_total = _parse_decimal(
                        raw_cycle.get("valor_total"),
                        cycle.valor_total,
                    )
                    cycle.save()
                touched_cycle_ids.add(cycle.id)
                cycle_ref_map[str(cycle.id)] = cycle
                if raw_cycle.get("client_key"):
                    cycle_ref_map[str(raw_cycle["client_key"])] = cycle

            for raw_parcela in parcel_items:
                parcela_id = raw_parcela.get("id")
                parcela = current_parcelas.get(parcela_id) if parcela_id else None
                cycle_ref = raw_parcela.get("cycle_ref") or raw_parcela.get("cycle_id")
                cycle = cycle_ref_map.get(str(cycle_ref))
                if cycle is None:
                    raise ValidationError("Parcela sem ciclo de destino válido.")
                if parcela is None:
                    parcela = Parcela.all_objects.create(
                        ciclo=cycle,
                        associado=contrato.associado,
                        numero=int(raw_parcela.get("numero") or 1),
                        referencia_mes=_parse_optional_date(raw_parcela.get("referencia_mes")) or cycle.data_inicio,
                        valor=_parse_decimal(raw_parcela.get("valor")),
                        data_vencimento=_parse_optional_date(raw_parcela.get("data_vencimento")) or cycle.data_inicio,
                        status=str(raw_parcela.get("status") or Parcela.Status.EM_PREVISAO),
                        data_pagamento=_parse_optional_date(raw_parcela.get("data_pagamento")),
                        observacao=str(raw_parcela.get("observacao") or ""),
                        layout_bucket=str(raw_parcela.get("layout_bucket") or Parcela.LayoutBucket.CYCLE),
                    )
                else:
                    parcela.ciclo = cycle
                    parcela.associado = contrato.associado
                    parcela.numero = int(raw_parcela.get("numero") or parcela.numero)
                    parcela.referencia_mes = _parse_optional_date(raw_parcela.get("referencia_mes")) or parcela.referencia_mes
                    parcela.valor = _parse_decimal(raw_parcela.get("valor"), parcela.valor)
                    parcela.data_vencimento = _parse_optional_date(raw_parcela.get("data_vencimento")) or parcela.data_vencimento
                    parcela.status = str(raw_parcela.get("status") or parcela.status)
                    parcela.data_pagamento = _parse_optional_date(raw_parcela.get("data_pagamento"))
                    parcela.observacao = str(raw_parcela.get("observacao") or "")
                    parcela.layout_bucket = str(raw_parcela.get("layout_bucket") or Parcela.LayoutBucket.CYCLE)
                    parcela.save()
                touched_parcela_ids.add(parcela.id)

            for parcela in current_parcelas.values():
                if parcela.id not in touched_parcela_ids:
                    parcela.soft_delete()

            for ciclo in current_cycles.values():
                if ciclo.id not in touched_cycle_ids:
                    for parcela in Parcela.all_objects.filter(ciclo=ciclo, deleted_at__isnull=True):
                        if parcela.id not in touched_parcela_ids:
                            parcela.soft_delete()
                    ciclo.soft_delete()

            contrato.admin_manual_layout_enabled = True
            contrato.admin_manual_layout_updated_at = timezone.now()
            contrato.save(update_fields=["admin_manual_layout_enabled", "admin_manual_layout_updated_at", "updated_at"])

            new_parcela_by_reference = {
                parcela.referencia_mes: parcela
                for parcela in Parcela.all_objects.filter(
                    ciclo__contrato=contrato,
                    deleted_at__isnull=True,
                ).exclude(status=Parcela.Status.CANCELADO)
            }
            rebind_financial_links_by_reference(
                old_reference_by_parcela_id=old_reference_by_parcela_id,
                new_parcela_by_reference=new_parcela_by_reference,
            )

        after_snapshot = AdminOverrideService.build_contract_projection_for_response(
            contrato,
            include_documents=True,
        )
        changes = []
        for cycle in contrato.ciclos.filter(deleted_at__isnull=True).order_by("numero", "id"):
            changes.append(
                {
                    "entity_type": AdminOverrideChange.EntityType.CICLO,
                    "entity_id": cycle.id,
                    "resumo": f"Layout do ciclo {cycle.numero} ajustado",
                    "before_snapshot": {},
                    "after_snapshot": _serialize_ciclo(cycle),
                }
            )
        for parcela in (
            Parcela.all_objects.filter(ciclo__contrato=contrato, deleted_at__isnull=True)
            .exclude(status=Parcela.Status.CANCELADO)
            .order_by("ciclo__numero", "numero", "id")
        ):
            changes.append(
                {
                    "entity_type": AdminOverrideChange.EntityType.PARCELA,
                    "entity_id": parcela.id,
                    "competencia_referencia": parcela.referencia_mes,
                    "resumo": f"Competência {parcela.referencia_mes.strftime('%m/%Y')} movida/atualizada",
                    "before_snapshot": {},
                    "after_snapshot": _serialize_parcela(parcela),
                }
            )
        AdminOverrideService._record_event(
            context=_OverrideContext(associado=contrato.associado, contrato=contrato),
            user=user,
            escopo=AdminOverrideEvent.Scope.CICLOS,
            resumo=f"Layout manual dos ciclos do contrato {contrato.codigo}",
            motivo=motivo,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            changes=changes,
        )
        return contrato

    @staticmethod
    def revert_event(
        *,
        event: AdminOverrideEvent,
        motivo: str,
        user,
    ) -> AdminOverrideEvent:
        if event.revertida_em is not None:
            raise ValidationError("Esta operação já foi revertida.")
        if not motivo.strip():
            raise ValidationError("O motivo da reversão é obrigatório.")

        with transaction.atomic():
            if event.escopo == AdminOverrideEvent.Scope.ASSOCIADO:
                associado = event.associado
                snapshot = event.before_snapshot.get("associado") or {}
                contract_snapshot = event.before_snapshot.get("contrato") or {}
                if snapshot:
                    associado.nome_completo = snapshot.get("nome_completo") or associado.nome_completo
                    associado.rg = snapshot.get("rg") or ""
                    associado.orgao_expedidor = snapshot.get("orgao_expedidor") or ""
                    associado.email = snapshot.get("email") or ""
                    associado.telefone = snapshot.get("telefone") or ""
                    associado.data_nascimento = _parse_optional_date(snapshot.get("data_nascimento"))
                    associado.profissao = snapshot.get("profissao") or ""
                    associado.estado_civil = snapshot.get("estado_civil") or ""
                    associado.orgao_publico = snapshot.get("orgao_publico") or ""
                    associado.matricula_orgao = snapshot.get("matricula_orgao") or ""
                    associado.cargo = snapshot.get("cargo") or ""
                    associado.status = snapshot.get("status") or associado.status
                    associado.observacao = snapshot.get("observacao") or ""
                    associado.agente_responsavel_id = snapshot.get("agente_responsavel_id")
                    if snapshot.get("percentual_repasse") not in (None, ""):
                        associado.auxilio_taxa = _parse_decimal(snapshot.get("percentual_repasse"))

                    endereco = snapshot.get("endereco") or {}
                    associado.cep = str(endereco.get("cep") or "")
                    associado.logradouro = str(endereco.get("endereco") or "")
                    associado.numero = str(endereco.get("numero") or "")
                    associado.complemento = str(endereco.get("complemento") or "")
                    associado.bairro = str(endereco.get("bairro") or "")
                    associado.cidade = str(endereco.get("cidade") or "")
                    associado.uf = str(endereco.get("uf") or "")

                    dados_bancarios = snapshot.get("dados_bancarios") or {}
                    associado.banco = str(dados_bancarios.get("banco") or "")
                    associado.agencia = str(dados_bancarios.get("agencia") or "")
                    associado.conta = str(dados_bancarios.get("conta") or "")
                    associado.tipo_conta = str(dados_bancarios.get("tipo_conta") or "")
                    associado.chave_pix = str(dados_bancarios.get("chave_pix") or "")

                    contato = snapshot.get("contato") or {}
                    associado.telefone = str(contato.get("celular") or associado.telefone)
                    associado.email = str(contato.get("email") or associado.email)
                    associado.orgao_publico = str(contato.get("orgao_publico") or associado.orgao_publico)
                    associado.situacao_servidor = str(contato.get("situacao_servidor") or "")
                    associado.matricula_orgao = str(contato.get("matricula_servidor") or associado.matricula_orgao)
                    associado.save()

                if event.contrato_id and contract_snapshot:
                    contrato = event.contrato
                    contrato.codigo = contract_snapshot.get("codigo") or contrato.codigo
                    contrato.status = contract_snapshot.get("status") or contrato.status
                    contrato.valor_bruto = _parse_decimal(contract_snapshot.get("valor_bruto"), contrato.valor_bruto)
                    contrato.valor_liquido = _parse_decimal(contract_snapshot.get("valor_liquido"), contrato.valor_liquido)
                    contrato.valor_mensalidade = _parse_decimal(
                        contract_snapshot.get("valor_mensalidade"),
                        contrato.valor_mensalidade,
                    )
                    contrato.prazo_meses = int(contract_snapshot.get("prazo_meses") or contrato.prazo_meses)
                    contrato.taxa_antecipacao = _parse_decimal(contract_snapshot.get("taxa_antecipacao"), contrato.taxa_antecipacao)
                    contrato.margem_disponivel = _parse_decimal(contract_snapshot.get("margem_disponivel"), contrato.margem_disponivel)
                    contrato.valor_total_antecipacao = _parse_decimal(
                        contract_snapshot.get("valor_total_antecipacao"),
                        contrato.valor_total_antecipacao,
                    )
                    contrato.doacao_associado = _parse_decimal(contract_snapshot.get("doacao_associado"), contrato.doacao_associado)
                    contrato.comissao_agente = _parse_decimal(contract_snapshot.get("comissao_agente"), contrato.comissao_agente)
                    contrato.data_contrato = _parse_optional_date(contract_snapshot.get("data_contrato")) or contrato.data_contrato
                    contrato.data_aprovacao = _parse_optional_date(contract_snapshot.get("data_aprovacao"))
                    contrato.data_primeira_mensalidade = _parse_optional_date(contract_snapshot.get("data_primeira_mensalidade"))
                    contrato.mes_averbacao = _parse_optional_date(contract_snapshot.get("mes_averbacao"))
                    contrato.auxilio_liberado_em = _parse_optional_date(contract_snapshot.get("auxilio_liberado_em"))
                    contrato.agente_id = contract_snapshot.get("agente_id")
                    contrato.admin_manual_layout_enabled = bool(contract_snapshot.get("admin_manual_layout_enabled"))
                    contrato.save()
            elif event.escopo == AdminOverrideEvent.Scope.CONTRATO and event.contrato_id:
                snapshot = event.before_snapshot or {}
                contrato = event.contrato
                contrato.status = snapshot.get("status") or contrato.status
                contrato.valor_bruto = _parse_decimal(snapshot.get("valor_bruto"), contrato.valor_bruto)
                contrato.valor_liquido = _parse_decimal(snapshot.get("valor_liquido"), contrato.valor_liquido)
                contrato.valor_mensalidade = _parse_decimal(snapshot.get("valor_mensalidade"), contrato.valor_mensalidade)
                contrato.taxa_antecipacao = _parse_decimal(snapshot.get("taxa_antecipacao"), contrato.taxa_antecipacao)
                contrato.margem_disponivel = _parse_decimal(snapshot.get("margem_disponivel"), contrato.margem_disponivel)
                contrato.valor_total_antecipacao = _parse_decimal(snapshot.get("valor_total_antecipacao"), contrato.valor_total_antecipacao)
                contrato.doacao_associado = _parse_decimal(snapshot.get("doacao_associado"), contrato.doacao_associado)
                contrato.comissao_agente = _parse_decimal(snapshot.get("comissao_agente"), contrato.comissao_agente)
                contrato.agente_id = snapshot.get("agente_id")
                contrato.contato_web = bool(snapshot.get("contato_web"))
                contrato.termos_web = bool(snapshot.get("termos_web"))
                contrato.data_contrato = _parse_optional_date(snapshot.get("data_contrato")) or contrato.data_contrato
                contrato.data_aprovacao = _parse_optional_date(snapshot.get("data_aprovacao"))
                contrato.data_primeira_mensalidade = _parse_optional_date(snapshot.get("data_primeira_mensalidade"))
                contrato.mes_averbacao = _parse_optional_date(snapshot.get("mes_averbacao"))
                contrato.auxilio_liberado_em = _parse_optional_date(snapshot.get("auxilio_liberado_em"))
                contrato.admin_manual_layout_enabled = bool(snapshot.get("admin_manual_layout_enabled"))
                contrato.save()
            elif event.escopo == AdminOverrideEvent.Scope.CICLOS and event.contrato_id:
                cycles = event.before_snapshot.get("cycles") or []
                unpaid = event.before_snapshot.get("unpaid_months") or []
                movements = event.before_snapshot.get("movimentos_financeiros_avulsos") or []
                parcel_items: list[dict[str, Any]] = []
                for cycle in cycles:
                    cycle_ref = cycle.get("id")
                    for parcela in cycle.get("parcelas", []):
                        parcel_items.append(
                            {
                                **parcela,
                                "cycle_ref": cycle_ref,
                                "layout_bucket": Parcela.LayoutBucket.CYCLE,
                            }
                        )
                fallback_cycle_ref = str(cycles[0]["id"]) if cycles else ""
                for row in unpaid:
                    parcel_items.append(
                        {
                            **row,
                            "cycle_ref": fallback_cycle_ref,
                            "numero": 1,
                            "data_vencimento": row["referencia_mes"],
                            "layout_bucket": Parcela.LayoutBucket.UNPAID,
                        }
                    )
                for row in movements:
                    parcel_items.append(
                        {
                            **row,
                            "cycle_ref": fallback_cycle_ref,
                            "numero": 1,
                            "data_vencimento": row["referencia_mes"],
                            "layout_bucket": Parcela.LayoutBucket.MOVEMENT,
                        }
                    )
                AdminOverrideService.apply_cycle_layout_override(
                    contrato=event.contrato,
                    payload={
                        "updated_at": event.contrato.updated_at.isoformat() if event.contrato.updated_at else None,
                        "motivo": f"Reversão da operação #{event.id}",
                        "cycles": cycles,
                        "parcelas": parcel_items,
                    },
                    user=user,
                )
            elif event.escopo == AdminOverrideEvent.Scope.REFINANCIAMENTO and event.refinanciamento_id:
                refinanciamento = event.refinanciamento
                snapshot = event.before_snapshot or {}
                refinanciamento.status = snapshot.get("status") or refinanciamento.status
                refinanciamento.competencia_solicitada = (
                    _parse_optional_date(snapshot.get("competencia_solicitada"))
                    or refinanciamento.competencia_solicitada
                )
                refinanciamento.valor_refinanciamento = _parse_decimal(
                    snapshot.get("valor_refinanciamento"),
                    refinanciamento.valor_refinanciamento,
                )
                refinanciamento.repasse_agente = _parse_decimal(
                    snapshot.get("repasse_agente"),
                    refinanciamento.repasse_agente,
                )
                refinanciamento.executado_em = parse_datetime(str(snapshot.get("executado_em"))) if snapshot.get("executado_em") else None
                refinanciamento.data_ativacao_ciclo = parse_datetime(str(snapshot.get("data_ativacao_ciclo"))) if snapshot.get("data_ativacao_ciclo") else None
                refinanciamento.motivo_bloqueio = snapshot.get("motivo_bloqueio") or ""
                refinanciamento.observacao = snapshot.get("observacao") or ""
                refinanciamento.analista_note = snapshot.get("analista_note") or ""
                refinanciamento.coordenador_note = snapshot.get("coordenador_note") or ""
                refinanciamento.reviewed_by_id = snapshot.get("reviewed_by_id")
                refinanciamento.save()
            elif event.escopo == AdminOverrideEvent.Scope.ESTEIRA:
                esteira = getattr(event.associado, "esteira_item", None)
                snapshot = event.before_snapshot or {}
                if esteira is not None:
                    esteira.etapa_atual = snapshot.get("etapa_atual") or esteira.etapa_atual
                    esteira.status = snapshot.get("status") or esteira.status
                    esteira.prioridade = int(snapshot.get("prioridade") or esteira.prioridade)
                    esteira.observacao = snapshot.get("observacao") or ""
                    esteira.analista_responsavel_id = snapshot.get("analista_responsavel_id")
                    esteira.coordenador_responsavel_id = snapshot.get("coordenador_responsavel_id")
                    esteira.tesoureiro_responsavel_id = snapshot.get("tesoureiro_responsavel_id")
                    esteira.save()
            elif event.escopo == AdminOverrideEvent.Scope.DOCUMENTO:
                if event.before_snapshot.get("id"):
                    documento = Documento.all_objects.filter(pk=event.before_snapshot["id"]).first()
                    if documento is not None:
                        documento.deleted_at = None
                        documento.save(update_fields=["deleted_at", "updated_at"])
                if event.after_snapshot.get("id"):
                    current = Documento.objects.filter(pk=event.after_snapshot["id"]).first()
                    if current is not None:
                        current.soft_delete()
            elif event.escopo == AdminOverrideEvent.Scope.COMPROVANTE:
                if event.before_snapshot.get("id"):
                    comprovante = Comprovante.all_objects.filter(pk=event.before_snapshot["id"]).first()
                    if comprovante is not None:
                        comprovante.deleted_at = None
                        comprovante.save(update_fields=["deleted_at", "updated_at"])
                if event.after_snapshot.get("id"):
                    current = Comprovante.objects.filter(pk=event.after_snapshot["id"]).first()
                    if current is not None:
                        current.soft_delete()

            event.revertida_em = timezone.now()
            event.revertida_por = user
            event.motivo_reversao = motivo
            event.save(update_fields=["revertida_em", "revertida_por", "motivo_reversao", "updated_at"])
            return event
