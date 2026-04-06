from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.contratos.models import Parcela
from core.business_reference import resolve_business_reference

from .models import ArquivoRetorno
from .parsers import ETIPITxtRetornoParser
from .return_auto_enrollment import is_synthetic_return_contract_code
from .services import competencia_to_date


STATUS_DESCONTADO = {"1", "4"}
SMOKE_TEST_CPF = "05201186343"


class ParcelasRetornoCorrectionError(Exception):
    pass


@dataclass(slots=True)
class CorrectionSource:
    path: Path
    label: str
    arquivo_retorno_id: int | None


def parse_competencia_argument(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ParcelasRetornoCorrectionError("Competência inválida. Use YYYY-MM.") from exc


def _only_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _parse_data_geracao(value: str) -> date:
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError as exc:
        raise ParcelasRetornoCorrectionError(
            f"Data de geração inválida no arquivo retorno: {value!r}."
        ) from exc


def _resolve_storage_path(arquivo: ArquivoRetorno) -> Path:
    try:
        return Path(default_storage.path(arquivo.arquivo_url))
    except Exception as exc:
        raise ParcelasRetornoCorrectionError(
            f"Não foi possível resolver o arquivo do ArquivoRetorno #{arquivo.id}: {exc}"
        ) from exc


def resolve_correction_source(
    *,
    competencia: date,
    arquivo_retorno_id: int | None = None,
    arquivo_path: str | None = None,
) -> CorrectionSource:
    if arquivo_retorno_id:
        arquivo = ArquivoRetorno.objects.filter(pk=arquivo_retorno_id).first()
        if arquivo is None:
            raise ParcelasRetornoCorrectionError(
                f"ArquivoRetorno #{arquivo_retorno_id} não encontrado."
            )
        if arquivo.competencia != competencia:
            raise ParcelasRetornoCorrectionError(
                f"ArquivoRetorno #{arquivo.id} pertence à competência "
                f"{arquivo.competencia:%Y-%m}, diferente de {competencia:%Y-%m}."
            )
        return CorrectionSource(
            path=_resolve_storage_path(arquivo),
            label=f"ArquivoRetorno #{arquivo.id} - {arquivo.arquivo_nome}",
            arquivo_retorno_id=arquivo.id,
        )

    arquivo = (
        ArquivoRetorno.objects.filter(
            competencia=competencia,
            status=ArquivoRetorno.Status.CONCLUIDO,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if arquivo is not None:
        return CorrectionSource(
            path=_resolve_storage_path(arquivo),
            label=f"ArquivoRetorno #{arquivo.id} - {arquivo.arquivo_nome}",
            arquivo_retorno_id=arquivo.id,
        )

    if arquivo_path:
        path = Path(arquivo_path).expanduser().resolve()
        if not path.exists():
            raise ParcelasRetornoCorrectionError(f"Arquivo não encontrado: {path}")
        return CorrectionSource(path=path, label=str(path), arquivo_retorno_id=None)

    raise ParcelasRetornoCorrectionError(
        "Nenhum ArquivoRetorno concluído encontrado para a competência informada; "
        "use --arquivo-path."
    )


def _line_signature(item: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    keys = (
        "cpf_cnpj",
        "competencia",
        "status_codigo",
        "status_desconto",
        "status_descricao",
        "motivo_rejeicao",
    )
    return tuple((key, str(item.get(key, ""))) for key in keys)


def consolidate_items_by_cpf(
    items: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    unique_by_cpf: dict[str, dict[str, Any]] = {}
    duplicate_groups: list[dict[str, Any]] = []

    for item in items:
        cpf = _only_digits(str(item.get("cpf_cnpj", "")))
        if len(cpf) != 11:
            continue

        current = unique_by_cpf.get(cpf)
        if current is None:
            unique_by_cpf[cpf] = item
            continue

        current_signature = _line_signature(current)
        item_signature = _line_signature(item)
        if current_signature != item_signature:
            raise ParcelasRetornoCorrectionError(
                f"CPF duplicado com payload divergente no arquivo: {cpf} "
                f"(linhas {current.get('linha_numero')} e {item.get('linha_numero')})."
            )

        duplicate_group = next((row for row in duplicate_groups if row["cpf_cnpj"] == cpf), None)
        if duplicate_group is None:
            duplicate_group = {
                "cpf_cnpj": cpf,
                "linha_mantida": current.get("linha_numero"),
                "linhas_ignoradas": [],
                "status_codigo": current.get("status_codigo"),
                "valor_descontado": str(current.get("valor_descontado", "")),
            }
            duplicate_groups.append(duplicate_group)
        duplicate_group["linhas_ignoradas"].append(item.get("linha_numero"))

    return unique_by_cpf, duplicate_groups


def _replace_competencia_note(existing: str, *, competencia_display: str, new_note: str) -> str:
    prefixes = (
        f"Correcao retorno {competencia_display}",
        f"Revisao manual retorno {competencia_display}",
    )
    lines = [line.strip() for line in (existing or "").splitlines() if line.strip()]
    cleaned = [line for line in lines if not any(line.startswith(prefix) for prefix in prefixes)]
    if new_note not in cleaned:
        cleaned.append(new_note)
    return "\n".join(cleaned)


def _build_matched_note(
    *,
    competencia_display: str,
    source_label: str,
    status_codigo: str,
    status_descricao: str,
) -> str:
    return (
        f"Correcao retorno {competencia_display} via {source_label}: "
        f"ETIPI {status_codigo} - {status_descricao}."
    )


def _build_missing_note(*, competencia_display: str, source_label: str) -> str:
    return (
        f"Revisao manual retorno {competencia_display} via {source_label}: "
        "parcela sem correspondencia no arquivo."
    )


def _build_smoke_test(competencia: date) -> dict[str, Any]:
    parcelas = list(
        Parcela.all_objects.filter(
            associado__cpf_cnpj=SMOKE_TEST_CPF,
            referencia_mes=competencia,
            deleted_at__isnull=True,
        )
        .select_related("associado", "ciclo__contrato")
        .order_by("id")
    )
    return {
        "cpf_cnpj": SMOKE_TEST_CPF,
        "found": bool(parcelas),
        "parcelas": [
            {
                "id": parcela.id,
                "status": parcela.status,
                "data_pagamento": (
                    parcela.data_pagamento.isoformat() if parcela.data_pagamento else None
                ),
                "valor": str(parcela.valor),
                "contrato_id": parcela.ciclo.contrato_id,
                "observacao": parcela.observacao,
            }
            for parcela in parcelas
        ],
    }


def run_parcelas_retorno_correction(
    *,
    competencia: date,
    apply: bool,
    arquivo_retorno_id: int | None = None,
    arquivo_path: str | None = None,
) -> dict[str, Any]:
    source = resolve_correction_source(
        competencia=competencia,
        arquivo_retorno_id=arquivo_retorno_id,
        arquivo_path=arquivo_path,
    )
    parser = ETIPITxtRetornoParser()
    parsed = parser.parse(str(source.path))
    parsed_competencia = competencia_to_date(parsed.meta.competencia)
    if parsed_competencia != competencia:
        raise ParcelasRetornoCorrectionError(
            f"Arquivo {source.label} pertence à competência {parsed_competencia:%Y-%m}, "
            f"diferente de {competencia:%Y-%m}."
        )
    data_pagamento = _parse_data_geracao(parsed.meta.data_geracao)
    unique_by_cpf, duplicate_groups = consolidate_items_by_cpf(parsed.items)

    parcelas = list(
        Parcela.all_objects.filter(
            referencia_mes=competencia,
            deleted_at__isnull=True,
        )
        .exclude(status__in=[Parcela.Status.CANCELADO, Parcela.Status.LIQUIDADA])
        .select_related("associado", "ciclo__contrato")
        .order_by("id")
    )
    parcelas = [
        parcela
        for parcela in parcelas
        if not is_synthetic_return_contract_code(getattr(parcela.ciclo.contrato, "codigo", ""))
    ]

    parcelas_by_cpf: dict[str, list[Parcela]] = {}
    for parcela in parcelas:
        cpf = _only_digits(getattr(parcela.associado, "cpf_cnpj", ""))
        if len(cpf) != 11:
            continue
        parcelas_by_cpf.setdefault(cpf, []).append(parcela)

    competencia_display = parsed.meta.competencia
    target_descontado_count = 0
    target_descontado_valor = Decimal("0")
    target_nao_descontado_count = 0
    target_nao_descontado_valor = Decimal("0")
    parcelas_sem_match_count = 0
    parcelas_sem_match_valor = Decimal("0")
    cpfs_sem_parcela: list[dict[str, Any]] = []
    parcelas_sem_arquivo: list[dict[str, Any]] = []
    to_update: list[Parcela] = []
    now = timezone.now()

    for cpf, row in unique_by_cpf.items():
        current_parcelas = parcelas_by_cpf.get(cpf, [])
        if not current_parcelas:
            cpfs_sem_parcela.append(
                {
                    "cpf_cnpj": cpf,
                    "nome_servidor": row.get("nome_servidor", ""),
                    "status_codigo": row.get("status_codigo", ""),
                    "linha_numero": row.get("linha_numero"),
                }
            )
            continue

        status_codigo = str(row.get("status_codigo", "")).upper()
        status_descricao = str(row.get("status_descricao", "")).strip()
        novo_status = (
            Parcela.Status.DESCONTADO
            if status_codigo in STATUS_DESCONTADO
            else Parcela.Status.NAO_DESCONTADO
        )
        note = _build_matched_note(
            competencia_display=competencia_display,
            source_label=source.label,
            status_codigo=status_codigo,
            status_descricao=status_descricao,
        )
        for parcela in current_parcelas:
            if novo_status == Parcela.Status.DESCONTADO:
                target_descontado_count += 1
                target_descontado_valor += parcela.valor
            else:
                target_nao_descontado_count += 1
                target_nao_descontado_valor += parcela.valor

            if not apply:
                continue

            parcela.status = novo_status
            parcela.data_pagamento = (
                data_pagamento if novo_status == Parcela.Status.DESCONTADO else None
            )
            parcela.observacao = _replace_competencia_note(
                parcela.observacao,
                competencia_display=competencia_display,
                new_note=note,
            )
            parcela.updated_at = now
            parcela.data_referencia_negocio = resolve_business_reference(parcela)
            to_update.append(parcela)

    missing_note = _build_missing_note(
        competencia_display=competencia_display,
        source_label=source.label,
    )
    for cpf, current_parcelas in parcelas_by_cpf.items():
        if cpf in unique_by_cpf:
            continue
        for parcela in current_parcelas:
            parcelas_sem_match_count += 1
            parcelas_sem_match_valor += parcela.valor
            parcelas_sem_arquivo.append(
                {
                    "parcela_id": parcela.id,
                    "cpf_cnpj": cpf,
                    "status_atual": parcela.status,
                }
            )
            if not apply:
                continue
            parcela.observacao = _replace_competencia_note(
                parcela.observacao,
                competencia_display=competencia_display,
                new_note=missing_note,
            )
            parcela.updated_at = now
            parcela.data_referencia_negocio = resolve_business_reference(parcela)
            to_update.append(parcela)

    if apply and to_update:
        unique_updates = {parcela.id: parcela for parcela in to_update}
        with transaction.atomic():
            Parcela.all_objects.bulk_update(
                list(unique_updates.values()),
                ["status", "data_pagamento", "observacao", "updated_at", "data_referencia_negocio"],
            )

    return {
        "mode": "apply" if apply else "dry-run",
        "competencia": competencia.isoformat(),
        "competencia_display": competencia_display,
        "data_geracao": parsed.meta.data_geracao,
        "source": {
            "label": source.label,
            "path": str(source.path),
            "arquivo_retorno_id": source.arquivo_retorno_id,
        },
        "warnings_count": len(parsed.warnings),
        "warnings": parsed.warnings,
        "linhas_brutas_total": len(parsed.items),
        "cpfs_unicos_total": len(unique_by_cpf),
        "cpfs_duplicados_total": len(duplicate_groups),
        "cpfs_duplicados": duplicate_groups,
        "status_bruto_por_codigo": {
            code: sum(1 for item in parsed.items if item.get("status_codigo") == code)
            for code in sorted({str(item.get("status_codigo", "")) for item in parsed.items})
        },
        "parcelas_elegiveis_total": len(parcelas),
        "parcelas_descontado_total": target_descontado_count,
        "parcelas_descontado_valor": str(target_descontado_valor),
        "parcelas_nao_descontado_total": target_nao_descontado_count,
        "parcelas_nao_descontado_valor": str(target_nao_descontado_valor),
        "parcelas_sem_match_total": parcelas_sem_match_count,
        "parcelas_sem_match_valor": str(parcelas_sem_match_valor),
        "parcelas_sem_match": parcelas_sem_arquivo,
        "cpfs_sem_parcela_total": len(cpfs_sem_parcela),
        "cpfs_sem_parcela": cpfs_sem_parcela,
        "smoke_test": _build_smoke_test(competencia),
    }
