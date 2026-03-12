from __future__ import annotations

from datetime import date, datetime

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado
from apps.contratos.models import Ciclo, Contrato
from apps.esteira.models import EsteiraItem, Transicao
from apps.refinanciamento.models import Comprovante

from .models import Confirmacao


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
        elif pagamento == "processado":
            queryset = queryset.exclude(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
            )

        if competencia and pagamento != "pendente":
            queryset = queryset.filter(
                ciclos__data_inicio__year=competencia.year,
                ciclos__data_inicio__month=competencia.month,
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

        for papel, arquivo in [
            (Comprovante.Papel.ASSOCIADO, comprovante_associado),
            (Comprovante.Papel.AGENTE, comprovante_agente),
        ]:
            Comprovante.objects.update_or_create(
                contrato=contrato,
                refinanciamento=None,
                papel=papel,
                defaults={
                    "tipo": Comprovante.Tipo.PIX,
                    "arquivo": arquivo,
                    "nome_original": getattr(arquivo, "name", ""),
                    "enviado_por": user,
                },
            )

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

        ciclo = contrato.ciclos.order_by("numero").first()
        if ciclo and ciclo.status == Ciclo.Status.FUTURO:
            ciclo.status = Ciclo.Status.ABERTO
            ciclo.save(update_fields=["status", "updated_at"])

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
        return getattr(contrato.associado, "dados_bancarios", None)


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
