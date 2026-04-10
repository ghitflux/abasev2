from __future__ import annotations

from decimal import Decimal

from django.db.models import Q

from apps.associados.models import only_digits
from apps.importacao.models import ArquivoRetornoItem
from apps.importacao.small_value_return_materialization import (
    SMALL_VALUE_RETURN_AMOUNTS,
)

from .models import Ciclo, Contrato, Parcela


def _normalized_amount(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def is_dedicated_small_value_contract(contrato: Contrato) -> bool:
    cached = getattr(contrato, "_is_dedicated_small_value_contract", None)
    if cached is not None:
        return bool(cached)

    mensalidade = _normalized_amount(contrato.valor_mensalidade)
    if mensalidade not in SMALL_VALUE_RETURN_AMOUNTS:
        contrato._is_dedicated_small_value_contract = False
        return False

    if contrato.is_shadow_duplicate:
        contrato._is_dedicated_small_value_contract = False
        return False

    active_parcelas = Parcela.all_objects.filter(
        ciclo__contrato=contrato,
        deleted_at__isnull=True,
    ).exclude(status=Parcela.Status.CANCELADO)
    has_active = active_parcelas.exists()
    if has_active and active_parcelas.exclude(valor=mensalidade).exists():
        contrato._is_dedicated_small_value_contract = False
        return False

    result = bool(has_active or contrato.admin_manual_layout_enabled)
    contrato._is_dedicated_small_value_contract = result
    return result


def is_return_imported_small_value_contract(contrato: Contrato) -> bool:
    cached = getattr(contrato, "_is_return_imported_small_value_contract", None)
    if cached is not None:
        return bool(cached)

    if not is_dedicated_small_value_contract(contrato):
        contrato._is_return_imported_small_value_contract = False
        return False

    mensalidade = _normalized_amount(contrato.valor_mensalidade)
    cpf = only_digits(getattr(contrato.associado, "cpf_cnpj", "") or "")
    result = ArquivoRetornoItem.objects.filter(
        deleted_at__isnull=True,
        valor_descontado=mensalidade,
    ).filter(
        Q(parcela__ciclo__contrato=contrato)
        | Q(associado=contrato.associado)
        | Q(cpf_cnpj=cpf)
    ).exists()
    contrato._is_return_imported_small_value_contract = result
    return result


def blocked_small_value_cycle_status(*, has_unpaid_months: bool) -> str:
    return Ciclo.Status.PENDENCIA if has_unpaid_months else Ciclo.Status.ABERTO
