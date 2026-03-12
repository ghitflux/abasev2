from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import Transicao

from .models import Comprovante, Refinanciamento
from .strategies import StandardEligibilityStrategy


def add_months(base_date: date, months: int) -> date:
    month_index = base_date.month - 1 + months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class RefinanciamentoService:
    strategy = StandardEligibilityStrategy()

    @staticmethod
    def _get_contrato(contrato_id: int) -> Contrato:
        try:
            return (
                Contrato.objects.select_related("associado", "agente")
                .prefetch_related("ciclos__parcelas", "associado__refinanciamentos")
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
                )
                .prefetch_related("ciclo_destino__parcelas", "comprovantes")
                .get(pk=refinanciamento_id)
            )
        except Refinanciamento.DoesNotExist as exc:
            raise ValidationError("Refinanciamento não encontrado.") from exc

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
    def verificar_elegibilidade(contrato_id: int) -> dict[str, object]:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        return RefinanciamentoService.strategy.evaluate(contrato)

    @staticmethod
    @transaction.atomic
    def solicitar(contrato_id: int, user) -> Refinanciamento:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        elegibilidade = RefinanciamentoService.strategy.evaluate(contrato)
        if not elegibilidade["elegivel"]:
            raise ValidationError(elegibilidade["motivo"])

        ultimo_ciclo = contrato.ciclos.order_by("-numero").first()
        if not ultimo_ciclo:
            raise ValidationError("Contrato sem ciclo base para refinanciamento.")

        proxima_competencia = add_months(ultimo_ciclo.data_fim.replace(day=1), 1)
        ciclo_destino = Ciclo.objects.create(
            contrato=contrato,
            numero=ultimo_ciclo.numero + 1,
            data_inicio=proxima_competencia,
            data_fim=add_months(proxima_competencia, 2),
            status=Ciclo.Status.FUTURO,
            valor_total=(contrato.valor_mensalidade * Decimal("3")).quantize(
                Decimal("0.01")
            ),
        )

        parcelas = []
        for indice in range(3):
            referencia = add_months(proxima_competencia, indice)
            parcelas.append(
                Parcela(
                    ciclo=ciclo_destino,
                    numero=indice + 1,
                    referencia_mes=referencia,
                    valor=contrato.valor_mensalidade,
                    data_vencimento=referencia,
                    status=Parcela.Status.FUTURO,
                )
            )
        Parcela.objects.bulk_create(parcelas)

        valor_refinanciamento = (
            contrato.valor_liquido
            if contrato.valor_liquido
            else ciclo_destino.valor_total
        )
        repasse_agente = (valor_refinanciamento * Decimal("0.10")).quantize(
            Decimal("0.01")
        )

        refinanciamento = Refinanciamento.objects.create(
            associado=contrato.associado,
            contrato_origem=contrato,
            solicitado_por=user,
            competencia_solicitada=proxima_competencia,
            status=Refinanciamento.Status.PENDENTE_APTO,
            ciclo_origem=ultimo_ciclo,
            ciclo_destino=ciclo_destino,
            valor_refinanciamento=valor_refinanciamento,
            repasse_agente=repasse_agente,
            observacao="Solicitação criada pelo agente.",
        )

        ultimo_ciclo.status = Ciclo.Status.APTO_A_RENOVAR
        ultimo_ciclo.save(update_fields=["status", "updated_at"])

        RefinanciamentoService._registrar_auditoria(
            contrato,
            user,
            "solicitar_refinanciamento",
            "Solicitação de refinanciamento enviada para coordenação.",
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def aprovar(refinanciamento_id: int, user) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status not in [
            Refinanciamento.Status.PENDENTE_APTO,
            Refinanciamento.Status.SOLICITADO,
            Refinanciamento.Status.EM_ANALISE,
        ]:
            raise ValidationError("Refinanciamento não está apto para aprovação.")

        refinanciamento.status = Refinanciamento.Status.CONCLUIDO
        refinanciamento.aprovado_por = user
        refinanciamento.observacao = "Refinanciamento aprovado pela coordenação."
        refinanciamento.save(
            update_fields=["status", "aprovado_por", "observacao", "updated_at"]
        )

        if refinanciamento.ciclo_destino:
            refinanciamento.ciclo_destino.status = Ciclo.Status.ABERTO
            refinanciamento.ciclo_destino.save(update_fields=["status", "updated_at"])
            refinanciamento.ciclo_destino.parcelas.update(status=Parcela.Status.EM_ABERTO)

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "aprovar_refinanciamento",
            "Refinanciamento aprovado e novo ciclo ativado.",
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

        if refinanciamento.ciclo_destino:
            refinanciamento.ciclo_destino.status = Ciclo.Status.FECHADO
            refinanciamento.ciclo_destino.save(update_fields=["status", "updated_at"])
            refinanciamento.ciclo_destino.parcelas.update(
                status=Parcela.Status.CANCELADO,
                observacao=f"Refinanciamento bloqueado: {motivo}",
            )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "bloquear_refinanciamento",
            motivo,
        )
        return refinanciamento

    @staticmethod
    @transaction.atomic
    def reverter(refinanciamento_id: int, user) -> Refinanciamento:
        refinanciamento = RefinanciamentoService._get_refinanciamento(refinanciamento_id)
        if refinanciamento.status not in [
            Refinanciamento.Status.CONCLUIDO,
            Refinanciamento.Status.EFETIVADO,
        ]:
            raise ValidationError("Somente refinanciamentos concluídos podem ser revertidos.")

        refinanciamento.status = Refinanciamento.Status.REVERTIDO
        refinanciamento.observacao = "Refinanciamento revertido."
        refinanciamento.save(update_fields=["status", "observacao", "updated_at"])

        if refinanciamento.ciclo_destino:
            refinanciamento.ciclo_destino.status = Ciclo.Status.FECHADO
            refinanciamento.ciclo_destino.save(update_fields=["status", "updated_at"])
            refinanciamento.ciclo_destino.parcelas.exclude(
                status=Parcela.Status.DESCONTADO
            ).update(
                status=Parcela.Status.CANCELADO,
                observacao="Refinanciamento revertido.",
            )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "reverter_refinanciamento",
            "Refinanciamento revertido.",
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
        if refinanciamento.status != Refinanciamento.Status.CONCLUIDO:
            raise ValidationError("Somente refinanciamentos aprovados podem ser efetivados.")
        if not comprovante_associado or not comprovante_agente:
            raise ValidationError("Os dois comprovantes são obrigatórios.")

        for papel, arquivo in [
            (Comprovante.Papel.ASSOCIADO, comprovante_associado),
            (Comprovante.Papel.AGENTE, comprovante_agente),
        ]:
            Comprovante.objects.update_or_create(
                refinanciamento=refinanciamento,
                papel=papel,
                defaults={
                    "tipo": Comprovante.Tipo.PIX,
                    "arquivo": arquivo,
                    "nome_original": getattr(arquivo, "name", ""),
                    "enviado_por": user,
                    "contrato": refinanciamento.contrato_origem,
                },
            )

        refinanciamento.status = Refinanciamento.Status.EFETIVADO
        refinanciamento.efetivado_por = user
        refinanciamento.executado_em = timezone.now()
        refinanciamento.observacao = "Refinanciamento efetivado pela tesouraria."
        refinanciamento.save(
            update_fields=[
                "status",
                "efetivado_por",
                "executado_em",
                "observacao",
                "updated_at",
            ]
        )

        RefinanciamentoService._registrar_auditoria(
            refinanciamento.contrato_origem,
            user,
            "efetivar_refinanciamento",
            "Tesouraria anexou comprovantes e efetivou o refinanciamento.",
        )
        return refinanciamento
