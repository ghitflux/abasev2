from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado
from apps.contratos.competencia import propagate_competencia_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao
from apps.refinanciamento.models import Comprovante

from .models import BaixaManual, Confirmacao, Pagamento


def parse_competencia(value: str | None) -> date:
    if not value:
        today = timezone.localdate()
        return today.replace(day=1)
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc
    return parsed.replace(day=1)


class TesourariaService:
    @staticmethod
    def listar_contratos_pendentes(
        competencia: date | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        search: str | None = None,
        pagamento: str | None = None,
    ):
        queryset = (
            Contrato.objects.select_related(
                "associado",
                "associado__dados_bancarios",
                "associado__esteira_item",
                "agente",
            )
            .prefetch_related(Prefetch("comprovantes__enviado_por"), Prefetch("ciclos"))
            .filter(
                Q(associado__esteira_item__etapa_atual__in=[
                    EsteiraItem.Etapa.TESOURARIA,
                    EsteiraItem.Etapa.CONCLUIDO,
                ])
                | Q(status=Contrato.Status.CANCELADO)
            )
            .distinct()
            .order_by("-created_at")
        )

        if pagamento == "pendente":
            queryset = queryset.filter(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
            )
        elif pagamento == "concluido":
            queryset = queryset.filter(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.CONCLUIDO
            ).exclude(status=Contrato.Status.CANCELADO)
        elif pagamento == "cancelado":
            queryset = queryset.filter(status=Contrato.Status.CANCELADO)
        elif pagamento == "processado":
            queryset = queryset.exclude(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
            )

        if competencia:
            if pagamento == "concluido":
                queryset = queryset.filter(
                    auxilio_liberado_em__year=competencia.year,
                    auxilio_liberado_em__month=competencia.month,
                )
            elif pagamento == "cancelado":
                queryset = queryset.filter(
                    updated_at__year=competencia.year,
                    updated_at__month=competencia.month,
                )
            elif pagamento == "processado":
                queryset = queryset.filter(
                    Q(
                        auxilio_liberado_em__year=competencia.year,
                        auxilio_liberado_em__month=competencia.month,
                    )
                    | Q(
                        status=Contrato.Status.CANCELADO,
                        updated_at__year=competencia.year,
                        updated_at__month=competencia.month,
                    )
                )

        if data_inicio:
            queryset = queryset.filter(data_contrato__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data_contrato__lte=data_fim)

        if search:
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(codigo__icontains=search)
            )

        return queryset

    @staticmethod
    def _get_contrato(contrato_id: int) -> Contrato:
        try:
            return (
                Contrato.objects.select_related(
                    "associado",
                    "associado__dados_bancarios",
                    "associado__esteira_item",
                    "agente",
                )
                .prefetch_related("ciclos__parcelas", "comprovantes")
                .get(pk=contrato_id)
            )
        except Contrato.DoesNotExist as exc:
            raise ValidationError("Contrato não encontrado.") from exc

    @staticmethod
    @transaction.atomic
    def efetivar_contrato(contrato_id, comprovante_associado, comprovante_agente, user):
        contrato = TesourariaService._get_contrato(int(contrato_id))
        esteira_item = getattr(contrato.associado, "esteira_item", None)
        if not esteira_item or esteira_item.etapa_atual != EsteiraItem.Etapa.TESOURARIA:
            raise ValidationError("Contrato não está disponível para efetivação na tesouraria.")
        if not comprovante_associado or not comprovante_agente:
            raise ValidationError("Os comprovantes do associado e do agente são obrigatórios.")

        contrato.status = Contrato.Status.ATIVO
        contrato.auxilio_liberado_em = timezone.localdate()
        if not contrato.data_aprovacao:
            contrato.data_aprovacao = timezone.localdate()
        contrato.save(
            update_fields=[
                "status",
                "auxilio_liberado_em",
                "data_aprovacao",
                "updated_at",
            ]
        )

        contrato.associado.status = Associado.Status.ATIVO
        contrato.associado.save(update_fields=["status", "updated_at"])

        pagamento = Pagamento.objects.create(
            cadastro=contrato.associado,
            created_by=user,
            contrato_codigo=contrato.codigo,
            contrato_valor_antecipacao=contrato.valor_liquido or contrato.valor_total_antecipacao,
            contrato_margem_disponivel=contrato.margem_disponivel,
            cpf_cnpj=contrato.associado.cpf_cnpj,
            full_name=contrato.associado.nome_completo,
            agente_responsavel=contrato.agente.full_name if contrato.agente else "",
            origem=Pagamento.Origem.OPERACIONAL,
            status=Pagamento.Status.PAGO,
            valor_pago=contrato.valor_liquido or contrato.valor_total_antecipacao,
            paid_at=timezone.now(),
            forma_pagamento="pix",
            comprovante_associado_path=getattr(comprovante_associado, "name", ""),
            comprovante_agente_path=getattr(comprovante_agente, "name", ""),
            notes="Efetivação inicial do contrato pela tesouraria.",
        )

        rebuild_contract_cycle_state(contrato, execute=True)
        contrato.refresh_from_db()
        ciclo = contrato.ciclos.order_by("numero").first()

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
                contrato=contrato,
                ciclo=ciclo,
                refinanciamento=None,
                papel=papel,
                tipo=tipo,
                origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
                arquivo=arquivo,
                nome_original=getattr(arquivo, "name", ""),
                enviado_por=user,
                data_pagamento=pagamento.paid_at,
                agente_snapshot=contrato.agente.full_name if contrato.agente else "",
            )

        de_situacao = esteira_item.status
        esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
        esteira_item.status = EsteiraItem.Situacao.APROVADO
        esteira_item.tesoureiro_responsavel = user
        esteira_item.concluido_em = timezone.now()
        esteira_item.save()

        Transicao.objects.create(
            esteira_item=esteira_item,
            acao="efetivar",
            de_status=EsteiraItem.Etapa.TESOURARIA,
            para_status=EsteiraItem.Etapa.CONCLUIDO,
            de_situacao=de_situacao,
            para_situacao=EsteiraItem.Situacao.APROVADO,
            realizado_por=user,
            observacao="Contrato efetivado pela tesouraria.",
        )
        return contrato

    @staticmethod
    @transaction.atomic
    def congelar_contrato(contrato_id, motivo, user):
        contrato = TesourariaService._get_contrato(int(contrato_id))
        esteira_item = getattr(contrato.associado, "esteira_item", None)
        if not esteira_item or esteira_item.etapa_atual != EsteiraItem.Etapa.TESOURARIA:
            raise ValidationError("Contrato não está na etapa de tesouraria.")

        de_situacao = esteira_item.status
        esteira_item.status = EsteiraItem.Situacao.PENDENCIADO
        esteira_item.tesoureiro_responsavel = user
        esteira_item.observacao = motivo
        esteira_item.save()

        Transicao.objects.create(
            esteira_item=esteira_item,
            acao="congelar",
            de_status=EsteiraItem.Etapa.TESOURARIA,
            para_status=EsteiraItem.Etapa.TESOURARIA,
            de_situacao=de_situacao,
            para_situacao=EsteiraItem.Situacao.PENDENCIADO,
            realizado_por=user,
            observacao=motivo,
        )
        return contrato

    @staticmethod
    def obter_dados_bancarios(contrato_id):
        contrato = TesourariaService._get_contrato(int(contrato_id))
        return contrato.associado.build_dados_bancarios_payload()


