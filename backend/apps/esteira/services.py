from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado, Documento
from apps.contratos.models import Contrato
from apps.refinanciamento.models import Refinanciamento

from .models import DocIssue, EsteiraItem, Pendencia, Transicao
from .strategies import AnalistaApprovalStrategy, CoordenadorApprovalStrategy


class EsteiraService:
    """State machine para o workflow de aprovação."""

    TRANSICOES_VALIDAS = {
        ("analise", "aguardando"): ["assumir"],
        ("analise", "em_andamento"): ["aprovar", "pendenciar", "solicitar_correcao"],
        ("coordenacao", "aguardando"): ["assumir"],
        ("coordenacao", "em_andamento"): ["aprovar", "pendenciar", "rejeitar"],
        ("tesouraria", "aguardando"): ["efetivar"],
    }

    @staticmethod
    def _validar_acao(esteira_item, acao: str):
        permitidas = EsteiraService.TRANSICOES_VALIDAS.get(
            (esteira_item.etapa_atual, esteira_item.status), []
        )
        if acao not in permitidas:
            raise ValidationError(
                f"A ação '{acao}' não é permitida em "
                f"{esteira_item.etapa_atual}:{esteira_item.status}."
            )

    @staticmethod
    def _registrar_transicao(
        esteira_item,
        user,
        acao: str,
        de_etapa: str,
        para_etapa: str,
        de_situacao: str,
        para_situacao: str,
        observacao: str = "",
    ):
        Transicao.objects.create(
            esteira_item=esteira_item,
            acao=acao,
            de_status=de_etapa,
            para_status=para_etapa,
            de_situacao=de_situacao,
            para_situacao=para_situacao,
            realizado_por=user,
            observacao=observacao,
        )

    @staticmethod
    def _destino_aprovacao_analise(esteira_item: EsteiraItem) -> str:
        possui_refinanciamento_pendente = Refinanciamento.objects.filter(
            associado_id=esteira_item.associado_id,
            status__in=[
                Refinanciamento.Status.PENDENTE_APTO,
                Refinanciamento.Status.SOLICITADO,
                Refinanciamento.Status.EM_ANALISE,
            ],
        ).exists()
        if possui_refinanciamento_pendente:
            return EsteiraItem.Etapa.COORDENACAO
        return EsteiraItem.Etapa.TESOURARIA

    @staticmethod
    @transaction.atomic
    def assumir(esteira_item, user):
        EsteiraService._validar_acao(esteira_item, "assumir")

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status

        if esteira_item.etapa_atual == EsteiraItem.Etapa.ANALISE:
            if (
                esteira_item.analista_responsavel_id
                and esteira_item.analista_responsavel_id != user.id
            ):
                raise ValidationError("Este item já foi assumido por outro analista.")
            esteira_item.analista_responsavel = user
        elif esteira_item.etapa_atual == EsteiraItem.Etapa.COORDENACAO:
            if (
                esteira_item.coordenador_responsavel_id
                and esteira_item.coordenador_responsavel_id != user.id
            ):
                raise ValidationError("Este item já foi assumido por outro coordenador.")
            esteira_item.coordenador_responsavel = user
        else:
            raise ValidationError("Somente análise e coordenação podem ser assumidas.")

        esteira_item.status = EsteiraItem.Situacao.EM_ANDAMENTO
        esteira_item.assumido_em = timezone.now()
        esteira_item.save()

        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "assumir",
            de_etapa,
            de_etapa,
            de_situacao,
            EsteiraItem.Situacao.EM_ANDAMENTO,
            "Item assumido para tratamento.",
        )
        return esteira_item

    @staticmethod
    @transaction.atomic
    def aprovar(esteira_item, user, observacao=""):
        if esteira_item.etapa_atual == EsteiraItem.Etapa.ANALISE:
            strategy = AnalistaApprovalStrategy()
        elif esteira_item.etapa_atual == EsteiraItem.Etapa.COORDENACAO:
            strategy = CoordenadorApprovalStrategy()
        elif esteira_item.etapa_atual == EsteiraItem.Etapa.TESOURARIA:
            strategy = None
        else:
            raise ValidationError("Etapa atual não pode ser aprovada.")

        acao = "aprovar" if esteira_item.etapa_atual != EsteiraItem.Etapa.TESOURARIA else "efetivar"
        EsteiraService._validar_acao(esteira_item, acao)

        if strategy and not strategy.can_approve(user, esteira_item):
            raise ValidationError("Usuário não pode aprovar este item da esteira.")

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status

        if esteira_item.etapa_atual == EsteiraItem.Etapa.ANALISE:
            Documento.objects.filter(associado=esteira_item.associado).exclude(
                status=Documento.Status.APROVADO
            ).update(status=Documento.Status.APROVADO)
            esteira_item.etapa_atual = EsteiraService._destino_aprovacao_analise(
                esteira_item
            )
            esteira_item.status = EsteiraItem.Situacao.AGUARDANDO
        elif esteira_item.etapa_atual == EsteiraItem.Etapa.COORDENACAO:
            esteira_item.etapa_atual = EsteiraItem.Etapa.TESOURARIA
            esteira_item.status = EsteiraItem.Situacao.AGUARDANDO
        else:
            contrato = esteira_item.associado.contratos.order_by("-created_at").first()
            if contrato:
                contrato.status = Contrato.Status.ATIVO
                contrato.auxilio_liberado_em = timezone.localdate()
                contrato.save()
            associado = esteira_item.associado
            associado.status = Associado.Status.ATIVO
            associado.save(update_fields=["status", "updated_at"])
            esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
            esteira_item.status = EsteiraItem.Situacao.APROVADO
            esteira_item.concluido_em = timezone.now()

        esteira_item.save()

        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            acao,
            de_etapa,
            esteira_item.etapa_atual,
            de_situacao,
            esteira_item.status,
            observacao or "Item aprovado na esteira.",
        )
        return esteira_item

    @staticmethod
    @transaction.atomic
    def pendenciar(esteira_item, user, tipo_pendencia, descricao):
        EsteiraService._validar_acao(esteira_item, "pendenciar")

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status

        destino = (
            EsteiraItem.Etapa.CADASTRO
            if esteira_item.etapa_atual == EsteiraItem.Etapa.ANALISE
            else EsteiraItem.Etapa.ANALISE
        )

        Pendencia.objects.create(
            esteira_item=esteira_item,
            tipo=tipo_pendencia,
            descricao=descricao,
        )
        esteira_item.etapa_atual = destino
        esteira_item.status = EsteiraItem.Situacao.PENDENCIADO
        esteira_item.observacao = descricao
        esteira_item.save()

        associado = esteira_item.associado
        associado.status = Associado.Status.PENDENTE
        associado.save(update_fields=["status", "updated_at"])

        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "pendenciar",
            de_etapa,
            destino,
            de_situacao,
            EsteiraItem.Situacao.PENDENCIADO,
            descricao,
        )
        return esteira_item

    @staticmethod
    def solicitar_correcao(esteira_item, user, observacao):
        return EsteiraService.pendenciar(
            esteira_item,
            user,
            "documentacao",
            observacao,
        )

    @staticmethod
    @transaction.atomic
    def validar_documento_revisto(esteira_item, user):
        Documento.objects.filter(associado=esteira_item.associado).exclude(
            status=Documento.Status.APROVADO
        ).update(status=Documento.Status.APROVADO)
        DocIssue.objects.filter(
            associado=esteira_item.associado,
            status=DocIssue.Status.INCOMPLETO,
        ).update(status=DocIssue.Status.RESOLVIDO)

        esteira_item.pendencias.filter(status=Pendencia.Status.ABERTA).update(
            status=Pendencia.Status.RESOLVIDA,
            resolvida_em=timezone.now(),
            resolvida_por=user,
        )

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status

        esteira_item.etapa_atual = EsteiraItem.Etapa.ANALISE
        esteira_item.status = EsteiraItem.Situacao.AGUARDANDO
        esteira_item.save()

        associado = esteira_item.associado
        associado.status = Associado.Status.EM_ANALISE
        associado.save(update_fields=["status", "updated_at"])

        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "validar_documento",
            de_etapa,
            EsteiraItem.Etapa.ANALISE,
            de_situacao,
            EsteiraItem.Situacao.AGUARDANDO,
            "Documentação revisada e liberada para nova análise.",
        )
        return esteira_item
