from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.cycle_timeline import get_contract_cycle_size
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import Transicao
from apps.importacao.models import PagamentoMensalidade
from apps.tesouraria.models import Pagamento

from .models import Assumption, Comprovante, Item, Refinanciamento
from .strategies import StandardEligibilityStrategy

_OPERATIONAL_ACTIVE_STATUSES = {
    Refinanciamento.Status.APTO_A_RENOVAR,
    Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO,
    Refinanciamento.Status.EM_ANALISE_RENOVACAO,
    Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
    Refinanciamento.Status.PENDENTE_APTO,
    Refinanciamento.Status.SOLICITADO,
    Refinanciamento.Status.EM_ANALISE,
    Refinanciamento.Status.APROVADO,
    Refinanciamento.Status.CONCLUIDO,
}


def _normalize_status(status: str) -> str:
    mapping = {
        Refinanciamento.Status.PENDENTE_APTO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.SOLICITADO: Refinanciamento.Status.APTO_A_RENOVAR,
        Refinanciamento.Status.EM_ANALISE: Refinanciamento.Status.EM_ANALISE_RENOVACAO,
        Refinanciamento.Status.APROVADO: Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
        Refinanciamento.Status.CONCLUIDO: Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
    }
    return mapping.get(status, status)


def _cycle_key(parcelas: list[dict[str, object]]) -> str:
    referencias = [parcela["referencia_mes"] for parcela in parcelas]
    return "|".join(referencia.strftime("%Y-%m") for referencia in referencias)


def _paid_projection_parcelas(parcelas: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        parcela
        for parcela in parcelas
        if parcela["status"] == Parcela.Status.DESCONTADO
    ]


