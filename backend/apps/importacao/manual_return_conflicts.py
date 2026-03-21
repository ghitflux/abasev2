from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from .models import ArquivoRetornoItem, PagamentoMensalidade


def competencia_item_label(competencia: date) -> str:
    return competencia.strftime("%m/%Y")


def pagamento_has_manual_context(pagamento: PagamentoMensalidade) -> bool:
    return bool(
        (pagamento.status_code or "").strip().upper() == "M"
        or pagamento.manual_status
        or pagamento.manual_paid_at
        or pagamento.manual_forma_pagamento
        or (pagamento.manual_comprovante_path or "").strip()
        or pagamento.recebido_manual is not None
        or pagamento.esperado_manual is not None
        or pagamento.manual_by_id
    )


def should_skip_legacy_manual_snapshot(*, return_status_code: str | None) -> bool:
    return (return_status_code or "").strip() == "1"


def should_promote_manual_pagamento_to_return(
    pagamento: PagamentoMensalidade,
    *,
    return_status_code: str | None,
    return_valor: Decimal | None,
) -> bool:
    if (return_status_code or "").strip() != "1":
        return False
    if not pagamento_has_manual_context(pagamento):
        return False
    if pagamento.valor is None or return_valor is None:
        return False
    try:
        return Decimal(str(pagamento.valor)) == Decimal(str(return_valor))
    except (InvalidOperation, TypeError, ValueError):
        return False


def promote_pagamento_to_return(
    pagamento: PagamentoMensalidade,
    *,
    return_item: ArquivoRetornoItem | None = None,
    source_file_path: str,
    import_uuid: str,
) -> list[str]:
    updated_fields: list[str] = []
    return_status_code = (
        getattr(return_item, "status_codigo", None) if return_item is not None else "1"
    )
    normalized_status = (return_status_code or "1").strip()

    if pagamento.status_code != normalized_status:
        pagamento.status_code = normalized_status
        updated_fields.append("status_code")

    if pagamento.import_uuid != import_uuid:
        pagamento.import_uuid = import_uuid
        updated_fields.append("import_uuid")

    if pagamento.source_file_path != source_file_path:
        pagamento.source_file_path = source_file_path
        updated_fields.append("source_file_path")

    if pagamento.manual_status is not None:
        pagamento.manual_status = None
        updated_fields.append("manual_status")
    if pagamento.manual_paid_at is not None:
        pagamento.manual_paid_at = None
        updated_fields.append("manual_paid_at")
    if pagamento.manual_forma_pagamento:
        pagamento.manual_forma_pagamento = ""
        updated_fields.append("manual_forma_pagamento")
    if pagamento.manual_comprovante_path:
        pagamento.manual_comprovante_path = ""
        updated_fields.append("manual_comprovante_path")
    if pagamento.recebido_manual is not None:
        pagamento.recebido_manual = None
        updated_fields.append("recebido_manual")
    if pagamento.esperado_manual is not None:
        pagamento.esperado_manual = None
        updated_fields.append("esperado_manual")
    if pagamento.manual_by_id is not None:
        pagamento.manual_by = None
        updated_fields.append("manual_by")

    return updated_fields