class ConfirmacaoService:
    @staticmethod
    def _garantir_registros(contrato: Contrato, competencia: date) -> tuple[Confirmacao, Confirmacao]:
        ligacao, _ = Confirmacao.objects.get_or_create(
            contrato=contrato,
            competencia=competencia,
            tipo=Confirmacao.Tipo.LIGACAO,
        )
        averbacao, _ = Confirmacao.objects.get_or_create(
            contrato=contrato,
            competencia=competencia,
            tipo=Confirmacao.Tipo.AVERBACAO,
        )
        return ligacao, averbacao

    @staticmethod
    def _serialize_pair(ligacao: Confirmacao, averbacao: Confirmacao) -> dict[str, object]:
        contrato = ligacao.contrato
        return {
            "id": ligacao.id,
            "contrato_id": contrato.id,
            "associado_id": contrato.associado_id,
            "nome": contrato.associado.nome_completo,
            "cpf_cnpj": contrato.associado.cpf_cnpj,
            "agente_nome": contrato.agente.full_name if contrato.agente else "",
            "competencia": ligacao.competencia,
            "link_chamada": ligacao.link_chamada,
            "ligacao_confirmada": ligacao.status == Confirmacao.Status.CONFIRMADO,
            "averbacao_confirmada": averbacao.status == Confirmacao.Status.CONFIRMADO,
            "status_visual": (
                "averbacao_confirmada"
                if averbacao.status == Confirmacao.Status.CONFIRMADO
                else "ligacao_recebida"
                if ligacao.status == Confirmacao.Status.CONFIRMADO
                else "sem_link"
            ),
        }

    @staticmethod
    def _get_ligacao(confirmacao_id: int) -> Confirmacao:
        try:
            confirmacao = Confirmacao.objects.select_related(
                "contrato",
                "contrato__associado",
                "contrato__agente",
            ).get(pk=confirmacao_id, tipo=Confirmacao.Tipo.LIGACAO)
        except Confirmacao.DoesNotExist as exc:
            raise ValidationError("Confirmação de ligação não encontrada.") from exc
        return confirmacao

    @staticmethod
    def listar_por_competencia(competencia: date) -> list[dict[str, object]]:
        contratos = (
            Contrato.objects.select_related("associado", "agente")
            .filter(status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO])
            .order_by("associado__nome_completo")
        )

        payload: list[dict[str, object]] = []
        for contrato in contratos:
            ligacao, averbacao = ConfirmacaoService._garantir_registros(
                contrato, competencia
            )
            payload.append(ConfirmacaoService._serialize_pair(ligacao, averbacao))
        return payload

    @staticmethod
    def obter(confirmacao_id: int) -> dict[str, object]:
        ligacao = ConfirmacaoService._get_ligacao(confirmacao_id)
        _, averbacao = ConfirmacaoService._garantir_registros(
            ligacao.contrato, ligacao.competencia
        )
        return ConfirmacaoService._serialize_pair(ligacao, averbacao)

    @staticmethod
    @transaction.atomic
    def salvar_link_chamada(confirmacao_id, link):
        ligacao = ConfirmacaoService._get_ligacao(int(confirmacao_id))
        ligacao.link_chamada = link
        ligacao.save(update_fields=["link_chamada", "updated_at"])
        return ConfirmacaoService.obter(ligacao.id)

    @staticmethod
    @transaction.atomic
    def confirmar_ligacao(confirmacao_id, user):
        ligacao = ConfirmacaoService._get_ligacao(int(confirmacao_id))
        if not ligacao.link_chamada:
            raise ValidationError("Salve o link da chamada antes de confirmar a ligação.")
        ligacao.confirmar(user)
        return ConfirmacaoService.obter(ligacao.id)

    @staticmethod
    @transaction.atomic
    def confirmar_averbacao(confirmacao_id, user):
        ligacao = ConfirmacaoService._get_ligacao(int(confirmacao_id))
        if ligacao.status != Confirmacao.Status.CONFIRMADO:
            raise ValidationError("Confirme a ligação antes de confirmar a averbação.")
        _, averbacao = ConfirmacaoService._garantir_registros(
            ligacao.contrato, ligacao.competencia
        )
        averbacao.confirmar(user)
        return ConfirmacaoService.obter(ligacao.id)


