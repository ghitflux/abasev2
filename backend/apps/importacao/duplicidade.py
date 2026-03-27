from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.contratos.models import Contrato

from .manual_return_conflicts import pagamento_has_manual_context
from .models import ArquivoRetornoItem, DuplicidadeFinanceira, PagamentoMensalidade


@dataclass(frozen=True)
class DuplicidadeListPayload:
    rows: list[dict[str, object]]
    kpis: dict[str, object]


def _append_note(base: str, note: str) -> str:
    if not base:
        return note
    if note in base:
        return base
    return f"{base}\n{note}"


class DuplicidadeFinanceiraService:
    @staticmethod
    def _resolve_contract(associado_id: int | None):
        if not associado_id:
            return None
        return (
            Contrato.objects.filter(associado_id=associado_id)
            .order_by("-created_at", "-id")
            .first()
        )

    @classmethod
    def register_conflict(
        cls,
        *,
        item: ArquivoRetornoItem,
        pagamento: PagamentoMensalidade,
        motivo: str,
        observacao: str,
        competencia_manual: date | None = None,
    ) -> DuplicidadeFinanceira:
        associado = item.associado or pagamento.associado
        contrato = cls._resolve_contract(getattr(associado, "id", None))
        duplicidade, _created = DuplicidadeFinanceira.objects.update_or_create(
            arquivo_retorno_item=item,
            defaults={
                "pagamento_mensalidade": pagamento,
                "associado": associado,
                "contrato": contrato,
                "motivo": motivo,
                "status": DuplicidadeFinanceira.Status.ABERTA,
                "competencia_retorno": _parse_item_competencia(item),
                "competencia_manual": competencia_manual or pagamento.referencia_month,
                "valor_retorno": item.valor_descontado,
                "valor_manual": pagamento.recebido_manual or pagamento.valor,
                "observacao": observacao,
                "devolucao": None,
                "resolvido_por": None,
                "resolvido_em": None,
                "motivo_resolucao": "",
            },
        )
        item.processado = True
        item.resultado_processamento = ArquivoRetornoItem.ResultadoProcessamento.DUPLICIDADE
        item.observacao = observacao
        item.save(
            update_fields=[
                "processado",
                "resultado_processamento",
                "observacao",
                "updated_at",
            ]
        )
        return duplicidade

    @classmethod
    def detect_existing_conflict(
        cls,
        *,
        item: ArquivoRetornoItem,
        cpf_cnpj: str,
        competencia: date,
        valor: Decimal | None,
    ) -> tuple[DuplicidadeFinanceira | None, PagamentoMensalidade | None]:
        exact = (
            PagamentoMensalidade.objects.filter(
                cpf_cnpj=cpf_cnpj,
                referencia_month=competencia,
            )
            .order_by("-updated_at", "-created_at", "-id")
            .first()
        )
        if exact and pagamento_has_manual_context(exact):
            same_value = (
                valor is not None
                and exact.valor is not None
                and Decimal(str(exact.valor)) == Decimal(str(valor))
            )
            motivo = (
                DuplicidadeFinanceira.Motivo.BAIXA_MANUAL_DUPLICADA
                if same_value
                else DuplicidadeFinanceira.Motivo.DIVERGENCIA_VALOR
            )
            observacao = (
                "Competência já baixada manualmente e reenviada no arquivo retorno."
                if same_value
                else "Competência já baixada manualmente com divergência de valor no arquivo retorno."
            )
            return cls.register_conflict(
                item=item,
                pagamento=exact,
                motivo=motivo,
                observacao=observacao,
                competencia_manual=exact.referencia_month,
            ), exact

        wrong_month_qs = PagamentoMensalidade.objects.filter(
            cpf_cnpj=cpf_cnpj,
            manual_status=PagamentoMensalidade.ManualStatus.PAGO,
        ).exclude(referencia_month=competencia)
        if valor is not None:
            wrong_month_qs = wrong_month_qs.filter(
                Q(recebido_manual=valor) | Q(valor=valor)
            )
        wrong_month = wrong_month_qs.order_by("-manual_paid_at", "-updated_at", "-id").first()
        if wrong_month is not None and pagamento_has_manual_context(wrong_month):
            return cls.register_conflict(
                item=item,
                pagamento=wrong_month,
                motivo=DuplicidadeFinanceira.Motivo.BAIXA_MANUAL_MES_ERRADO,
                observacao=(
                    "Foi identificada baixa manual em competência diferente da competência recebida no retorno."
                ),
                competencia_manual=wrong_month.referencia_month,
            ), wrong_month

        return None, None

    @staticmethod
    def _queryset():
        return (
            DuplicidadeFinanceira.objects.select_related(
                "arquivo_retorno_item",
                "arquivo_retorno_item__arquivo_retorno",
                "associado",
                "associado__agente_responsavel",
                "contrato",
                "devolucao",
                "resolvido_por",
            )
            .order_by("-created_at", "-id")
        )

    @classmethod
    def _serialize(cls, item: DuplicidadeFinanceira) -> dict[str, object]:
        associado = item.associado
        agente = getattr(associado, "agente_responsavel", None)
        return {
            "id": item.id,
            "arquivo_retorno_item_id": item.arquivo_retorno_item_id,
            "arquivo_retorno_id": item.arquivo_retorno_item.arquivo_retorno_id,
            "arquivo_nome": item.arquivo_retorno_item.arquivo_retorno.arquivo_nome,
            "linha_numero": item.arquivo_retorno_item.linha_numero,
            "associado_id": getattr(associado, "id", None),
            "nome": associado.nome_completo if associado else item.arquivo_retorno_item.nome_servidor,
            "cpf_cnpj": item.arquivo_retorno_item.cpf_cnpj,
            "matricula": (
                associado.matricula_orgao or associado.matricula
                if associado
                else item.arquivo_retorno_item.matricula_servidor
            ),
            "agente_nome": agente.full_name if agente else "",
            "contrato_id": item.contrato_id,
            "contrato_codigo": item.contrato.codigo if item.contrato_id else "",
            "motivo": item.motivo,
            "status": item.status,
            "competencia_retorno": item.competencia_retorno,
            "competencia_manual": item.competencia_manual,
            "valor_retorno": item.valor_retorno,
            "valor_manual": item.valor_manual,
            "observacao": item.observacao,
            "devolucao_id": item.devolucao_id,
            "resolvido_em": item.resolvido_em,
            "resolvido_por": getattr(item.resolvido_por, "full_name", ""),
            "motivo_resolucao": item.motivo_resolucao,
            "created_at": item.created_at,
        }

    @classmethod
    def _build_kpis(cls, rows: list[dict[str, object]]) -> dict[str, object]:
        return {
            "total": len(rows),
            "abertas": sum(1 for row in rows if row["status"] == DuplicidadeFinanceira.Status.ABERTA),
            "em_tratamento": sum(
                1 for row in rows if row["status"] == DuplicidadeFinanceira.Status.EM_TRATAMENTO
            ),
            "resolvidas": sum(
                1 for row in rows if row["status"] == DuplicidadeFinanceira.Status.RESOLVIDA
            ),
            "descartadas": sum(
                1 for row in rows if row["status"] == DuplicidadeFinanceira.Status.DESCARTADA
            ),
        }

    @classmethod
    def listar(
        cls,
        *,
        search: str | None = None,
        status: str | None = None,
        motivo: str | None = None,
        competencia: date | None = None,
        agente: str | None = None,
        arquivo_retorno_id: int | None = None,
    ) -> DuplicidadeListPayload:
        queryset = cls._queryset()
        if search:
            queryset = queryset.filter(
                Q(arquivo_retorno_item__nome_servidor__icontains=search)
                | Q(arquivo_retorno_item__cpf_cnpj__icontains=search)
                | Q(associado__nome_completo__icontains=search)
                | Q(contrato__codigo__icontains=search)
            )
        if status in {choice[0] for choice in DuplicidadeFinanceira.Status.choices}:
            queryset = queryset.filter(status=status)
        if motivo in {choice[0] for choice in DuplicidadeFinanceira.Motivo.choices}:
            queryset = queryset.filter(motivo=motivo)
        if competencia:
            queryset = queryset.filter(
                competencia_retorno__year=competencia.year,
                competencia_retorno__month=competencia.month,
            )
        if agente:
            queryset = queryset.filter(
                Q(associado__agente_responsavel__first_name__icontains=agente)
                | Q(associado__agente_responsavel__last_name__icontains=agente)
                | Q(associado__agente_responsavel__email__icontains=agente)
            )
        if arquivo_retorno_id:
            queryset = queryset.filter(
                arquivo_retorno_item__arquivo_retorno_id=arquivo_retorno_id
            )

        rows = [cls._serialize(item) for item in queryset]
        return DuplicidadeListPayload(rows=rows, kpis=cls._build_kpis(rows))

    @classmethod
    @transaction.atomic
    def descartar(cls, duplicidade_id: int, *, motivo: str, user) -> DuplicidadeFinanceira:
        duplicidade = cls._queryset().select_for_update().filter(pk=duplicidade_id).first()
        if duplicidade is None:
            raise ValidationError("Caso de duplicidade não encontrado.")
        duplicidade.status = DuplicidadeFinanceira.Status.DESCARTADA
        duplicidade.resolvido_por = user
        duplicidade.resolvido_em = timezone.now()
        duplicidade.motivo_resolucao = motivo
        duplicidade.save(
            update_fields=[
                "status",
                "resolvido_por",
                "resolvido_em",
                "motivo_resolucao",
                "updated_at",
            ]
        )
        return duplicidade

    @classmethod
    @transaction.atomic
    def resolver_com_devolucao(
        cls,
        duplicidade_id: int,
        *,
        data_devolucao: date,
        valor: Decimal,
        motivo: str,
        comprovantes: list,
        user,
    ) -> DuplicidadeFinanceira:
        duplicidade = cls._queryset().select_for_update().filter(pk=duplicidade_id).first()
        if duplicidade is None:
            raise ValidationError("Caso de duplicidade não encontrado.")
        if duplicidade.contrato_id is None:
            raise ValidationError("A duplicidade não possui contrato vinculado para devolução.")

        from apps.tesouraria.devolucao import DevolucaoAssociadoService
        from apps.tesouraria.models import DevolucaoAssociado

        devolucao = DevolucaoAssociadoService.registrar(
            duplicidade.contrato_id,
            tipo=DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO,
            data_devolucao=data_devolucao,
            quantidade_parcelas=1,
            valor=valor,
            motivo=motivo,
            comprovantes=comprovantes,
            competencia_referencia=duplicidade.competencia_retorno,
            user=user,
        )
        duplicidade.status = DuplicidadeFinanceira.Status.RESOLVIDA
        duplicidade.devolucao = devolucao
        duplicidade.resolvido_por = user
        duplicidade.resolvido_em = timezone.now()
        duplicidade.motivo_resolucao = motivo
        duplicidade.save(
            update_fields=[
                "status",
                "devolucao",
                "resolvido_por",
                "resolvido_em",
                "motivo_resolucao",
                "updated_at",
            ]
        )
        return duplicidade


def _parse_item_competencia(item: ArquivoRetornoItem) -> date:
    return datetime.strptime(item.competencia, "%m/%Y").date().replace(day=1)
