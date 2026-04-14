"""
Signals do app associados.

Responsabilidade principal: manter Contrato.status sincronizado com
Associado.status sempre que o status do associado é alterado.

Regra: Contrato sempre reflete o estado do associado.
  cadastrado / importado / pendente  →  rascunho
  em_analise                         →  em_analise
  ativo / inadimplente               →  ativo
  inativo                            →  cancelado
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.contratos.models import Contrato

from .models import Associado

# Mapeamento canônico: Associado.status → Contrato.status
ASSOCIADO_TO_CONTRATO_STATUS: dict[str, str] = {
    Associado.Status.CADASTRADO: Contrato.Status.RASCUNHO,
    Associado.Status.IMPORTADO: Contrato.Status.RASCUNHO,
    Associado.Status.PENDENTE: Contrato.Status.EM_ANALISE,
    Associado.Status.EM_ANALISE: Contrato.Status.EM_ANALISE,
    Associado.Status.ATIVO: Contrato.Status.ATIVO,
    Associado.Status.INADIMPLENTE: Contrato.Status.ATIVO,
    Associado.Status.INATIVO: Contrato.Status.CANCELADO,
}


@receiver(post_save, sender=Associado)
def sync_contrato_status_on_associado_change(
    sender, instance: Associado, created: bool, update_fields=None, **kwargs
):
    """
    Sempre que Associado.status mudar, propaga a mudança para o(s)
    contrato(s) ativo(s) do associado (deleted_at__isnull=True).

    Ignora contratos já com status 'encerrado' — esses têm ciclo de vida
    próprio e não devem ser sobrescritos pelo fluxo do associado.
    """
    # Só atua quando o campo 'status' está sendo salvo
    if update_fields is not None and "status" not in update_fields:
        return

    novo_status_contrato = ASSOCIADO_TO_CONTRATO_STATUS.get(instance.status)
    if novo_status_contrato is None:
        return

    (
        Contrato.objects.filter(
            associado_id=instance.pk,
            deleted_at__isnull=True,
        )
        .exclude(status=Contrato.Status.ENCERRADO)
        .update(status=novo_status_contrato)
    )
