from django.db import transaction
from typing import Optional
from ..models import Cadastro, CadastroStatus, EventLog
from infrastructure.cache.redis_client import publish

CHANNEL_ALL = "events:all"


class CadastroService:
    @staticmethod
    @transaction.atomic
    def submit(cadastro: Cadastro, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.ENVIADO_ANALISE
        cadastro.save(update_fields=["status", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="submitted",
            payload={"status": cadastro.status},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:submitted")
        return cadastro

    @staticmethod
    @transaction.atomic
    def aprovar(cadastro: Cadastro, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.APROVADO_ANALISE
        cadastro.save(update_fields=["status", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="approved",
            payload={"status": cadastro.status},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:approved")
        return cadastro

    @staticmethod
    @transaction.atomic
    def pendenciar(cadastro: Cadastro, motivo: str, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.PENDENTE_CORRECAO
        cadastro.observacao = motivo
        cadastro.save(update_fields=["status", "observacao", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="needs_changes",
            payload={"motivo": motivo},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:needs_changes")
        return cadastro

    @staticmethod
    @transaction.atomic
    def cancelar(cadastro: Cadastro, motivo: str, actor_id: Optional[str] = None) -> Cadastro:
        cadastro.status = CadastroStatus.CANCELADO
        cadastro.observacao = motivo
        cadastro.save(update_fields=["status", "observacao", "atualizado_em"])
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="canceled",
            payload={"motivo": motivo},
            actor_id=actor_id,
        )
        publish(CHANNEL_ALL, f"cadastro:{cadastro.id}:canceled")
        return cadastro
