from __future__ import annotations

from django.db import transaction
from django.db.models import Exists, OuterRef, Q

from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.importacao.models import ArquivoRetornoItem

from .small_value_return_materialization import (
    SMALL_VALUE_RETURN_AMOUNTS,
    resolve_default_small_value_agent,
)


def build_small_value_associados_without_agent_queryset():
    small_return_items = ArquivoRetornoItem.objects.filter(
        deleted_at__isnull=True,
        cpf_cnpj=OuterRef("cpf_cnpj"),
        valor_descontado__in=SMALL_VALUE_RETURN_AMOUNTS,
    )
    small_contracts = Contrato.all_objects.filter(
        associado=OuterRef("pk"),
        deleted_at__isnull=True,
        valor_mensalidade__in=SMALL_VALUE_RETURN_AMOUNTS,
    )
    return (
        Associado.objects.filter(agente_responsavel__isnull=True, deleted_at__isnull=True)
        .annotate(
            has_small_return=Exists(small_return_items),
            has_small_contract=Exists(small_contracts),
        )
        .filter(Q(has_small_return=True) | Q(has_small_contract=True))
        .order_by("nome_completo", "id")
    )


def assign_default_agent_to_small_value_associados(*, apply: bool) -> dict[str, object]:
    default_agent = resolve_default_small_value_agent()
    queryset = build_small_value_associados_without_agent_queryset()
    associados = list(queryset)
    summary = {
        "mode": "apply" if apply else "dry-run",
        "default_agent_id": getattr(default_agent, "id", None),
        "default_agent_email": getattr(default_agent, "email", None),
        "associado_total": len(associados),
        "associado_ids": [associado.id for associado in associados],
        "cpfs": [associado.cpf_cnpj for associado in associados],
    }

    if not apply or not associados or default_agent is None:
        return summary

    with transaction.atomic():
        Associado.objects.filter(id__in=summary["associado_ids"]).update(
            agente_responsavel=default_agent,
        )
    return summary
