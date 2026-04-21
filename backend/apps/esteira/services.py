from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado, Documento
from apps.contratos.canonicalization import resolve_operational_contract_for_associado
from apps.contratos.soft_delete import soft_delete_contract_tree
from apps.contratos.models import Contrato
from apps.refinanciamento.models import Refinanciamento

from .models import DocIssue, DocReupload, EsteiraItem, Pendencia, Transicao
from .strategies import AnalistaApprovalStrategy, CoordenadorApprovalStrategy


class EsteiraService:
    """State machine para o workflow de aprovação."""

    TRANSICOES_VALIDAS = {
        ("analise", "aguardando"): ["assumir"],
        ("analise", "em_andamento"): [
            "aprovar",
            "pendenciar",
            "solicitar_correcao",
            "reprovar",
        ],
        ("coordenacao", "aguardando"): ["assumir"],
        ("coordenacao", "em_andamento"): ["aprovar", "pendenciar", "rejeitar"],
        ("tesouraria", "aguardando"): ["efetivar"],
    }

    @staticmethod
    def _user_can_delete_broadly(user) -> bool:
        return bool(
            user
            and getattr(user, "is_authenticated", False)
            and hasattr(user, "has_role")
            and user.has_role("ADMIN", "COORDENADOR")
        )

    @staticmethod
    def _can_delete_restricted(esteira_item: EsteiraItem) -> bool:
        return bool(
            esteira_item.status == EsteiraItem.Situacao.AGUARDANDO
            and esteira_item.assumido_em is None
            and esteira_item.analista_responsavel_id is None
            and esteira_item.coordenador_responsavel_id is None
            and esteira_item.tesoureiro_responsavel_id is None
        )

    @staticmethod
    def can_delete(esteira_item: EsteiraItem, user=None) -> bool:
        if EsteiraService._user_can_delete_broadly(user):
            return True
        return EsteiraService._can_delete_restricted(esteira_item)

    @staticmethod
    def get_available_actions(esteira_item: EsteiraItem, user=None) -> list[str]:
        actions = list(
            EsteiraService.TRANSICOES_VALIDAS.get(
                (esteira_item.etapa_atual, esteira_item.status),
                [],
            )
        )
        if EsteiraService.can_delete(esteira_item, user=user):
            actions.append("excluir")
        return actions

    @staticmethod
    def _resolve_operational_delete_mode(
        esteira_item: EsteiraItem,
    ) -> tuple[str, str, str]:
        associado = esteira_item.associado
        contrato = resolve_operational_contract_for_associado(associado)
        contrato_cancelado = (
            associado.contratos.filter(
                deleted_at__isnull=True,
                status=Contrato.Status.CANCELADO,
            )
            .order_by("-updated_at", "-id")
            .first()
        )

        if (
            contrato_cancelado is not None
        ) or associado.status == Associado.Status.INATIVO:
            return (
                "preserve",
                EsteiraItem.Situacao.REJEITADO,
                "Item removido da fila com histórico preservado. O status real do associado indica cancelamento ou inativação.",
            )

        if (
            contrato is not None
            and (
                contrato.status in {Contrato.Status.ATIVO, Contrato.Status.ENCERRADO}
                or contrato.auxilio_liberado_em is not None
            )
        ) or associado.status in {
            Associado.Status.ATIVO,
            Associado.Status.INADIMPLENTE,
        }:
            return (
                "preserve",
                EsteiraItem.Situacao.APROVADO,
                "Item removido da fila com histórico preservado. O status real do associado/contrato já está consolidado.",
            )

        return (
            "soft_delete",
            EsteiraItem.Situacao.REJEITADO,
            "Cadastro pré-operacional removido por exclusão operacional.",
        )

    @staticmethod
    def _cancelar_pendencias_abertas(esteira_item: EsteiraItem, user) -> None:
        now = timezone.now()
        for pendencia in esteira_item.pendencias.filter(
            deleted_at__isnull=True,
            status=Pendencia.Status.ABERTA,
        ):
            pendencia.status = Pendencia.Status.CANCELADA
            pendencia.resolvida_em = now
            pendencia.resolvida_por = user
            pendencia.save(
                update_fields=[
                    "status",
                    "resolvida_em",
                    "resolvida_por",
                    "updated_at",
                ]
            )

    @staticmethod
    def _finalize_operational_exclusion(
        esteira_item: EsteiraItem,
        *,
        user,
        target_status: str,
        observacao: str,
    ) -> None:
        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status
        now = timezone.now()
        EsteiraService._cancelar_pendencias_abertas(esteira_item, user)
        esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
        esteira_item.status = target_status
        esteira_item.concluido_em = now
        esteira_item.observacao = observacao
        esteira_item.assumido_em = None
        esteira_item.save(
            update_fields=[
                "etapa_atual",
                "status",
                "concluido_em",
                "observacao",
                "assumido_em",
                "updated_at",
            ]
        )
        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "excluir_preservando_historico",
            de_etapa,
            EsteiraItem.Etapa.CONCLUIDO,
            de_situacao,
            target_status,
            observacao,
        )

    @staticmethod
    def _pending_reactivation_contract(esteira_item: EsteiraItem) -> Contrato | None:
        return (
            Contrato.objects.filter(
                associado_id=esteira_item.associado_id,
                deleted_at__isnull=True,
                contrato_canonico__isnull=True,
                origem_operacional=Contrato.OrigemOperacional.REATIVACAO,
            )
            .exclude(
                status__in=[
                    Contrato.Status.ATIVO,
                    Contrato.Status.CANCELADO,
                    Contrato.Status.ENCERRADO,
                ]
            )
            .order_by("-created_at", "-id")
            .first()
        )

    @staticmethod
    def _reset_item_to_stage(
        esteira_item: EsteiraItem,
        *,
        user,
        target_stage: str,
        action: str,
        observacao: str,
    ) -> None:
        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status
        EsteiraService._cancelar_pendencias_abertas(esteira_item, user)
        esteira_item.etapa_atual = target_stage
        esteira_item.status = EsteiraItem.Situacao.AGUARDANDO
        esteira_item.observacao = observacao
        esteira_item.assumido_em = None
        esteira_item.heartbeat_at = None
        esteira_item.concluido_em = None
        esteira_item.analista_responsavel = None
        esteira_item.coordenador_responsavel = None
        esteira_item.tesoureiro_responsavel = None
        esteira_item.save(
            update_fields=[
                "etapa_atual",
                "status",
                "observacao",
                "assumido_em",
                "heartbeat_at",
                "concluido_em",
                "analista_responsavel",
                "coordenador_responsavel",
                "tesoureiro_responsavel",
                "updated_at",
            ]
        )
        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            action,
            de_etapa,
            target_stage,
            de_situacao,
            EsteiraItem.Situacao.AGUARDANDO,
            observacao,
        )

    @staticmethod
    def normalizar_inativacao_associado(
        associado: Associado,
        user=None,
        *,
        observacao: str = "Associado inativado; fila operacional residual finalizada.",
    ) -> None:
        esteira_item = EsteiraItem.objects.filter(associado=associado).first()
        if esteira_item is None:
            return
        if (
            esteira_item.etapa_atual == EsteiraItem.Etapa.CONCLUIDO
            and esteira_item.status
            in {EsteiraItem.Situacao.APROVADO, EsteiraItem.Situacao.REJEITADO}
        ):
            return

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status
        now = timezone.now()
        if user is not None:
            EsteiraService._cancelar_pendencias_abertas(esteira_item, user)
        esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
        esteira_item.status = EsteiraItem.Situacao.REJEITADO
        esteira_item.concluido_em = now
        esteira_item.observacao = observacao
        esteira_item.assumido_em = None
        esteira_item.heartbeat_at = None
        esteira_item.analista_responsavel = None
        esteira_item.coordenador_responsavel = None
        esteira_item.tesoureiro_responsavel = None
        esteira_item.save(
            update_fields=[
                "etapa_atual",
                "status",
                "concluido_em",
                "observacao",
                "assumido_em",
                "heartbeat_at",
                "analista_responsavel",
                "coordenador_responsavel",
                "tesoureiro_responsavel",
                "updated_at",
            ]
        )
        if user is not None:
            EsteiraService._registrar_transicao(
                esteira_item,
                user,
                "inativar_associado",
                de_etapa,
                EsteiraItem.Etapa.CONCLUIDO,
                de_situacao,
                EsteiraItem.Situacao.REJEITADO,
                observacao,
            )

    @staticmethod
    def _cancel_pending_reactivation(
        esteira_item: EsteiraItem,
        *,
        user,
        action: str,
        observacao: str,
    ) -> bool:
        contrato = EsteiraService._pending_reactivation_contract(esteira_item)
        if contrato is None:
            return False

        de_etapa = esteira_item.etapa_atual
        de_situacao = esteira_item.status
        now = timezone.now()
        EsteiraService._cancelar_pendencias_abertas(esteira_item, user)

        contrato.status = Contrato.Status.CANCELADO
        contrato.cancelamento_tipo = Contrato.CancelamentoTipo.CANCELADO
        contrato.cancelamento_motivo = observacao
        contrato.cancelado_em = now
        contrato.save(
            update_fields=[
                "status",
                "cancelamento_tipo",
                "cancelamento_motivo",
                "cancelado_em",
                "updated_at",
            ]
        )

        associado = esteira_item.associado
        associado.status = Associado.Status.INATIVO
        associado.save(update_fields=["status", "updated_at"])

        esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
        esteira_item.status = EsteiraItem.Situacao.REJEITADO
        esteira_item.concluido_em = now
        esteira_item.observacao = observacao
        esteira_item.assumido_em = None
        esteira_item.heartbeat_at = None
        esteira_item.save(
            update_fields=[
                "etapa_atual",
                "status",
                "concluido_em",
                "observacao",
                "assumido_em",
                "heartbeat_at",
                "updated_at",
            ]
        )
        if user is not None:
            EsteiraService._registrar_transicao(
                esteira_item,
                user,
                action,
                de_etapa,
                EsteiraItem.Etapa.CONCLUIDO,
                de_situacao,
                EsteiraItem.Situacao.REJEITADO,
                observacao,
            )
        return True

    @staticmethod
    @transaction.atomic
    def garantir_item_inicial_cadastro(
        associado: Associado,
        user,
        *,
        observacao: str = "Cadastro inicial enviado para análise.",
    ) -> tuple[EsteiraItem, bool]:
        esteira_item = EsteiraItem.objects.filter(associado=associado).first()
        if esteira_item is not None:
            return esteira_item, False

        esteira_item = EsteiraItem.objects.create(
            associado=associado,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "criar_cadastro",
            EsteiraItem.Etapa.CADASTRO,
            EsteiraItem.Etapa.ANALISE,
            EsteiraItem.Situacao.AGUARDANDO,
            EsteiraItem.Situacao.AGUARDANDO,
            observacao,
        )
        return esteira_item, True

    @staticmethod
    @transaction.atomic
    def enviar_reativacao_para_analise(
        associado: Associado,
        user,
        *,
        observacao: str = "Reativação enviada para análise.",
    ) -> tuple[EsteiraItem, bool]:
        esteira_item = EsteiraItem.objects.filter(associado=associado).first()
        created = esteira_item is None

        if esteira_item is None:
            esteira_item = EsteiraItem.objects.create(
                associado=associado,
                etapa_atual=EsteiraItem.Etapa.ANALISE,
                status=EsteiraItem.Situacao.AGUARDANDO,
                observacao=observacao,
            )
            EsteiraService._registrar_transicao(
                esteira_item,
                user,
                "reativar_associado",
                EsteiraItem.Etapa.CONCLUIDO,
                EsteiraItem.Etapa.ANALISE,
                EsteiraItem.Situacao.REJEITADO,
                EsteiraItem.Situacao.AGUARDANDO,
                observacao,
            )
        else:
            EsteiraService._reset_item_to_stage(
                esteira_item,
                user=user,
                target_stage=EsteiraItem.Etapa.ANALISE,
                action="reativar_associado",
                observacao=observacao,
            )

        return esteira_item, created

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
        if EsteiraService._pending_reactivation_contract(esteira_item) is not None:
            return EsteiraItem.Etapa.TESOURARIA

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
            contrato = resolve_operational_contract_for_associado(esteira_item.associado)
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
    def _soft_delete_solicitacao_package(esteira_item: EsteiraItem) -> None:
        associado = esteira_item.associado

        for pendencia in esteira_item.pendencias.filter(deleted_at__isnull=True):
            pendencia.soft_delete()
        for transicao in esteira_item.transicoes.filter(deleted_at__isnull=True):
            transicao.soft_delete()
        for documento in associado.documentos.filter(deleted_at__isnull=True):
            documento.soft_delete()
        for issue in associado.doc_issues.filter(deleted_at__isnull=True):
            issue.soft_delete()
        for reupload in DocReupload.objects.filter(
            associado=associado,
            deleted_at__isnull=True,
        ):
            reupload.soft_delete()
        for contrato in associado.contratos.filter(deleted_at__isnull=True).order_by("id"):
            soft_delete_contract_tree(contrato)

        esteira_item.soft_delete()
        associado.soft_delete()

    @staticmethod
    @transaction.atomic
    def excluir_solicitacao(esteira_item: EsteiraItem, user=None) -> None:
        if EsteiraService._pending_reactivation_contract(esteira_item) is not None:
            if not EsteiraService._user_can_delete_broadly(
                user
            ) and not EsteiraService._can_delete_restricted(esteira_item):
                raise ValidationError(
                    "Somente itens aguardando, sem assunção e sem responsáveis podem ser excluídos."
                )
            EsteiraService._cancel_pending_reactivation(
                esteira_item,
                user=user,
                action="excluir_preservando_historico",
                observacao="Reativação cancelada com histórico anterior preservado.",
            )
            return

        if EsteiraService._user_can_delete_broadly(user):
            mode, target_status, observacao = (
                EsteiraService._resolve_operational_delete_mode(esteira_item)
            )
            if mode == "soft_delete":
                EsteiraService._soft_delete_solicitacao_package(esteira_item)
                return
            EsteiraService._finalize_operational_exclusion(
                esteira_item,
                user=user,
                target_status=target_status,
                observacao=observacao,
            )
            return

        if not EsteiraService._can_delete_restricted(esteira_item):
            raise ValidationError(
                "Somente itens aguardando, sem assunção e sem responsáveis podem ser excluídos."
            )

        EsteiraService._soft_delete_solicitacao_package(esteira_item)

    @staticmethod
    @transaction.atomic
    def reprovar(esteira_item: EsteiraItem, user, observacao: str = "") -> None:
        EsteiraService._validar_acao(esteira_item, "reprovar")

        if esteira_item.etapa_atual != EsteiraItem.Etapa.ANALISE:
            raise ValidationError("A reprovação só está disponível na etapa de análise.")
        if (
            esteira_item.analista_responsavel_id
            and esteira_item.analista_responsavel_id != user.id
        ):
            raise ValidationError("Este item foi assumido por outro analista.")

        if EsteiraService._cancel_pending_reactivation(
            esteira_item,
            user=user,
            action="reprovar",
            observacao=observacao
            or "Reativação reprovada na análise com histórico anterior preservado.",
        ):
            return

        EsteiraService._registrar_transicao(
            esteira_item,
            user,
            "reprovar",
            esteira_item.etapa_atual,
            EsteiraItem.Etapa.CONCLUIDO,
            esteira_item.status,
            EsteiraItem.Situacao.REJEITADO,
            observacao or "Cadastro reprovado na análise e removido da operação.",
        )
        EsteiraService._soft_delete_solicitacao_package(esteira_item)

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