class BaixaManualService:
    @staticmethod
    def listar_parcelas_pendentes(
        search: str | None = None,
        status_filter: str | None = None,
        competencia: date | None = None,
    ):
        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)

        queryset = (
            Parcela.objects.select_related(
                "ciclo__contrato__associado",
                "ciclo__contrato__agente",
            )
            .filter(
                status__in=[
                    Parcela.Status.EM_ABERTO,
                    Parcela.Status.EM_PREVISAO,
                    Parcela.Status.NAO_DESCONTADO,
                ],
                referencia_mes__lt=mes_atual,
            )
            .order_by("-referencia_mes", "ciclo__contrato__associado__nome_completo")
        )

        if competencia:
            queryset = queryset.filter(
                referencia_mes__year=competencia.year,
                referencia_mes__month=competencia.month,
            )

        if status_filter in {"em_aberto", "nao_descontado"}:
            queryset = queryset.filter(status=status_filter)

        if search:
            queryset = queryset.filter(
                Q(ciclo__contrato__associado__nome_completo__icontains=search)
                | Q(ciclo__contrato__associado__cpf_cnpj__icontains=search)
                | Q(ciclo__contrato__associado__matricula__icontains=search)
                | Q(ciclo__contrato__codigo__icontains=search)
            )

        return queryset

    @staticmethod
    def kpis() -> dict:
        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)

        base = Parcela.objects.filter(
            status__in=[Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO],
            referencia_mes__lt=mes_atual,
        )
        totals = base.aggregate(
            total=Count("id"),
            em_aberto=Count("id", filter=Q(status=Parcela.Status.EM_ABERTO)),
            nao_descontado=Count("id", filter=Q(status=Parcela.Status.NAO_DESCONTADO)),
            valor_total=Sum("valor"),
        )

        baixas_mes = BaixaManual.objects.filter(
            created_at__year=hoje.year,
            created_at__month=hoje.month,
        ).count()

        return {
            "total_pendentes": totals["total"] or 0,
            "em_aberto": totals["em_aberto"] or 0,
            "nao_descontado": totals["nao_descontado"] or 0,
            "valor_total_pendente": str(totals["valor_total"] or Decimal("0")),
            "baixas_realizadas_mes": baixas_mes,
        }

    @staticmethod
    @transaction.atomic
    def dar_baixa(parcela_id: int, comprovante, valor_pago, observacao: str, user):
        try:
            parcela = Parcela.objects.select_related(
                "ciclo__contrato__associado",
            ).get(pk=parcela_id)
        except Parcela.DoesNotExist as exc:
            raise ValidationError("Parcela não encontrada.") from exc

        if parcela.status not in {
            Parcela.Status.EM_ABERTO,
            Parcela.Status.EM_PREVISAO,
            Parcela.Status.NAO_DESCONTADO,
        }:
            raise ValidationError(
                "Apenas parcelas em aberto, não descontadas ou em previsão podem receber baixa manual."
            )

        if BaixaManual.objects.filter(parcela=parcela).exists():
            raise ValidationError("Esta parcela já possui uma baixa manual registrada.")

        parcela.status = Parcela.Status.DESCONTADO
        parcela.data_pagamento = timezone.localdate()
        if observacao:
            parcela.observacao = observacao
        parcela.save(update_fields=["status", "data_pagamento", "observacao", "updated_at"])
        propagate_competencia_status(parcela)
        rebuild_contract_cycle_state(parcela.ciclo.contrato, execute=True)

        return BaixaManual.objects.create(
            parcela=parcela,
            realizado_por=user,
            comprovante=comprovante,
            nome_comprovante=getattr(comprovante, "name", ""),
            observacao=observacao or "",
            valor_pago=valor_pago,
            data_baixa=timezone.localdate(),
        )
