"""
Service de Tesouraria

Gerencia o pipeline de 6 etapas da tesouraria:
1. Aguardando Pagamento
2. Pagamento Recebido
3. Comprovantes Anexados
4. Enviado para NuVideo
5. Contrato Gerado
6. Concluído
"""
from django.db import transaction
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
from ..models import Cadastro, CadastroStatus, EventLog
from infrastructure.cache.redis_client import publish

CHANNEL_ALL = "events:all"


class TesourariaService:
    """Service para gerenciar operações da tesouraria"""

    @staticmethod
    @transaction.atomic
    def registrar_pagamento(
        cadastro: Cadastro,
        valor: Decimal,
        forma_pagamento: str,
        data_pagamento: datetime,
        referencia: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Registra o recebimento do pagamento

        Args:
            cadastro: Instância do cadastro
            valor: Valor recebido
            forma_pagamento: PIX, Boleto, Cartão, etc
            data_pagamento: Data do pagamento
            referencia: Referência/ID da transação
            actor_id: ID do usuário que registrou

        Returns:
            Cadastro atualizado
        """
        # Validar que está no status correto
        if cadastro.status != CadastroStatus.APROVADO_ANALISE:
            raise ValueError(
                f"Cadastro deve estar em APROVADO_ANALISE. Status atual: {cadastro.status}"
            )

        # Atualizar status
        cadastro.status = CadastroStatus.AGUARDANDO_PAGAMENTO
        cadastro.save(update_fields=["status", "atualizado_em"])

        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="PAGAMENTO_RECEBIDO",
            payload={
                "valor": str(valor),
                "forma_pagamento": forma_pagamento,
                "data_pagamento": data_pagamento.isoformat(),
                "referencia": referencia,
            },
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "PAGAMENTO_RECEBIDO",
            "cadastro_id": cadastro.id,
            "valor": str(valor),
            "forma_pagamento": forma_pagamento,
        })

        return cadastro

    @staticmethod
    @transaction.atomic
    def confirmar_comprovantes(
        cadastro: Cadastro,
        comprovantes_urls: list[str],
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Confirma que comprovantes foram anexados

        Args:
            cadastro: Instância do cadastro
            comprovantes_urls: URLs dos comprovantes anexados
            actor_id: ID do usuário que confirmou

        Returns:
            Cadastro atualizado
        """
        # Atualizar status
        cadastro.status = CadastroStatus.AGUARDANDO_PAGAMENTO  # Mantém no mesmo status mas registra comprovantes
        cadastro.save(update_fields=["atualizado_em"])

        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="COMPROVANTES_ANEXADOS",
            payload={"comprovantes": comprovantes_urls},
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "COMPROVANTES_ANEXADOS",
            "cadastro_id": cadastro.id,
            "count": len(comprovantes_urls),
        })

        return cadastro

    @staticmethod
    @transaction.atomic
    def enviar_para_nuvideo(
        cadastro: Cadastro,
        documento_id: str,
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Marca que cadastro foi enviado para NuVideo

        Args:
            cadastro: Instância do cadastro
            documento_id: ID do documento no NuVideo
            actor_id: ID do usuário que enviou

        Returns:
            Cadastro atualizado
        """
        # Atualizar status
        cadastro.status = CadastroStatus.AGUARDANDO_PAGAMENTO  # Ainda aguardando mas enviado para assinatura
        cadastro.save(update_fields=["atualizado_em"])

        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="ENVIADO_NUVIDEO",
            payload={"documento_id": documento_id},
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "ENVIADO_NUVIDEO",
            "cadastro_id": cadastro.id,
            "documento_id": documento_id,
        })

        return cadastro

    @staticmethod
    @transaction.atomic
    def gerar_contrato(
        cadastro: Cadastro,
        contrato_url: str,
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Registra geração do contrato em PDF

        Args:
            cadastro: Instância do cadastro
            contrato_url: URL do contrato gerado
            actor_id: ID do usuário que gerou

        Returns:
            Cadastro atualizado
        """
        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="CONTRATO_GERADO",
            payload={"contrato_url": contrato_url},
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "CONTRATO_GERADO",
            "cadastro_id": cadastro.id,
            "contrato_url": contrato_url,
        })

        return cadastro

    @staticmethod
    @transaction.atomic
    def confirmar_assinatura(
        cadastro: Cadastro,
        assinatura_id: str,
        assinatura_data: datetime,
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Confirma que contrato foi assinado

        Args:
            cadastro: Instância do cadastro
            assinatura_id: ID da assinatura no NuVideo
            assinatura_data: Data da assinatura
            actor_id: ID do usuário que confirmou

        Returns:
            Cadastro atualizado
        """
        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="CONTRATO_ASSINADO",
            payload={
                "assinatura_id": assinatura_id,
                "assinatura_data": assinatura_data.isoformat(),
            },
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "CONTRATO_ASSINADO",
            "cadastro_id": cadastro.id,
            "assinatura_id": assinatura_id,
        })

        return cadastro

    @staticmethod
    @transaction.atomic
    def concluir_cadastro(
        cadastro: Cadastro,
        observacoes: Optional[str] = None,
        actor_id: Optional[str] = None
    ) -> Cadastro:
        """
        Finaliza o processo de cadastro

        Args:
            cadastro: Instância do cadastro
            observacoes: Observações finais
            actor_id: ID do usuário que concluiu

        Returns:
            Cadastro atualizado
        """
        # Validar que todas etapas foram cumpridas
        # (Simplificado - em produção, verificar eventos anteriores)

        # Atualizar status
        cadastro.status = CadastroStatus.CONCLUIDO
        if observacoes:
            cadastro.observacao = observacoes
        cadastro.save(update_fields=["status", "observacao", "atualizado_em"])

        # Registrar evento
        EventLog.objects.create(
            entity_type="Cadastro",
            entity_id=str(cadastro.id),
            event_type="CADASTRO_CONCLUIDO",
            payload={"observacoes": observacoes},
            actor_id=actor_id,
        )

        # Publicar evento SSE
        publish(CHANNEL_ALL, {
            "type": "CADASTRO_CONCLUIDO",
            "cadastro_id": cadastro.id,
        })

        return cadastro

    @staticmethod
    def obter_progresso(cadastro: Cadastro) -> Dict[str, Any]:
        """
        Retorna o progresso do cadastro no pipeline

        Args:
            cadastro: Instância do cadastro

        Returns:
            Dict com informações de progresso
        """
        # Buscar eventos do cadastro
        eventos = EventLog.objects.filter(
            entity_type="Cadastro",
            entity_id=str(cadastro.id)
        ).order_by("created_at")

        # Mapear etapas cumpridas
        etapas = {
            "pagamento_recebido": False,
            "comprovantes_anexados": False,
            "enviado_nuvideo": False,
            "contrato_gerado": False,
            "contrato_assinado": False,
            "concluido": False,
        }

        for evento in eventos:
            if evento.event_type == "PAGAMENTO_RECEBIDO":
                etapas["pagamento_recebido"] = True
            elif evento.event_type == "COMPROVANTES_ANEXADOS":
                etapas["comprovantes_anexados"] = True
            elif evento.event_type == "ENVIADO_NUVIDEO":
                etapas["enviado_nuvideo"] = True
            elif evento.event_type == "CONTRATO_GERADO":
                etapas["contrato_gerado"] = True
            elif evento.event_type == "CONTRATO_ASSINADO":
                etapas["contrato_assinado"] = True
            elif evento.event_type == "CADASTRO_CONCLUIDO":
                etapas["concluido"] = True

        # Calcular porcentagem de progresso
        etapas_concluidas = sum(1 for v in etapas.values() if v)
        progresso_percentual = (etapas_concluidas / len(etapas)) * 100

        return {
            "cadastro_id": cadastro.id,
            "status": cadastro.status,
            "etapas": etapas,
            "progresso_percentual": progresso_percentual,
            "etapas_concluidas": etapas_concluidas,
            "total_etapas": len(etapas),
        }
