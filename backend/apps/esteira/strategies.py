from __future__ import annotations

from abc import ABC, abstractmethod


class ApprovalStrategy(ABC):
    @abstractmethod
    def can_approve(self, user, esteira_item) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_next_etapa(self) -> str:
        raise NotImplementedError


class AnalistaApprovalStrategy(ApprovalStrategy):
    def can_approve(self, user, esteira_item):
        return bool(
            user.has_role("ADMIN")
            or (
                esteira_item.etapa_atual == "analise"
                and esteira_item.analista_responsavel_id == user.id
                and esteira_item.status == "em_andamento"
            )
        )

    def get_next_etapa(self):
        return "coordenacao"


class CoordenadorApprovalStrategy(ApprovalStrategy):
    def can_approve(self, user, esteira_item):
        return bool(
            user.has_role("ADMIN")
            or (
                esteira_item.etapa_atual == "coordenacao"
                and esteira_item.status == "em_andamento"
                and (
                    esteira_item.coordenador_responsavel_id in [None, user.id]
                    or user.has_role("COORDENADOR")
                )
            )
        )

    def get_next_etapa(self):
        return "tesouraria"
