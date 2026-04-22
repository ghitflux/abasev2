from __future__ import annotations

from decimal import Decimal


def normalize_multi_value_list(
    value: object,
    *,
    request_values: list[object] | None = None,
) -> list[str]:
    raw_values: list[object] = []
    if request_values:
        raw_values.extend(request_values)
    if isinstance(value, list):
        raw_values.extend(value)
    elif value not in (None, ""):
        raw_values.append(value)

    normalized: list[str] = []
    for raw_value in raw_values:
        if raw_value in (None, ""):
            continue
        if isinstance(raw_value, str):
            chunks = [chunk.strip() for chunk in raw_value.split(",") if chunk.strip()]
        else:
            chunks = [str(raw_value).strip()]
        for chunk in chunks:
            if chunk and chunk not in normalized:
                normalized.append(chunk)
    return normalized


def faixa_mensalidade_bounds(value: object) -> tuple[Decimal | None, Decimal | None]:
    if not isinstance(value, str) or not value.strip():
        return None, None
    normalized = value.strip()
    if normalized == "ate_100":
        return None, Decimal("100.00")
    if normalized == "100_200":
        return Decimal("100.00"), Decimal("200.00")
    if normalized == "200_300":
        return Decimal("200.00"), Decimal("300.00")
    if normalized == "300_500":
        return Decimal("300.00"), Decimal("500.00")
    if normalized == "acima_500":
        return Decimal("500.00"), None
    return None, None


def mensalidade_in_selected_ranges(
    valor_mensalidade: Decimal,
    faixa_mensalidade: object,
    *,
    request_values: list[object] | None = None,
) -> bool:
    selected_ranges = normalize_multi_value_list(
        faixa_mensalidade,
        request_values=request_values,
    )
    if not selected_ranges:
        return True

    for selected_range in selected_ranges:
        min_value, max_value = faixa_mensalidade_bounds(selected_range)
        if min_value is not None and valor_mensalidade < min_value:
            continue
        if max_value is not None and valor_mensalidade >= max_value:
            continue
        return True
    return False


def parcelas_pagas_in_selected_ranges(
    parcelas_pagas: int,
    faixa_parcelas: object,
    *,
    request_values: list[object] | None = None,
) -> bool:
    selected_ranges = normalize_multi_value_list(
        faixa_parcelas,
        request_values=request_values,
    )
    if not selected_ranges:
        return True

    for selected_range in selected_ranges:
        if selected_range == "1_parcela_paga" and parcelas_pagas >= 1:
            return True
        if selected_range == "3_parcelas_pagas" and parcelas_pagas >= 3:
            return True
    return False
