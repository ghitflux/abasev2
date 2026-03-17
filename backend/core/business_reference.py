from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Iterable

from django.db import models
from django.utils import timezone


BUSINESS_REFERENCE_FIELD_PRIORITY: dict[str, tuple[str, ...]] = {
    "accounts.role": ("created_at",),
    "accounts.user": ("created_at",),
    "accounts.userrole": ("assigned_at", "created_at"),
    "accounts.agentemargemconfig": ("vigente_desde", "created_at"),
    "accounts.agentemargemhistorico": ("created_at",),
    "accounts.agentemargemsnapshot": ("created_at",),
    "associados.associado": ("created_at",),
    "associados.endereco": ("created_at",),
    "associados.dadosbancarios": ("created_at",),
    "associados.contatohistorico": ("ultima_interacao_em", "created_at"),
    "associados.documento": ("created_at",),
    "contratos.contrato": ("data_aprovacao", "data_contrato", "created_at"),
    "contratos.ciclo": ("data_inicio", "created_at"),
    "contratos.parcela": ("data_pagamento", "referencia_mes", "data_vencimento", "created_at"),
    "esteira.esteiraitem": ("assumido_em", "concluido_em", "created_at"),
    "esteira.transicao": ("realizado_em", "created_at"),
    "esteira.pendencia": ("resolvida_em", "created_at"),
    "esteira.docissue": ("created_at",),
    "esteira.docreupload": ("uploaded_at", "created_at"),
    "financeiro.despesa": ("data_pagamento", "data_despesa", "created_at"),
    "importacao.pagamentomensalidade": ("manual_paid_at", "referencia_month", "created_at"),
    "importacao.arquivoretorno": ("processado_em", "competencia", "created_at"),
    "importacao.arquivoretornoitem": ("competencia", "created_at"),
    "importacao.importacaolog": ("created_at",),
    "refinanciamento.refinanciamento": ("executado_em", "competencia_solicitada", "ref1", "created_at"),
    "refinanciamento.comprovante": ("created_at",),
    "refinanciamento.assumption": ("finalizado_em", "assumido_em", "liberado_em", "solicitado_em", "created_at"),
    "refinanciamento.ajustevalor": ("created_at",),
    "refinanciamento.item": ("referencia_month", "created_at"),
    "relatorios.relatoriogerado": ("created_at",),
    "tesouraria.baixamanual": ("data_baixa", "created_at"),
    "tesouraria.confirmacao": ("data_confirmacao", "competencia", "created_at"),
    "tesouraria.pagamento": ("paid_at", "created_at"),
}


def _make_aware(value: datetime) -> datetime:
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _coerce_value(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _make_aware(value)
    if isinstance(value, date):
        naive = datetime.combine(value, time.min)
        return timezone.make_aware(naive, timezone.get_current_timezone())
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        for fmt in ("%m/%Y", "%Y-%m", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(stripped, fmt)
                if fmt == "%m/%Y":
                    parsed = parsed.replace(day=1)
                return timezone.make_aware(parsed, timezone.get_current_timezone())
            except ValueError:
                continue
    return None


def resolve_business_reference(instance: models.Model) -> datetime | None:
    label = instance._meta.label_lower
    for field_name in BUSINESS_REFERENCE_FIELD_PRIORITY.get(label, ("created_at",)):
        if not hasattr(instance, field_name):
            continue
        value = getattr(instance, field_name)
        resolved = _coerce_value(value)
        if resolved is not None:
            return resolved
    return _coerce_value(getattr(instance, "created_at", None))


def backfill_business_references(
    model_classes: Iterable[type[models.Model]],
) -> dict[str, int]:
    updated_by_model: dict[str, int] = {}

    for model_class in model_classes:
        updated = 0
        queryset = model_class.all_objects.all().iterator()
        for instance in queryset:
            computed = resolve_business_reference(instance)
            if computed == instance.data_referencia_negocio:
                continue
            model_class.all_objects.filter(pk=instance.pk).update(
                data_referencia_negocio=computed
            )
            updated += 1
        updated_by_model[model_class._meta.label_lower] = updated

    return updated_by_model
