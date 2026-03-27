from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import (
    AgenteMargemConfig,
    ConfiguracaoComissaoGlobal,
    ConfiguracaoComissaoHistorico,
    User,
)


class ComissaoService:
    @staticmethod
    def _active_global():
        now = timezone.now()
        return (
            ConfiguracaoComissaoGlobal.objects.filter(
                Q(vigente_ate__isnull=True) | Q(vigente_ate__gt=now)
            )
            .order_by("-vigente_desde", "-id")
            .first()
        )

    @staticmethod
    def _active_agent_config(agente_id: int | None):
        if not agente_id:
            return None
        now = timezone.now()
        return (
            AgenteMargemConfig.objects.filter(
                agente_id=agente_id,
                vigente_ate__isnull=True,
            )
            .order_by("-vigente_desde", "-id")
            .first()
        )

    @classmethod
    def resolve_percentual(cls, agente_id: int | None = None) -> Decimal:
        agent_config = cls._active_agent_config(agente_id)
        if agent_config is not None:
            return Decimal(str(agent_config.percentual))

        global_config = cls._active_global()
        if global_config is not None:
            return Decimal(str(global_config.percentual))

        return Decimal("10.00")

    @classmethod
    def build_settings_payload(cls) -> dict[str, object]:
        global_config = cls._active_global()
        agents = (
            User.objects.filter(
                is_active=True,
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo="AGENTE",
            )
            .distinct()
            .order_by("first_name", "last_name", "email")
        )
        rows: list[dict[str, object]] = []
        for agente in agents:
            override = cls._active_agent_config(agente.id)
            percentual_efetivo = cls.resolve_percentual(agente.id)
            rows.append(
                {
                    "agente_id": agente.id,
                    "agente_nome": agente.full_name,
                    "agente_email": agente.email,
                    "percentual_efetivo": percentual_efetivo,
                    "percentual_override": (
                        Decimal(str(override.percentual)) if override is not None else None
                    ),
                    "possui_override": override is not None,
                }
            )

        return {
            "global": {
                "percentual": (
                    Decimal(str(global_config.percentual))
                    if global_config is not None
                    else Decimal("10.00")
                ),
                "vigente_desde": getattr(global_config, "vigente_desde", None),
                "updated_by": getattr(global_config, "updated_by", None),
                "motivo": getattr(global_config, "motivo", ""),
            },
            "agentes": rows,
        }

    @classmethod
    @transaction.atomic
    def aplicar_percentual_global(
        cls,
        *,
        percentual: Decimal,
        motivo: str,
        user,
    ) -> dict[str, object]:
        now = timezone.now()
        atual = cls._active_global()
        percentual_anterior = Decimal(str(atual.percentual)) if atual is not None else Decimal("10.00")
        if atual is not None:
            atual.vigente_ate = now
            atual.save(update_fields=["vigente_ate", "updated_at"])

        novo = ConfiguracaoComissaoGlobal.objects.create(
            percentual=percentual,
            vigente_desde=now,
            updated_by=user,
            motivo=motivo,
        )
        ConfiguracaoComissaoHistorico.objects.create(
            escopo=ConfiguracaoComissaoHistorico.Escopo.GLOBAL,
            agente=None,
            percentual_anterior=percentual_anterior,
            percentual_novo=percentual,
            changed_by=user,
            motivo=motivo,
            meta={"aplicacao": "global"},
        )
        return cls.build_settings_payload() | {"global_obj": novo}

    @classmethod
    @transaction.atomic
    def aplicar_percentual_agentes(
        cls,
        *,
        agente_ids: list[int],
        percentual: Decimal,
        motivo: str,
        user,
    ) -> dict[str, object]:
        if not agente_ids:
            raise ValidationError({"agentes": "Selecione ao menos um agente."})

        agentes = list(
            User.objects.filter(
                id__in=agente_ids,
                is_active=True,
                user_roles__deleted_at__isnull=True,
                user_roles__role__codigo="AGENTE",
            )
            .distinct()
        )
        if len(agentes) != len(set(agente_ids)):
            raise ValidationError({"agentes": "Um ou mais agentes são inválidos."})

        now = timezone.now()
        for agente in agentes:
            atual = cls._active_agent_config(agente.id)
            percentual_anterior = (
                Decimal(str(atual.percentual))
                if atual is not None
                else cls.resolve_percentual(None)
            )
            if atual is not None:
                atual.vigente_ate = now
                atual.save(update_fields=["vigente_ate", "updated_at"])

            AgenteMargemConfig.objects.create(
                agente=agente,
                percentual=percentual,
                vigente_desde=now,
                updated_by=user,
                motivo=motivo,
            )
            ConfiguracaoComissaoHistorico.objects.create(
                escopo=ConfiguracaoComissaoHistorico.Escopo.AGENTE,
                agente=agente,
                percentual_anterior=percentual_anterior,
                percentual_novo=percentual,
                changed_by=user,
                motivo=motivo,
                meta={"aplicacao": "override"},
            )

        return cls.build_settings_payload()

    @classmethod
    @transaction.atomic
    def remover_override_agente(cls, *, agente_id: int, motivo: str, user) -> dict[str, object]:
        atual = cls._active_agent_config(agente_id)
        if atual is None:
            raise ValidationError("O agente informado não possui override ativo.")

        now = timezone.now()
        atual.vigente_ate = now
        atual.save(update_fields=["vigente_ate", "updated_at"])
        ConfiguracaoComissaoHistorico.objects.create(
            escopo=ConfiguracaoComissaoHistorico.Escopo.AGENTE,
            agente=atual.agente,
            percentual_anterior=Decimal(str(atual.percentual)),
            percentual_novo=cls.resolve_percentual(None),
            changed_by=user,
            motivo=motivo,
            meta={"aplicacao": "remocao_override"},
        )
        return cls.build_settings_payload()