class RefinanciamentoService:
    strategy = StandardEligibilityStrategy()

    @staticmethod
    def _get_contrato(contrato_id: int) -> Contrato:
        try:
            return (
                Contrato.objects.select_related("associado", "agente")
                .prefetch_related(
                    "ciclos__parcelas",
                    "associado__refinanciamentos",
                    "associado__pagamentos_mensalidades__refi_itens",
                    "associado__tesouraria_pagamentos",
                )
                .get(pk=contrato_id)
            )
        except Contrato.DoesNotExist as exc:
            raise ValidationError("Contrato não encontrado.") from exc

    @staticmethod
    def _get_refinanciamento(refinanciamento_id: int) -> Refinanciamento:
        try:
            return (
                Refinanciamento.objects.select_related(
                    "associado",
                    "contrato_origem",
                    "contrato_origem__agente",
                    "ciclo_origem",
                    "ciclo_destino",
                    "solicitado_por",
                    "aprovado_por",
                    "bloqueado_por",
                    "efetivado_por",
                    "reviewed_by",
                )
                .prefetch_related(
                    "ciclo_origem__parcelas",
                    "ciclo_destino__parcelas",
                    "comprovantes__enviado_por",
                    "itens__pagamento_mensalidade",
                )
                .get(pk=refinanciamento_id)
            )
        except Refinanciamento.DoesNotExist as exc:
            raise ValidationError("Refinanciamento não encontrado.") from exc

    @staticmethod
    def _serialize_pagamento_seed(pagamento: PagamentoMensalidade) -> dict[str, object]:
        return {
            "pagamento_mensalidade_id": pagamento.id,
            "referencia_month": pagamento.referencia_month.isoformat(),
            "status_code": pagamento.status_code or "1",
            "valor": str(pagamento.valor or Decimal("0.00")),
            "import_uuid": pagamento.import_uuid,
            "source_file_path": pagamento.source_file_path,
        }

    @staticmethod
    def _registrar_auditoria(contrato: Contrato, user, acao: str, observacao: str):
        esteira_item = getattr(contrato.associado, "esteira_item", None)
        if not esteira_item:
            return

        Transicao.objects.create(
            esteira_item=esteira_item,
            acao=acao,
            de_status=esteira_item.etapa_atual,
            para_status=esteira_item.etapa_atual,
            de_situacao=esteira_item.status,
            para_situacao=esteira_item.status,
            realizado_por=user,
            observacao=observacao,
        )

    @staticmethod
    def _active_operational_refinanciamento(contrato: Contrato) -> Refinanciamento | None:
        return (
            Refinanciamento.objects.filter(
                contrato_origem=contrato,
                deleted_at__isnull=True,
                legacy_refinanciamento_id__isnull=True,
                origem=Refinanciamento.Origem.OPERACIONAL,
                status__in=_OPERATIONAL_ACTIVE_STATUSES,
            )
            .order_by("-created_at", "-id")
            .first()
        )

    @staticmethod
    def _assumption_for_refinanciamento(refinanciamento: Refinanciamento) -> Assumption | None:
        if not refinanciamento.cycle_key:
            return None
        return Assumption.objects.filter(
            cadastro=refinanciamento.associado,
            request_key=refinanciamento.cycle_key,
        ).order_by("-created_at", "-id").first()

    @staticmethod
    def _sync_contract_and_get_refi(contrato: Contrato) -> tuple[dict[str, object], Refinanciamento | None]:
        rebuild_contract_cycle_state(contrato, execute=True)
        contrato.refresh_from_db()
        projection = build_contract_cycle_projection(contrato)
        return projection, RefinanciamentoService._active_operational_refinanciamento(contrato)

    @staticmethod
    def verificar_elegibilidade(contrato_id: int) -> dict[str, object]:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        return RefinanciamentoService.strategy.evaluate(contrato)

    @staticmethod
    @transaction.atomic
    def solicitar(contrato_id: int, termo_antecipacao, user) -> Refinanciamento:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        evaluation = RefinanciamentoService.strategy.evaluate(contrato)
        if not evaluation["elegivel"]:
            raise ValidationError(evaluation["motivo"])
        if not termo_antecipacao:
            raise ValidationError("O termo de antecipação é obrigatório.")

        _, refinanciamento = RefinanciamentoService._sync_contract_and_get_refi(
            contrato
        )
        if refinanciamento is None:
            raise ValidationError(
                "A fila operacional de renovação não pôde ser materializada."
            )

        normalized_status = _normalize_status(refinanciamento.status)
        if normalized_status != Refinanciamento.Status.APTO_A_RENOVAR:
            raise ValidationError(
                "Esta renovação já foi enviada para análise ou está em etapa posterior."
            )

        refinanciamento.status = Refinanciamento.Status.EM_ANALISE_RENOVACAO
        refinanciamento.solicitado_por = user
        refinanciamento.reviewed_by = None
        refinanciamento.reviewed_at = None
        refinanciamento.analista_note = ""
        refinanciamento.coordenador_note = ""
        refinanciamento.termo_antecipacao_path = getattr(termo_antecipacao, "name", "")
        refinanciamento.termo_antecipacao_original_name = getattr(
            termo_antecipacao, "name", ""
        )
        refinanciamento.termo_antecipacao_mime = (
            getattr(termo_antecipacao, "content_type", "") or ""
        )
        refinanciamento.termo_antecipacao_size_bytes = getattr(
            termo_antecipacao, "size", None
        )
        refinanciamento.termo_antecipacao_uploaded_at = timezone.now()
        refinanciamento.save(
            update_fields=[
                "status",
                "solicitado_por",
                "reviewed_by",
                "reviewed_at",
                "analista_note",
                "coordenador_note",
                "termo_antecipacao_path",
                "termo_antecipacao_original_name",
                "termo_antecipacao_mime",
                "termo_antecipacao_size_bytes",
                "termo_antecipacao_uploaded_at",
                "updated_at",
            ]
        )

        Comprovante.objects.create(
            refinanciamento=refinanciamento,
            contrato=contrato,
            ciclo=refinanciamento.ciclo_origem,
            tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
            papel=Comprovante.Papel.AGENTE,
            origem=Comprovante.Origem.SOLICITACAO_RENOVACAO,
            arquivo=termo_antecipacao,
            nome_original=getattr(termo_antecipacao, "name", ""),
            enviado_por=user,
        )

        assumption = RefinanciamentoService._assumption_for_refinanciamento(refinanciamento)
        if assumption:
            assumption.status = Assumption.Status.LIBERADO
            assumption.solicitado_por = user
            assumption.liberado_em = timezone.now()
            assumption.assumido_em = None
            assumption.finalizado_em = None
            assumption.analista = None
            assumption.heartbeat_at = None
            assumption.save(
                update_fields=[
                    "status",
                    "solicitado_por",
                    "liberado_em",
                    "assumido_em",
                    "finalizado_em",
                    "analista",
                    "heartbeat_at",
                    "updated_at",
                ]
            )

        RefinanciamentoService._registrar_auditoria(
            contrato,
            user,
            "solicitar_renovacao_analise",
            "Agente anexou o termo de antecipação e enviou a renovação para análise.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def solicitar_liquidacao(contrato_id: int, user) -> Refinanciamento:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        evaluation = RefinanciamentoService.strategy.evaluate(contrato)
        if not evaluation["elegivel"]:
            raise ValidationError(evaluation["motivo"])

        _, refinanciamento = RefinanciamentoService._sync_contract_and_get_refi(
            contrato
        )
        if refinanciamento is None:
            raise ValidationError(
                "A fila operacional de renovação não pôde ser materializada."
            )

        normalized_status = _normalize_status(refinanciamento.status)
        if normalized_status != Refinanciamento.Status.APTO_A_RENOVAR:
            raise ValidationError(
                "Este contrato já foi encaminhado para renovação ou liquidação."
            )

        refinanciamento.status = Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO
        refinanciamento.solicitado_por = user
        refinanciamento.reviewed_by = None
        refinanciamento.reviewed_at = None
        refinanciamento.analista_note = ""
        refinanciamento.coordenador_note = ""
        refinanciamento.observacao = "Solicitação de liquidação aberta pelo agente."
        refinanciamento.save(
            update_fields=[
                "status",
                "solicitado_por",
                "reviewed_by",
                "reviewed_at",
                "analista_note",
                "coordenador_note",
                "observacao",
                "updated_at",
            ]
        )

        RefinanciamentoService._registrar_auditoria(
            contrato,
            user,
            "solicitar_liquidacao_renovacao",
            "Agente optou por encerrar o contrato via liquidação em vez de enviar a renovação.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def aprovar(refinanciamento_id: int, user, observacao: str = "") -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if (
            _normalize_status(refinanciamento.status)
            != Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO
        ):
            raise ValidationError(
                "Somente renovações aprovadas pela análise podem seguir para a tesouraria."
            )

        refinanciamento.status = Refinanciamento.Status.APROVADO_PARA_RENOVACAO
        refinanciamento.aprovado_por = user
        refinanciamento.coordenador_note = (
            observacao.strip() or "Renovação validada pela coordenação."
        )
        refinanciamento.save(
            update_fields=["status", "aprovado_por", "coordenador_note", "updated_at"]
        )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "aprovar_renovacao_coordenacao",
            "Coordenação validou os anexos e encaminhou a renovação para a tesouraria.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def assumir_analise(refinanciamento_id: int, user) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status != Refinanciamento.Status.EM_ANALISE_RENOVACAO:
            raise ValidationError("A renovação não está disponível para análise.")

        assumption = RefinanciamentoService._assumption_for_refinanciamento(refinanciamento)
        if assumption is None:
            raise ValidationError("Nenhuma fila analítica foi encontrada para esta renovação.")
        if (
            assumption.status == Assumption.Status.ASSUMIDO
            and assumption.analista_id
            and assumption.analista_id != user.id
        ):
            raise ValidationError("Esta renovação já foi assumida por outro analista.")

        assumption.analista = user
        assumption.status = Assumption.Status.ASSUMIDO
        assumption.assumido_em = timezone.now()
        assumption.heartbeat_at = timezone.now()
        assumption.save(
            update_fields=["analista", "status", "assumido_em", "heartbeat_at", "updated_at"]
        )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "assumir_renovacao_analise",
            "Renovação assumida na fila analítica.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def aprovar_analise(
        refinanciamento_id: int,
        user,
        observacao: str = "",
    ) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status != Refinanciamento.Status.EM_ANALISE_RENOVACAO:
            raise ValidationError("A renovação não está disponível para aprovação analítica.")

        assumption = RefinanciamentoService._assumption_for_refinanciamento(refinanciamento)
        if assumption and assumption.analista_id and assumption.analista_id != user.id:
            raise ValidationError("A renovação foi assumida por outro analista.")

        refinanciamento.status = Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO
        refinanciamento.reviewed_by = user
        refinanciamento.reviewed_at = timezone.now()
        refinanciamento.analista_note = observacao
        refinanciamento.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "analista_note",
                "updated_at",
            ]
        )

        if assumption:
            if assumption.analista_id is None:
                assumption.analista = user
            assumption.status = Assumption.Status.FINALIZADO
            assumption.finalizado_em = timezone.now()
            assumption.save(
                update_fields=["analista", "status", "finalizado_em", "updated_at"]
            )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "aprovar_renovacao_analise",
            "Analista aprovou a renovação e encaminhou o caso para validação da coordenação.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def bloquear(refinanciamento_id: int, motivo: str, user) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status in [
            Refinanciamento.Status.BLOQUEADO,
            Refinanciamento.Status.REVERTIDO,
            Refinanciamento.Status.EFETIVADO,
            Refinanciamento.Status.DESATIVADO,
        ]:
            raise ValidationError("Refinanciamento já está em estado final.")

        refinanciamento.status = Refinanciamento.Status.BLOQUEADO
        refinanciamento.bloqueado_por = user
        refinanciamento.motivo_bloqueio = motivo
        refinanciamento.observacao = motivo
        refinanciamento.save(
            update_fields=[
                "status",
                "bloqueado_por",
                "motivo_bloqueio",
                "observacao",
                "updated_at",
            ]
        )

        assumption = RefinanciamentoService._assumption_for_refinanciamento(refinanciamento)
        if assumption:
            assumption.status = Assumption.Status.FINALIZADO
            assumption.finalizado_em = timezone.now()
            assumption.save(update_fields=["status", "finalizado_em", "updated_at"])

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "bloquear_refinanciamento",
            motivo,
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def desativar(refinanciamento_id: int, motivo: str, user) -> Refinanciamento:
        raise ValidationError(
            "A desativação direta da renovação foi bloqueada. Use a liquidação do contrato para encerrar os meses pendentes."
        )

    @staticmethod
    @transaction.atomic
    def reverter(refinanciamento_id: int, user) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status not in [
            Refinanciamento.Status.APROVADO_ANALISE_RENOVACAO,
            Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            Refinanciamento.Status.CONCLUIDO,
        ]:
            raise ValidationError("Somente renovações aprovadas podem ser revertidas.")

        refinanciamento.status = Refinanciamento.Status.REVERTIDO
        refinanciamento.observacao = "Renovação revertida."
        refinanciamento.save(update_fields=["status", "observacao", "updated_at"])

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "reverter_refinanciamento",
            "Renovação revertida antes da efetivação da tesouraria.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def efetivar(
        refinanciamento_id: int,
        comprovante_associado,
        comprovante_agente,
        user,
    ) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if _normalize_status(refinanciamento.status) != Refinanciamento.Status.APROVADO_PARA_RENOVACAO:
            raise ValidationError(
                "Somente renovações validadas pela coordenação podem ser efetivadas."
            )
        if not comprovante_associado or not comprovante_agente:
            raise ValidationError("Os dois comprovantes são obrigatórios.")

        contrato = refinanciamento.contrato_origem
        if contrato is None:
            raise ValidationError("Renovação sem contrato de origem.")

        executado_em = timezone.now()
        Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=user,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=refinanciamento.valor_refinanciamento,
            contrato_margem_disponivel=contrato.margem_disponivel,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=contrato.agente.full_name if contrato.agente else "",
            origem=Pagamento.Origem.OPERACIONAL,
            status=Pagamento.Status.PAGO,
            valor_pago=refinanciamento.valor_refinanciamento,
            paid_at=executado_em,
            forma_pagamento="pix",
            comprovante_associado_path=getattr(comprovante_associado, "name", ""),
            comprovante_agente_path=getattr(comprovante_agente, "name", ""),
            notes=f"Renovação efetivada via tesouraria para refi #{refinanciamento.id}.",
        )

        refinanciamento.status = Refinanciamento.Status.EFETIVADO
        refinanciamento.efetivado_por = user
        refinanciamento.executado_em = executado_em
        refinanciamento.data_ativacao_ciclo = executado_em
        refinanciamento.origem = Refinanciamento.Origem.OPERACIONAL
        refinanciamento.observacao = "Renovação efetivada pela tesouraria."
        refinanciamento.save(
            update_fields=[
                "status",
                "efetivado_por",
                "executado_em",
                "data_ativacao_ciclo",
                "origem",
                "observacao",
                "updated_at",
            ]
        )

        rebuild_contract_cycle_state(contrato, execute=True)
        refinanciamento.refresh_from_db()

        for papel, arquivo, tipo in [
            (
                Comprovante.Papel.ASSOCIADO,
                comprovante_associado,
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            ),
            (
                Comprovante.Papel.AGENTE,
                comprovante_agente,
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            ),
        ]:
            Comprovante.objects.create(
                refinanciamento=refinanciamento,
                contrato=contrato,
                ciclo=refinanciamento.ciclo_destino,
                tipo=tipo,
                papel=papel,
                origem=Comprovante.Origem.TESOURARIA_RENOVACAO,
                arquivo=arquivo,
                nome_original=getattr(arquivo, "name", ""),
                enviado_por=user,
                data_pagamento=executado_em,
                agente_snapshot=contrato.agente.full_name if contrato.agente else "",
            )

        RefinanciamentoService._registrar_auditoria(
            contrato,
            user,
            "efetivar_refinanciamento",
            "Tesouraria anexou comprovantes e materializou o próximo ciclo.",
        )
        return refinanciamento
