from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.contratos.competencia import create_cycle_with_parcelas
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import Transicao
from apps.importacao.models import PagamentoMensalidade

from .models import Comprovante, Item, Refinanciamento
from .payment_rules import (
    REFINANCIAMENTO_MENSALIDADES_NECESSARIAS,
    get_free_paid_pagamentos,
    has_active_refinanciamento,
)
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
                .prefetch_related(
                    "ciclo_destino__parcelas",
                    "comprovantes",
                    "itens__pagamento_mensalidade",
                )
                .get(pk=refinanciamento_id)
            )
        except Refinanciamento.DoesNotExist as exc:
            raise ValidationError("Refinanciamento não encontrado.") from exc

    @staticmethod
    def _serialize_pagamento_seed(
        pagamento: PagamentoMensalidade,
    ) -> dict[str, object]:
        return {
            "pagamento_mensalidade_id": pagamento.id,
            "referencia_month": pagamento.referencia_month.isoformat(),
            "status_code": pagamento.status_code,
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
    def verificar_elegibilidade(contrato_id: int) -> dict[str, object]:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        return RefinanciamentoService.strategy.evaluate(contrato)

    @staticmethod
    @transaction.atomic
    def solicitar(contrato_id: int, user) -> Refinanciamento:
        contrato = RefinanciamentoService._get_contrato(contrato_id)
        if has_active_refinanciamento(contrato):
            raise ValidationError("CPF já possui refinanciamento ativo ou pendente.")

        ultimo_ciclo = contrato.ciclos.order_by("-numero").first()
        if not ultimo_ciclo:
            raise ValidationError("Contrato sem ciclo base para refinanciamento.")

        pagamentos_base = get_free_paid_pagamentos(
            contrato,
            limit=REFINANCIAMENTO_MENSALIDADES_NECESSARIAS,
            for_update=True,
        )
        if len(pagamentos_base) < REFINANCIAMENTO_MENSALIDADES_NECESSARIAS:
            raise ValidationError(
                f"Apenas {len(pagamentos_base)}/3 pagamentos elegíveis foram identificados."
            )

        referencias_base = [
            pagamento.referencia_month.replace(day=1) for pagamento in pagamentos_base
        ]
        referencias_base.sort()
        cycle_key = "|".join(
            referencia.strftime("%Y-%m") for referencia in referencias_base
        )
        proxima_competencia = add_months(referencias_base[-1], 1)
        ciclo_destino, _parcelas = create_cycle_with_parcelas(
            contrato=contrato,
            numero=ultimo_ciclo.numero + 1,
            competencia_inicial=proxima_competencia,
            parcelas_total=3,
            ciclo_status=Ciclo.Status.FUTURO,
            parcela_status=Parcela.Status.FUTURO,
            valor_mensalidade=contrato.valor_mensalidade,
            valor_total=(contrato.valor_mensalidade * Decimal("3")).quantize(
                Decimal("0.01")
            ),
        )

        valor_refinanciamento = (
            contrato.valor_liquido
            if contrato.valor_liquido
            else ciclo_destino.valor_total
        )
        repasse_agente = (valor_refinanciamento * Decimal("0.10")).quantize(
            Decimal("0.01")
        )
        agente = contrato.agente or contrato.associado.agente_responsavel
        solicitacao_origem = (
            "Solicitação criada pelo admin."
            if user.has_role("ADMIN")
            else "Solicitação criada pelo agente."
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
            observacao=solicitacao_origem,
            mode="admin_auto" if user.has_role("ADMIN") else "auto",
            cycle_key=cycle_key,
            ref1=referencias_base[0],
            ref2=referencias_base[1],
            ref3=referencias_base[2],
            cpf_cnpj_snapshot=contrato.associado.cpf_cnpj,
            nome_snapshot=contrato.associado.nome_completo,
            agente_snapshot=agente.full_name if agente else "",
            contrato_codigo_origem=contrato.codigo,
            contrato_codigo_novo=contrato.codigo,
            parcelas_ok=REFINANCIAMENTO_MENSALIDADES_NECESSARIAS,
            parcelas_json=[
                RefinanciamentoService._serialize_pagamento_seed(pagamento)
                for pagamento in pagamentos_base
            ],
        )
        Item.objects.bulk_create(
            [
                Item(
                    refinanciamento=refinanciamento,
                    pagamento_mensalidade=pagamento,
                    referencia_month=pagamento.referencia_month,
                    status_code=pagamento.status_code,
                    valor=pagamento.valor,
                    import_uuid=pagamento.import_uuid,
                    source_file_path=pagamento.source_file_path,
                )
                for pagamento in pagamentos_base
            ]
        )
        PagamentoMensalidade.objects.filter(
            id__in=[pagamento.id for pagamento in pagamentos_base]
        ).update(agente_refi_solicitado=True)

        ultimo_ciclo.status = Ciclo.Status.APTO_A_RENOVAR
        ultimo_ciclo.save(update_fields=["status", "updated_at"])

        RefinanciamentoService._registrar_auditoria(
            contrato,
            user,
            "solicitar_refinanciamento",
            f"Solicitação de refinanciamento enviada para coordenação com base em {cycle_key}.",
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
                competencia_lock=None,
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
                competencia_lock=None,
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
