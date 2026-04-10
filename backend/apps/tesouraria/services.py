from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from calendar import monthrange

from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Count, DecimalField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.contratos.canonicalization import operational_contracts_queryset
from apps.contratos.competencia import propagate_competencia_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Transicao
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante, Refinanciamento

from .models import BaixaManual, Confirmacao, DevolucaoAssociado, Pagamento


def parse_competencia(value: str | None) -> date:
    if not value:
        today = timezone.localdate()
        return today.replace(day=1)
    try:
        parsed = datetime.strptime(value, "%Y-%m").date()
    except ValueError as exc:
        raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc
    return parsed.replace(day=1)


def shift_month(base_date: date, offset: int) -> date:
    month_index = base_date.month - 1 + offset
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)


class TesourariaService:
    @staticmethod
    def listar_usuarios_filtro_agente() -> list[dict[str, object]]:
        linked_queryset = Contrato.objects.filter(
            Q(
                associado__esteira_item__etapa_atual__in=[
                    EsteiraItem.Etapa.TESOURARIA,
                    EsteiraItem.Etapa.CONCLUIDO,
                ]
            )
            | Q(status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO])
        )
        linked_user_ids = {
            user_id
            for user_id in (
                list(linked_queryset.values_list("agente_id", flat=True))
                + list(
                    linked_queryset.values_list(
                        "associado__agente_responsavel_id",
                        flat=True,
                    )
                )
            )
            if user_id
        }

        users = (
            User.objects.filter(
                Q(
                    is_active=True,
                    user_roles__deleted_at__isnull=True,
                    user_roles__role__codigo="AGENTE",
                )
                | Q(id__in=linked_user_ids)
            )
            .distinct()
            .order_by("first_name", "last_name", "email")
        )
        return [
            {
                "id": user.id,
                "full_name": user.full_name or user.email,
                "email": user.email,
                "primary_role": user.primary_role,
            }
            for user in users
        ]

    @staticmethod
    def listar_contratos_pendentes(
        competencia: date | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        search: str | None = None,
        pagamento: str | None = None,
        agente: str | None = None,
        status_contrato: str | None = None,
        situacao_esteira: str | None = None,
        ordering: str | None = None,
    ):
        ordering_map = {
            "created_at": "created_at",
            "-created_at": "-created_at",
            "data_contrato": "data_contrato",
            "-data_contrato": "-data_contrato",
            "codigo": "codigo",
            "-codigo": "-codigo",
        }
        has_explicit_period = bool(data_inicio or data_fim)
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
                | Q(status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO])
            )
            .distinct()
            .order_by(ordering_map.get(ordering or "", "-created_at"))
        )
        queryset = operational_contracts_queryset(queryset)

        if pagamento == "pendente":
            queryset = queryset.filter(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
            )
        elif pagamento == "concluido":
            queryset = queryset.filter(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.CONCLUIDO
            ).exclude(status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO])
        elif pagamento == "liquidado":
            queryset = queryset.filter(status=Contrato.Status.ENCERRADO)
        elif pagamento == "cancelado":
            queryset = queryset.filter(status=Contrato.Status.CANCELADO)
        elif pagamento == "processado":
            queryset = queryset.exclude(
                associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
            )

        if competencia and not has_explicit_period:
            if pagamento == "concluido":
                queryset = queryset.filter(
                    auxilio_liberado_em__year=competencia.year,
                    auxilio_liberado_em__month=competencia.month,
                )
            elif pagamento == "liquidado":
                queryset = queryset.filter(
                    updated_at__year=competencia.year,
                    updated_at__month=competencia.month,
                )
            elif pagamento == "cancelado":
                queryset = queryset.filter(
                    cancelado_em__year=competencia.year,
                    cancelado_em__month=competencia.month,
                )
            elif pagamento == "processado":
                queryset = queryset.filter(
                    Q(
                        auxilio_liberado_em__year=competencia.year,
                        auxilio_liberado_em__month=competencia.month,
                    )
                    | Q(
                        status__in=[Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO],
                        updated_at__year=competencia.year,
                        updated_at__month=competencia.month,
                    )
                )

        if data_inicio:
            queryset = queryset.filter(created_at__date__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(created_at__date__lte=data_fim)

        if search:
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(codigo__icontains=search)
                | Q(associado__matricula__icontains=search)
            )

        if agente:
            agente_term = agente.strip()
            if agente_term:
                if agente_term.isdigit():
                    agente_id = int(agente_term)
                    queryset = queryset.filter(
                        Q(agente_id=agente_id)
                        | Q(associado__agente_responsavel_id=agente_id)
                    )
                else:
                    queryset = queryset.filter(
                        Q(agente__first_name__icontains=agente_term)
                        | Q(agente__last_name__icontains=agente_term)
                        | Q(agente__email__icontains=agente_term)
                        | Q(
                            associado__agente_responsavel__first_name__icontains=agente_term
                        )
                        | Q(
                            associado__agente_responsavel__last_name__icontains=agente_term
                        )
                        | Q(
                            associado__agente_responsavel__email__icontains=agente_term
                        )
                    )

        if status_contrato == "congelado":
            queryset = queryset.filter(
                associado__esteira_item__status=EsteiraItem.Situacao.PENDENCIADO
            )
        elif status_contrato and status_contrato in {
            choice[0] for choice in Contrato.Status.choices
        }:
            queryset = queryset.filter(status=status_contrato)

        if situacao_esteira and situacao_esteira in {
            choice[0] for choice in EsteiraItem.Situacao.choices
        }:
            queryset = queryset.filter(associado__esteira_item__status=situacao_esteira)

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
            referencias_externas={
                "payment_kind": "contrato_inicial",
                "contrato_id": contrato.id,
            },
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

    @staticmethod
    @transaction.atomic
    def substituir_comprovante(contrato_id, *, papel: str, arquivo, user):
        contrato = TesourariaService._get_contrato(int(contrato_id))
        comprovante = (
            contrato.comprovantes.filter(
                refinanciamento__isnull=True,
                origem=Comprovante.Origem.EFETIVACAO_CONTRATO,
                papel=papel,
            )
            .order_by("-created_at")
            .first()
        )
        if comprovante is None:
            raise ValidationError("Comprovante não encontrado para substituição.")

        comprovante.arquivo = arquivo
        comprovante.nome_original = getattr(arquivo, "name", "")
        comprovante.mime = getattr(arquivo, "content_type", "") or ""
        comprovante.size_bytes = getattr(arquivo, "size", None)
        comprovante.arquivo_referencia_path = ""
        comprovante.enviado_por = user
        if comprovante.data_pagamento is None:
            comprovante.data_pagamento = timezone.now()
        comprovante.save(
            update_fields=[
                "arquivo",
                "nome_original",
                "mime",
                "size_bytes",
                "arquivo_referencia_path",
                "enviado_por",
                "data_pagamento",
                "updated_at",
            ]
        )
        return contrato

    @staticmethod
    @transaction.atomic
    def cancelar_contrato(contrato_id: int, tipo: str, motivo: str, user) -> Contrato:
        contrato = TesourariaService._get_contrato(int(contrato_id))
        if contrato.status == Contrato.Status.ATIVO:
            raise ValidationError("Somente contratos ainda não ativos podem ser cancelados.")
        if contrato.status == Contrato.Status.ENCERRADO:
            raise ValidationError("Contratos liquidados não podem ser cancelados.")
        if contrato.status == Contrato.Status.CANCELADO:
            raise ValidationError("Este contrato já foi cancelado.")

        now = timezone.now()
        contrato.status = Contrato.Status.CANCELADO
        contrato.cancelamento_tipo = tipo
        contrato.cancelamento_motivo = motivo.strip()
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

        esteira_item = getattr(contrato.associado, "esteira_item", None)
        if esteira_item:
            de_etapa = esteira_item.etapa_atual
            de_situacao = esteira_item.status
            esteira_item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
            esteira_item.status = EsteiraItem.Situacao.REJEITADO
            esteira_item.observacao = contrato.cancelamento_motivo
            esteira_item.tesoureiro_responsavel = user
            esteira_item.concluido_em = now
            esteira_item.save(
                update_fields=[
                    "etapa_atual",
                    "status",
                    "observacao",
                    "tesoureiro_responsavel",
                    "concluido_em",
                    "updated_at",
                ]
            )
            Transicao.objects.create(
                esteira_item=esteira_item,
                acao="cancelar_contrato",
                de_status=de_etapa,
                para_status=EsteiraItem.Etapa.CONCLUIDO,
                de_situacao=de_situacao,
                para_situacao=EsteiraItem.Situacao.REJEITADO,
                realizado_por=user,
                observacao=contrato.cancelamento_motivo,
            )

        return contrato


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
    def _apply_parcela_search(queryset, search: str | None):
        if not search:
            return queryset
        return queryset.filter(
            Q(ciclo__contrato__associado__nome_completo__icontains=search)
            | Q(ciclo__contrato__associado__cpf_cnpj__icontains=search)
            | Q(ciclo__contrato__associado__matricula__icontains=search)
            | Q(ciclo__contrato__associado__matricula_orgao__icontains=search)
            | Q(ciclo__contrato__codigo__icontains=search)
        )

    @staticmethod
    def _apply_baixa_search(queryset, search: str | None):
        if not search:
            return queryset
        return queryset.filter(
            Q(parcela__ciclo__contrato__associado__nome_completo__icontains=search)
            | Q(parcela__ciclo__contrato__associado__cpf_cnpj__icontains=search)
            | Q(parcela__ciclo__contrato__associado__matricula__icontains=search)
            | Q(
                parcela__ciclo__contrato__associado__matricula_orgao__icontains=search
            )
            | Q(parcela__ciclo__contrato__codigo__icontains=search)
        )

    @staticmethod
    def _apply_parcela_agent_filter(queryset, agente: str | None):
        agente_term = (agente or "").strip()
        if not agente_term:
            return queryset
        if agente_term.isdigit():
            agente_id = int(agente_term)
            return queryset.filter(
                Q(ciclo__contrato__agente_id=agente_id)
                | Q(ciclo__contrato__associado__agente_responsavel_id=agente_id)
            )
        return queryset.filter(
            Q(ciclo__contrato__agente__first_name__icontains=agente_term)
            | Q(ciclo__contrato__agente__last_name__icontains=agente_term)
            | Q(ciclo__contrato__agente__email__icontains=agente_term)
            | Q(
                ciclo__contrato__associado__agente_responsavel__first_name__icontains=agente_term
            )
            | Q(
                ciclo__contrato__associado__agente_responsavel__last_name__icontains=agente_term
            )
            | Q(
                ciclo__contrato__associado__agente_responsavel__email__icontains=agente_term
            )
        )

    @staticmethod
    def _apply_baixa_agent_filter(queryset, agente: str | None):
        agente_term = (agente or "").strip()
        if not agente_term:
            return queryset
        if agente_term.isdigit():
            agente_id = int(agente_term)
            return queryset.filter(
                Q(parcela__ciclo__contrato__agente_id=agente_id)
                | Q(
                    parcela__ciclo__contrato__associado__agente_responsavel_id=agente_id
                )
            )
        return queryset.filter(
            Q(parcela__ciclo__contrato__agente__first_name__icontains=agente_term)
            | Q(parcela__ciclo__contrato__agente__last_name__icontains=agente_term)
            | Q(parcela__ciclo__contrato__agente__email__icontains=agente_term)
            | Q(
                parcela__ciclo__contrato__associado__agente_responsavel__first_name__icontains=agente_term
            )
            | Q(
                parcela__ciclo__contrato__associado__agente_responsavel__last_name__icontains=agente_term
            )
            | Q(
                parcela__ciclo__contrato__associado__agente_responsavel__email__icontains=agente_term
            )
        )

    @staticmethod
    def _parse_item_competencia(value: str | None) -> date | None:
        if not value:
            return None

        normalized = value.strip()
        for pattern in ("%m/%Y", "%Y-%m"):
            try:
                return datetime.strptime(normalized, pattern).date().replace(day=1)
            except ValueError:
                continue
        return None

    @classmethod
    def _latest_return_file_ids(
        cls,
        *,
        competencia: date | None = None,
    ) -> list[int]:
        base_queryset = ArquivoRetorno.objects.filter(status="concluido")
        if competencia:
            latest = (
                base_queryset.filter(competencia=competencia)
                .order_by("-processado_em", "-created_at", "-id")
                .first()
            )
            return [latest.id] if latest else []

        file_ids_by_month: dict[date, int] = {}
        for arquivo in base_queryset.order_by("-competencia", "-processado_em", "-created_at", "-id"):
            if arquivo.competencia not in file_ids_by_month:
                file_ids_by_month[arquivo.competencia] = arquivo.id
        return list(file_ids_by_month.values())

    @staticmethod
    def _build_pending_row_from_parcela(
        parcela: Parcela,
        *,
        source: str = "parcela",
        arquivo_retorno_item_id: int | None = None,
    ) -> dict[str, object]:
        contrato = parcela.ciclo.contrato
        associado = contrato.associado
        agente = contrato.agente or associado.agente_responsavel
        return {
            "id": parcela.id,
            "parcela_id": parcela.id,
            "associado_id": associado.id,
            "nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "",
            "agente_nome": agente.full_name if agente else "",
            "contrato_id": contrato.id,
            "contrato_codigo": contrato.codigo,
            "referencia_mes": parcela.referencia_mes,
            "valor": parcela.valor,
            "status": parcela.status,
            "data_vencimento": parcela.data_vencimento,
            "observacao": parcela.observacao,
            "data_baixa": None,
            "valor_pago": None,
            "realizado_por_nome": "",
            "nome_comprovante": "",
            "origem": source,
            "arquivo_retorno_item_id": arquivo_retorno_item_id,
            "pode_dar_baixa": True,
            "_agente_id": agente.id if agente else None,
            "_sort_nome": associado.nome_completo or "",
            "_sort_referencia": parcela.referencia_mes,
        }

    @classmethod
    def _build_pending_row_from_return_item(
        cls,
        item: ArquivoRetornoItem,
    ) -> dict[str, object] | None:
        referencia = cls._parse_item_competencia(item.competencia)
        if referencia is None:
            return None

        parcela = item.parcela
        if parcela and parcela.status not in {
            Parcela.Status.EM_ABERTO,
            Parcela.Status.NAO_DESCONTADO,
        }:
            return None

        associado = item.associado or getattr(parcela, "associado", None)
        if associado is None:
            return None

        if parcela is None and associado.status == Associado.Status.INATIVO:
            return None

        contrato = getattr(getattr(parcela, "ciclo", None), "contrato", None)
        agente = None
        if contrato and contrato.agente:
            agente = contrato.agente
        elif associado.agente_responsavel:
            agente = associado.agente_responsavel

        return {
            "id": -item.id,
            "parcela_id": item.parcela_id,
            "associado_id": associado.id,
            "nome": associado.nome_completo or item.nome_servidor,
            "cpf_cnpj": associado.cpf_cnpj or item.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or item.matricula_servidor,
            "agente_nome": agente.full_name if agente else "",
            "contrato_id": contrato.id if contrato else None,
            "contrato_codigo": contrato.codigo if contrato else "",
            "referencia_mes": referencia,
            "valor": item.valor_descontado,
            "status": Parcela.Status.NAO_DESCONTADO,
            "data_vencimento": getattr(parcela, "data_vencimento", None),
            "observacao": item.observacao or item.motivo_rejeicao or "",
            "data_baixa": None,
            "valor_pago": None,
            "realizado_por_nome": "",
            "nome_comprovante": "",
            "origem": "arquivo_retorno",
            "arquivo_retorno_item_id": item.id,
            "pode_dar_baixa": bool(item.parcela_id),
            "_agente_id": agente.id if agente else None,
            "_sort_nome": associado.nome_completo or item.nome_servidor or "",
            "_sort_referencia": referencia,
        }

    @staticmethod
    def _pending_row_matches_search(row: dict[str, object], search: str | None) -> bool:
        search_term = (search or "").strip().lower()
        if not search_term:
            return True

        comparable = " ".join(
            [
                str(row.get("nome") or ""),
                str(row.get("cpf_cnpj") or ""),
                str(row.get("matricula") or ""),
                str(row.get("contrato_codigo") or ""),
            ]
        ).lower()
        return search_term in comparable

    @staticmethod
    def _pending_row_matches_agent(row: dict[str, object], agente: str | None) -> bool:
        agente_term = (agente or "").strip()
        if not agente_term:
            return True
        if agente_term.isdigit():
            return row.get("_agente_id") == int(agente_term)
        return agente_term.lower() in str(row.get("agente_nome") or "").lower()

    @staticmethod
    def _pending_row_matches_dates(
        row: dict[str, object],
        *,
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> bool:
        target_date = row.get("data_vencimento") or row.get("referencia_mes")
        if not isinstance(target_date, date):
            return False
        if data_inicio and target_date < data_inicio:
            return False
        if data_fim and target_date > data_fim:
            return False
        return True

    @classmethod
    def listar_parcelas_pendentes(
        cls,
        search: str | None = None,
        status_filter: str | None = None,
        competencia: date | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        agente: str | None = None,
    ):
        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)
        effective_status = (
            status_filter
            if status_filter in {Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO}
            else None
        )

        rows: list[dict[str, object]] = []
        retorno_parcela_ids: set[int] = set()
        retorno_associado_competencias: set[tuple[int, date]] = set()
        latest_file_ids: list[int] = []

        if effective_status in {None, Parcela.Status.NAO_DESCONTADO}:
            latest_file_ids = cls._latest_return_file_ids(competencia=competencia)
            if latest_file_ids:
                return_items = (
                    ArquivoRetornoItem.objects.select_related(
                        "associado__agente_responsavel",
                        "parcela__associado__agente_responsavel",
                        "parcela__ciclo__contrato__agente",
                    )
                    .filter(
                        arquivo_retorno_id__in=latest_file_ids,
                        resultado_processamento=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO,
                    )
                    .order_by("associado__nome_completo", "linha_numero", "id")
                )

                for item in return_items:
                    row = cls._build_pending_row_from_return_item(item)
                    if row is None:
                        continue
                    referencia = row.get("referencia_mes")
                    if not isinstance(referencia, date) or referencia >= mes_atual:
                        continue
                    if not cls._pending_row_matches_dates(
                        row,
                        data_inicio=data_inicio,
                        data_fim=data_fim,
                    ):
                        continue
                    if not cls._pending_row_matches_agent(row, agente):
                        continue
                    if not cls._pending_row_matches_search(row, search):
                        continue

                    parcela_id = row.get("parcela_id")
                    associado_id = row.get("associado_id")
                    if isinstance(parcela_id, int):
                        retorno_parcela_ids.add(parcela_id)
                    if isinstance(associado_id, int):
                        retorno_associado_competencias.add((associado_id, referencia))
                    rows.append(row)

        parcela_queryset = (
            Parcela.objects.select_related(
                "ciclo__contrato__associado__agente_responsavel",
                "ciclo__contrato__agente",
            )
            .filter(
                ciclo__contrato__contrato_canonico__isnull=True,
                status__in=[Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO],
                referencia_mes__lt=mes_atual,
            )
            .order_by(
                "ciclo__contrato__associado__nome_completo",
                "referencia_mes",
                "id",
            )
        )

        if competencia:
            parcela_queryset = parcela_queryset.filter(
                referencia_mes__year=competencia.year,
                referencia_mes__month=competencia.month,
            )

        if effective_status in {Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO}:
            parcela_queryset = parcela_queryset.filter(status=effective_status)

        if data_inicio:
            parcela_queryset = parcela_queryset.filter(data_vencimento__gte=data_inicio)

        if data_fim:
            parcela_queryset = parcela_queryset.filter(data_vencimento__lte=data_fim)

        parcela_queryset = cls._apply_parcela_agent_filter(parcela_queryset, agente)
        parcela_queryset = cls._apply_parcela_search(parcela_queryset, search)

        for parcela in parcela_queryset:
            if parcela.status == Parcela.Status.NAO_DESCONTADO:
                if latest_file_ids:
                    continue
                if (
                    parcela.id in retorno_parcela_ids
                    or (parcela.associado_id, parcela.referencia_mes)
                    in retorno_associado_competencias
                ):
                    continue
            rows.append(cls._build_pending_row_from_parcela(parcela))

        rows.sort(
            key=lambda row: (
                str(row.get("_sort_nome") or ""),
                row.get("_sort_referencia") or date.min,
                abs(int(row.get("id") or 0)),
            )
        )
        return rows

    @staticmethod
    def listar_parcelas_quitadas(
        search: str | None = None,
        competencia: date | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        agente: str | None = None,
    ):
        queryset = (
            BaixaManual.objects.select_related(
                "realizado_por",
                "parcela__ciclo__contrato__associado",
                "parcela__ciclo__contrato__agente",
            )
            .filter(
                parcela__ciclo__contrato__contrato_canonico__isnull=True,
            )
            .order_by("-data_baixa", "-created_at", "-id")
        )

        if competencia:
            queryset = queryset.filter(
                parcela__referencia_mes__year=competencia.year,
                parcela__referencia_mes__month=competencia.month,
            )

        if data_inicio:
            queryset = queryset.filter(data_baixa__gte=data_inicio)

        if data_fim:
            queryset = queryset.filter(data_baixa__lte=data_fim)

        queryset = BaixaManualService._apply_baixa_agent_filter(queryset, agente)
        return BaixaManualService._apply_baixa_search(queryset, search)

    @staticmethod
    def kpis_pendentes(
        *,
        status_filter: str | None = None,
        competencia: date | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        agente: str | None = None,
    ) -> dict:
        hoje = timezone.localdate()
        rows = BaixaManualService.listar_parcelas_pendentes(
            status_filter=status_filter,
            competencia=competencia,
            data_inicio=data_inicio,
            data_fim=data_fim,
            agente=agente,
        )
        total_pendentes = len(rows)
        em_aberto = sum(1 for row in rows if row.get("status") == Parcela.Status.EM_ABERTO)
        nao_descontado = sum(
            1 for row in rows if row.get("status") == Parcela.Status.NAO_DESCONTADO
        )
        valor_total = sum(Decimal(str(row.get("valor") or "0")) for row in rows)
        total_associados = len(
            {
                int(associado_id)
                for associado_id in (row.get("associado_id") for row in rows)
                if associado_id is not None
            }
        )
        total_com_parcela = sum(1 for row in rows if row.get("parcela_id"))

        baixas_mes = BaixaManual.objects.filter(
            created_at__year=hoje.year,
            created_at__month=hoje.month,
        ).count()

        total_quitados = BaixaManual.objects.filter(
            parcela__ciclo__contrato__contrato_canonico__isnull=True,
        ).count()

        return {
            "total_pendentes": total_pendentes,
            "total_pendentes_com_parcela": total_com_parcela,
            "em_aberto": em_aberto,
            "nao_descontado": nao_descontado,
            "valor_total_pendente": str(valor_total),
            "baixas_realizadas_mes": baixas_mes,
            "total_associados": total_associados,
            "total_quitados": total_quitados,
            "total_inadimplentes": total_associados,
        }

    @staticmethod
    def kpis_quitados(
        *,
        competencia: date | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
        agente: str | None = None,
    ) -> dict:
        hoje = timezone.localdate()
        base = BaixaManual.objects.filter(
            parcela__ciclo__contrato__contrato_canonico__isnull=True,
        )
        if competencia:
            base = base.filter(
                parcela__referencia_mes__year=competencia.year,
                parcela__referencia_mes__month=competencia.month,
            )
        if data_inicio:
            base = base.filter(data_baixa__gte=data_inicio)
        if data_fim:
            base = base.filter(data_baixa__lte=data_fim)
        base = BaixaManualService._apply_baixa_agent_filter(base, agente)
        totals = base.aggregate(
            total=Count("id"),
            valor_total=Sum("valor_pago"),
        )
        quitados_mes = BaixaManual.objects.filter(
            data_baixa__year=hoje.year,
            data_baixa__month=hoje.month,
            parcela__ciclo__contrato__contrato_canonico__isnull=True,
        )
        quitados_mes = BaixaManualService._apply_baixa_agent_filter(quitados_mes, agente)
        quitados_mes_totals = quitados_mes.aggregate(
            total=Count("id"),
            valor_total=Sum("valor_pago"),
        )
        return {
            "total_quitados": totals["total"] or 0,
            "valor_total_quitado": str(totals["valor_total"] or Decimal("0")),
            "quitados_este_mes": quitados_mes_totals["total"] or 0,
            "valor_quitado_este_mes": str(
                quitados_mes_totals["valor_total"] or Decimal("0")
            ),
        }

    @staticmethod
    def _registrar_baixa_manual(
        parcela: Parcela,
        *,
        comprovante,
        valor_pago,
        observacao: str,
        user,
    ) -> BaixaManual:
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

    @staticmethod
    @transaction.atomic
    def dar_baixa(parcela_id: int, comprovante, valor_pago, observacao: str, user):
        try:
            parcela = Parcela.objects.select_related(
                "ciclo__contrato__associado",
            ).get(pk=parcela_id)
        except Parcela.DoesNotExist as exc:
            raise ValidationError("Parcela não encontrada.") from exc

        return BaixaManualService._registrar_baixa_manual(
            parcela,
            comprovante=comprovante,
            valor_pago=valor_pago,
            observacao=observacao,
            user=user,
        )

    @staticmethod
    @transaction.atomic
    def inativar_associado_com_baixa(
        associado_id: int,
        *,
        comprovante,
        observacao: str,
        user,
    ) -> dict[str, object]:
        try:
            associado = Associado.objects.get(pk=associado_id)
        except Associado.DoesNotExist as exc:
            raise ValidationError("Associado não encontrado.") from exc

        hoje = timezone.localdate()
        mes_atual = hoje.replace(day=1)
        parcelas = list(
            Parcela.objects.select_related("ciclo__contrato__associado")
            .filter(
                associado=associado,
                ciclo__contrato__contrato_canonico__isnull=True,
                status__in=[Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO],
                referencia_mes__lt=mes_atual,
            )
            .order_by("referencia_mes", "numero", "id")
        )
        if not parcelas:
            raise ValidationError(
                "O associado não possui parcelas vencidas elegíveis para baixa e inativação."
            )

        file_name = getattr(comprovante, "name", "comprovante.pdf")
        file_content = comprovante.read()
        if not file_content:
            raise ValidationError("Envie um comprovante válido para registrar a baixa.")

        baixas: list[BaixaManual] = []
        for index, parcela in enumerate(parcelas, start=1):
            cloned = ContentFile(
                file_content,
                name=f"{index:02d}-{parcela.id}-{file_name}",
            )
            baixas.append(
                BaixaManualService._registrar_baixa_manual(
                    parcela,
                    comprovante=cloned,
                    valor_pago=parcela.valor,
                    observacao=observacao,
                    user=user,
                )
            )

        associado.status = Associado.Status.INATIVO
        associado.save(update_fields=["status", "updated_at"])

        return {
            "associado_id": associado.id,
            "parcelas_baixadas": len(baixas),
            "total_baixado": str(sum(baixa.valor_pago for baixa in baixas)),
        }


class DespesaService:
    @staticmethod
    def _pagamento_receita_identity(
        pagamento: PagamentoMensalidade,
        origem: str,
    ) -> tuple[str, object, date]:
        associado_key = pagamento.associado_id or re.sub(r"\D", "", pagamento.cpf_cnpj or "")
        return origem, associado_key, pagamento.referencia_month

    @staticmethod
    def _pagamento_receita_recency_key(
        pagamento: PagamentoMensalidade,
    ) -> tuple[object, int]:
        return (
            pagamento.manual_paid_at or pagamento.updated_at or pagamento.created_at,
            pagamento.id,
        )

    @classmethod
    def _listar_receitas_pagamentos(
        cls,
        *,
        start: date,
        end: date,
        agent_filter: dict[str, object] | None = None,
    ) -> list[tuple[str, PagamentoMensalidade]]:
        pagamentos = list(
            PagamentoMensalidade.objects.filter(
                referencia_month__gte=start,
                referencia_month__lt=end,
            )
            .select_related("associado", "associado__agente_responsavel")
            .order_by("referencia_month", "id")
        )
        if agent_filter is not None:
            pagamentos = [
                pagamento
                for pagamento in pagamentos
                if cls._matches_pagamento_mensalidade_agent(
                    pagamento,
                    agent_filter,
                )
            ]

        eventos: dict[tuple[str, object, date], PagamentoMensalidade] = {}
        for pagamento in pagamentos:
            if pagamento.manual_status == PagamentoMensalidade.ManualStatus.PAGO:
                key = cls._pagamento_receita_identity(pagamento, "inadimplencia_manual")
                atual = eventos.get(key)
                if atual is None or cls._pagamento_receita_recency_key(
                    pagamento
                ) >= cls._pagamento_receita_recency_key(atual):
                    eventos[key] = pagamento

            if (pagamento.status_code or "").strip() in {"1", "4"}:
                key = cls._pagamento_receita_identity(pagamento, "arquivo_retorno")
                atual = eventos.get(key)
                if atual is None or cls._pagamento_receita_recency_key(
                    pagamento
                ) >= cls._pagamento_receita_recency_key(atual):
                    eventos[key] = pagamento

        return sorted(
            ((key[0], pagamento) for key, pagamento in eventos.items()),
            key=lambda item: (
                item[1].referencia_month,
                item[1].nome_relatorio or "",
                item[1].id,
                item[0],
            ),
        )

    _RENEWAL_ID_PATTERN = re.compile(r"refi\s*#(\d+)", re.IGNORECASE)

    @staticmethod
    def _monthly_window(month: date | None = None) -> tuple[date, date]:
        month_start = (month or timezone.localdate()).replace(day=1)
        return month_start, shift_month(month_start, 1)

    @staticmethod
    def _manual_launch_reference_date(despesa: Despesa) -> date:
        return despesa.data_pagamento or despesa.data_despesa

    @staticmethod
    def _build_agent_filter(agente: str | None) -> dict[str, object] | None:
        term = (agente or "").strip()
        if not term:
            return None

        agent_id = int(term) if term.isdigit() else None
        resolved_term = term
        if agent_id is not None:
            agent = User.objects.filter(pk=agent_id).only("first_name", "last_name", "email").first()
            if agent is not None:
                resolved_term = agent.full_name or agent.email or term

        return {
            "id": agent_id,
            "term": resolved_term.casefold(),
        }

    @staticmethod
    def _matches_agent_filter(
        agent_filter: dict[str, object] | None,
        *,
        user: User | None = None,
        fallback_text: str | None = None,
    ) -> bool:
        if agent_filter is None:
            return True

        agent_id = agent_filter.get("id")
        if user is not None:
            if agent_id is not None and user.id == agent_id:
                return True

            full_name = (user.full_name or "").casefold()
            email = (user.email or "").casefold()
            term = str(agent_filter["term"])
            if term and (term in full_name or term in email):
                return True

        if fallback_text:
            return str(agent_filter["term"]) in fallback_text.casefold()

        return False

    @classmethod
    def _matches_pagamento_mensalidade_agent(
        cls,
        pagamento: PagamentoMensalidade,
        agent_filter: dict[str, object] | None,
    ) -> bool:
        associado = getattr(pagamento, "associado", None)
        agente = getattr(associado, "agente_responsavel", None)
        return cls._matches_agent_filter(agent_filter, user=agente)

    @classmethod
    def _matches_devolucao_agent(
        cls,
        devolucao: DevolucaoAssociado,
        agent_filter: dict[str, object] | None,
    ) -> bool:
        contrato = getattr(devolucao, "contrato", None)
        agente = getattr(contrato, "agente", None)
        return cls._matches_agent_filter(
            agent_filter,
            user=agente,
            fallback_text=devolucao.agente_snapshot,
        )

    @classmethod
    def _matches_pagamento_operacional_agent(
        cls,
        pagamento: Pagamento,
        pagamento_context: dict[str, object],
        agent_filter: dict[str, object] | None,
    ) -> bool:
        contrato = pagamento_context.get("contrato")
        agente = getattr(contrato, "agente", None) if contrato is not None else None
        return cls._matches_agent_filter(
            agent_filter,
            user=agente,
            fallback_text=pagamento.agente_responsavel,
        )

    @classmethod
    def _resolve_pagamento_operacional_context(
        cls,
        pagamentos: list[Pagamento],
    ) -> dict[int, dict[str, object]]:
        zero = Decimal("0.00")
        contract_ids: set[int] = set()
        contract_codes: set[str] = set()
        refinancing_ids: set[int] = set()
        parsed_refs: dict[int, dict[str, int | str | None]] = {}

        for pagamento in pagamentos:
            refs = (
                pagamento.referencias_externas
                if isinstance(pagamento.referencias_externas, dict)
                else {}
            )
            payment_kind = str(refs.get("payment_kind") or "").strip()
            contract_id_raw = refs.get("contrato_id")
            refinancing_id_raw = refs.get("refinanciamento_id")

            contract_id = (
                int(contract_id_raw)
                if str(contract_id_raw).isdigit()
                else None
            )
            refinancing_id = (
                int(refinancing_id_raw)
                if str(refinancing_id_raw).isdigit()
                else None
            )

            if refinancing_id is None:
                match = cls._RENEWAL_ID_PATTERN.search(pagamento.notes or "")
                if match:
                    refinancing_id = int(match.group(1))
                    if not payment_kind:
                        payment_kind = "renovacao"

            if contract_id is not None:
                contract_ids.add(contract_id)
            elif pagamento.contrato_codigo:
                contract_codes.add(pagamento.contrato_codigo)

            if refinancing_id is not None:
                refinancing_ids.add(refinancing_id)

            parsed_refs[pagamento.id] = {
                "payment_kind": payment_kind or None,
                "contract_id": contract_id,
                "refinancing_id": refinancing_id,
            }

        contracts = Contrato.objects.select_related("agente").filter(
            Q(id__in=contract_ids) | Q(codigo__in=contract_codes)
        )
        contracts_by_id = {contrato.id: contrato for contrato in contracts}
        contracts_by_code = {contrato.codigo: contrato for contrato in contracts}

        refinancings = Refinanciamento.objects.select_related("contrato_origem").filter(
            id__in=refinancing_ids
        )
        refinancings_by_id = {refinanciamento.id: refinanciamento for refinanciamento in refinancings}

        payload: dict[int, dict[str, object]] = {}
        for pagamento in pagamentos:
            refs = parsed_refs.get(pagamento.id, {})
            refinancing = refinancings_by_id.get(int(refs["refinancing_id"])) if refs.get("refinancing_id") else None
            contract = None
            if refinancing and refinancing.contrato_origem_id:
                contract = refinancing.contrato_origem
            elif refs.get("contract_id"):
                contract = contracts_by_id.get(int(refs["contract_id"]))
            elif pagamento.contrato_codigo:
                contract = contracts_by_code.get(pagamento.contrato_codigo)

            payment_kind = str(refs.get("payment_kind") or "").strip()
            notes_lower = (pagamento.notes or "").lower()
            is_renewal = bool(
                payment_kind == "renovacao"
                or refinancing is not None
                or ("renova" in notes_lower and "tesouraria" in notes_lower)
            )

            valor_associado = Decimal(str(pagamento.valor_pago or zero))
            if is_renewal:
                valor_agente = Decimal(
                    str(refinancing.repasse_agente if refinancing is not None else zero)
                )
            else:
                valor_agente = Decimal(
                    str(contract.comissao_agente if contract is not None else zero)
                )

            payload[pagamento.id] = {
                "payment_kind": "renovacao" if is_renewal else "contrato_inicial",
                "contrato": contract,
                "refinanciamento": refinancing,
                "valor_associado": valor_associado,
                "valor_agente": valor_agente,
                "valor_total": valor_associado + valor_agente,
            }

        return payload

    @staticmethod
    def _build_resultado_row(
        *,
        month: date,
        receitas_inadimplencia: Decimal,
        receitas_retorno: Decimal,
        complementos_receita: Decimal,
        despesas_manuais: Decimal,
        devolucoes: Decimal,
        pagamentos_operacionais: Decimal,
    ) -> dict[str, object]:
        receitas = receitas_inadimplencia + receitas_retorno + complementos_receita
        despesas_total = despesas_manuais + devolucoes
        lucro = receitas - despesas_total
        lucro_liquido = lucro - pagamentos_operacionais
        return {
            "mes": month,
            "receitas": receitas,
            "receitas_inadimplencia": receitas_inadimplencia,
            "receitas_retorno": receitas_retorno,
            "complementos_receita": complementos_receita,
            "despesas": despesas_total,
            "despesas_manuais": despesas_manuais,
            "devolucoes": devolucoes,
            "pagamentos_operacionais": pagamentos_operacionais,
            "lucro": lucro,
            "lucro_liquido": lucro_liquido,
        }

    @staticmethod
    def listar_despesas(
        *,
        competencia: date | None = None,
        search: str | None = None,
        status: str | None = None,
        status_anexo: str | None = None,
        tipo: str | None = None,
        natureza: str | None = None,
    ):
        queryset = Despesa.objects.select_related("user").order_by(
            "-data_despesa",
            "-created_at",
            "-id",
        )

        if competencia:
            queryset = queryset.filter(
                data_despesa__year=competencia.year,
                data_despesa__month=competencia.month,
            )

        if search:
            queryset = queryset.filter(
                Q(categoria__icontains=search) | Q(descricao__icontains=search)
            )

        if status in {choice[0] for choice in Despesa.Status.choices}:
            queryset = queryset.filter(status=status)

        if status_anexo in {choice[0] for choice in Despesa.StatusAnexo.choices}:
            queryset = queryset.filter(status_anexo=status_anexo)

        if tipo in {choice[0] for choice in Despesa.Tipo.choices}:
            queryset = queryset.filter(tipo=tipo)

        if natureza in {choice[0] for choice in Despesa.Natureza.choices}:
            queryset = queryset.filter(natureza=natureza)

        return queryset

    @staticmethod
    def kpis(queryset) -> dict[str, object]:
        zero = Value(Decimal("0.00"), output_field=DecimalField(max_digits=15, decimal_places=2))
        return queryset.aggregate(
            total_despesas=Count("id"),
            valor_total=Coalesce(Sum("valor"), zero),
            valor_pago=Coalesce(
                Sum("valor", filter=Q(status=Despesa.Status.PAGO)),
                zero,
            ),
            valor_pendente=Coalesce(
                Sum("valor", filter=Q(status=Despesa.Status.PENDENTE)),
                zero,
            ),
            pendentes_anexo=Count(
                "id",
                filter=Q(status_anexo=Despesa.StatusAnexo.PENDENTE),
            ),
        )

    @staticmethod
    def anexar(despesa: Despesa, arquivo) -> Despesa:
        despesa.anexo = arquivo
        despesa.nome_anexo = getattr(arquivo, "name", "")[:255]
        despesa.status_anexo = Despesa.StatusAnexo.ANEXADO
        despesa.save(update_fields=["anexo", "nome_anexo", "status_anexo", "updated_at"])
        return despesa

    @staticmethod
    def excluir(despesa: Despesa) -> None:
        despesa.soft_delete()

    @staticmethod
    def sugerir_categorias(search: str | None = None) -> list[dict[str, object]]:
        queryset = (
            Despesa.objects.exclude(categoria="")
            .values("categoria")
            .annotate(total=Count("id"))
            .order_by("-total", "categoria")
        )
        if search:
            queryset = queryset.filter(categoria__icontains=search)
        return [
            {"categoria": row["categoria"], "frequencia": row["total"]}
            for row in queryset[:12]
        ]

    @staticmethod
    def resultado_mensal(
        *,
        competencia: date | None = None,
        agente: str | None = None,
    ) -> dict[str, object]:
        base_month = (competencia or timezone.localdate()).replace(day=1)
        start_month = shift_month(base_month, -11)
        months = [shift_month(start_month, index) for index in range(12)]
        _, end_month = DespesaService._monthly_window(base_month)
        zero = Decimal("0.00")
        agent_filter = DespesaService._build_agent_filter(agente)

        pagamentos = DespesaService._listar_receitas_pagamentos(
            start=start_month,
            end=end_month,
            agent_filter=agent_filter,
        )
        despesas = list(
            Despesa.objects.filter(
                Q(data_despesa__gte=start_month, data_despesa__lt=end_month)
                | Q(data_pagamento__gte=start_month, data_pagamento__lt=end_month)
            )
        )
        if agent_filter is not None:
            despesas = []
        devolucoes = list(
            DevolucaoAssociado.objects.filter(
                revertida_em__isnull=True,
                data_devolucao__gte=start_month,
                data_devolucao__lt=end_month,
            )
            .select_related("contrato", "contrato__agente")
        )
        if agent_filter is not None:
            devolucoes = [
                devolucao
                for devolucao in devolucoes
                if DespesaService._matches_devolucao_agent(devolucao, agent_filter)
            ]
        pagamentos_operacionais = list(
            Pagamento.objects.filter(
                status=Pagamento.Status.PAGO,
                paid_at__date__gte=start_month,
                paid_at__date__lt=end_month,
            )
        )

        receitas_inadimplencia_por_mes = {month: zero for month in months}
        receitas_retorno_por_mes = {month: zero for month in months}
        despesas_manuais_por_mes = {month: zero for month in months}
        complementos_receita_por_mes = {month: zero for month in months}
        devolucoes_por_mes = {month: zero for month in months}
        pagamentos_operacionais_por_mes = {month: zero for month in months}

        for origem, pagamento in pagamentos:
            month_key = pagamento.referencia_month.replace(day=1)
            if month_key not in receitas_inadimplencia_por_mes:
                continue
            if origem == "inadimplencia_manual":
                receitas_inadimplencia_por_mes[month_key] += Decimal(
                    str(pagamento.recebido_manual or pagamento.valor or zero)
                )
            elif origem == "arquivo_retorno":
                receitas_retorno_por_mes[month_key] += Decimal(
                    str(pagamento.valor or zero)
                )

        for despesa in despesas:
            if despesa.natureza == Despesa.Natureza.COMPLEMENTO_RECEITA:
                if despesa.status != Despesa.Status.PAGO:
                    continue
                month_key = DespesaService._manual_launch_reference_date(despesa).replace(day=1)
                if month_key in complementos_receita_por_mes:
                    complementos_receita_por_mes[month_key] += Decimal(str(despesa.valor or zero))
                continue

            month_key = despesa.data_despesa.replace(day=1)
            if month_key in despesas_manuais_por_mes:
                despesas_manuais_por_mes[month_key] += Decimal(str(despesa.valor or zero))

        for devolucao in devolucoes:
            month_key = devolucao.data_devolucao.replace(day=1)
            if month_key in devolucoes_por_mes:
                devolucoes_por_mes[month_key] += Decimal(str(devolucao.valor or zero))

        pagamentos_operacionais_context = DespesaService._resolve_pagamento_operacional_context(
            pagamentos_operacionais
        )
        if agent_filter is not None:
            pagamentos_operacionais = [
                pagamento
                for pagamento in pagamentos_operacionais
                if DespesaService._matches_pagamento_operacional_agent(
                    pagamento,
                    pagamentos_operacionais_context.get(pagamento.id, {}),
                    agent_filter,
                )
            ]
        for pagamento in pagamentos_operacionais:
            if pagamento.paid_at is None:
                continue
            month_key = pagamento.paid_at.date().replace(day=1)
            if month_key in pagamentos_operacionais_por_mes:
                pagamento_context = pagamentos_operacionais_context.get(pagamento.id, {})
                pagamentos_operacionais_por_mes[month_key] += Decimal(
                    str(pagamento_context.get("valor_total") or zero)
                )

        rows: list[dict[str, object]] = []
        for month in months:
            rows.append(
                DespesaService._build_resultado_row(
                    month=month,
                    receitas_inadimplencia=receitas_inadimplencia_por_mes[month],
                    receitas_retorno=receitas_retorno_por_mes[month],
                    complementos_receita=complementos_receita_por_mes[month],
                    despesas_manuais=despesas_manuais_por_mes[month],
                    devolucoes=devolucoes_por_mes[month],
                    pagamentos_operacionais=pagamentos_operacionais_por_mes[month],
                )
            )

        totais = {
            "receitas": sum((row["receitas"] for row in rows), zero),
            "despesas": sum((row["despesas"] for row in rows), zero),
            "lucro": sum((row["lucro"] for row in rows), zero),
            "lucro_liquido": sum((row["lucro_liquido"] for row in rows), zero),
        }
        return {"rows": rows, "totais": totais}

    @staticmethod
    def resultado_mensal_detalhe(
        *,
        mes: date,
        agente: str | None = None,
    ) -> dict[str, object]:
        month_start, next_month = DespesaService._monthly_window(mes)
        zero = Decimal("0.00")
        agent_filter = DespesaService._build_agent_filter(agente)

        pagamentos = DespesaService._listar_receitas_pagamentos(
            start=month_start,
            end=next_month,
            agent_filter=agent_filter,
        )
        despesas = list(
            Despesa.objects.filter(
                Q(data_despesa__gte=month_start, data_despesa__lt=next_month)
                | Q(data_pagamento__gte=month_start, data_pagamento__lt=next_month)
            )
            .select_related("user")
            .order_by("-data_despesa", "-created_at", "-id")
        )
        if agent_filter is not None:
            despesas = []
        devolucoes = list(
            DevolucaoAssociado.objects.filter(
                revertida_em__isnull=True,
                data_devolucao__gte=month_start,
                data_devolucao__lt=next_month,
            )
            .select_related("associado", "contrato", "contrato__agente", "realizado_por")
            .order_by("-data_devolucao", "-created_at", "-id")
        )
        if agent_filter is not None:
            devolucoes = [
                devolucao
                for devolucao in devolucoes
                if DespesaService._matches_devolucao_agent(devolucao, agent_filter)
            ]
        pagamentos_operacionais = list(
            Pagamento.objects.filter(
                status=Pagamento.Status.PAGO,
                paid_at__date__gte=month_start,
                paid_at__date__lt=next_month,
            )
            .select_related("cadastro")
            .order_by("-paid_at", "-created_at", "-id")
        )

        receitas_itens: list[dict[str, object]] = []
        receitas_inadimplencia = zero
        receitas_retorno = zero
        complementos_receita = zero

        for origem, pagamento in pagamentos:
            associado = pagamento.associado
            associado_nome = (
                associado.nome_completo
                if associado and associado.nome_completo
                else pagamento.nome_relatorio or "-"
            )
            matricula = ""
            agente_nome = ""
            if associado:
                matricula = associado.matricula_orgao or associado.matricula or pagamento.matricula
                if associado.agente_responsavel:
                    agente_nome = associado.agente_responsavel.full_name

            if origem == "inadimplencia_manual":
                valor = Decimal(str(pagamento.recebido_manual or pagamento.valor or zero))
                receitas_inadimplencia += valor
                receitas_itens.append(
                    {
                        "id": pagamento.id,
                        "origem": "inadimplencia_manual",
                        "origem_label": "Inadimplência manual",
                        "data": (
                            pagamento.manual_paid_at.date()
                            if pagamento.manual_paid_at
                            else pagamento.referencia_month
                        ),
                        "referencia": pagamento.referencia_month,
                        "associado_nome": associado_nome,
                        "cpf_cnpj": pagamento.cpf_cnpj,
                        "matricula": matricula,
                        "agente_nome": agente_nome,
                        "descricao": "Recebimento manual de inadimplência.",
                        "valor": valor,
                    }
                )
            elif origem == "arquivo_retorno":
                valor = Decimal(str(pagamento.valor or zero))
                receitas_retorno += valor
                receitas_itens.append(
                    {
                        "id": pagamento.id,
                        "origem": "arquivo_retorno",
                        "origem_label": "Arquivo retorno",
                        "data": pagamento.referencia_month,
                        "referencia": pagamento.referencia_month,
                        "associado_nome": associado_nome,
                        "cpf_cnpj": pagamento.cpf_cnpj,
                        "matricula": matricula,
                        "agente_nome": agente_nome,
                        "descricao": "Receita reconhecida via arquivo retorno.",
                        "valor": valor,
                    }
                )

        despesas_itens: list[dict[str, object]] = []
        despesas_manuais = zero
        devolucoes_total = zero

        for despesa in despesas:
            valor = Decimal(str(despesa.valor or zero))
            if despesa.natureza == Despesa.Natureza.COMPLEMENTO_RECEITA:
                if despesa.status != Despesa.Status.PAGO:
                    continue
                reference_date = DespesaService._manual_launch_reference_date(despesa)
                if reference_date < month_start or reference_date >= next_month:
                    continue
                complementos_receita += valor
                receitas_itens.append(
                    {
                        "id": despesa.id,
                        "origem": "complemento_receita",
                        "origem_label": "Complemento de receita",
                        "data": reference_date,
                        "referencia": reference_date.replace(day=1),
                        "associado_nome": despesa.categoria,
                        "cpf_cnpj": "",
                        "matricula": "",
                        "agente_nome": "",
                        "descricao": despesa.descricao or "Complemento de receita lançado manualmente.",
                        "valor": valor,
                    }
                )
                continue

            despesas_manuais += valor
            despesas_itens.append(
                {
                    "id": despesa.id,
                    "origem": "despesa_manual",
                    "origem_label": "Despesa manual",
                    "data": despesa.data_despesa,
                    "titulo": despesa.categoria,
                    "subtitulo": despesa.descricao or "Sem descrição complementar.",
                    "descricao": despesa.observacoes or "",
                    "referencia": (
                        f"{despesa.get_status_display()} · {despesa.get_tipo_display()}"
                        if despesa.tipo
                        else despesa.get_status_display()
                    ),
                    "valor": valor,
                }
            )

        for devolucao in devolucoes:
            valor = Decimal(str(devolucao.valor or zero))
            devolucoes_total += valor
            despesas_itens.append(
                {
                    "id": devolucao.id,
                    "origem": "devolucao",
                    "origem_label": "Devolução",
                    "data": devolucao.data_devolucao,
                    "titulo": devolucao.nome_snapshot,
                    "subtitulo": devolucao.contrato_codigo_snapshot,
                    "descricao": devolucao.motivo,
                    "referencia": devolucao.get_tipo_display(),
                    "valor": valor,
                }
            )

        pagamentos_operacionais_itens: list[dict[str, object]] = []
        pagamentos_operacionais_total = zero
        pagamentos_operacionais_context = DespesaService._resolve_pagamento_operacional_context(
            pagamentos_operacionais
        )
        if agent_filter is not None:
            pagamentos_operacionais = [
                pagamento
                for pagamento in pagamentos_operacionais
                if DespesaService._matches_pagamento_operacional_agent(
                    pagamento,
                    pagamentos_operacionais_context.get(pagamento.id, {}),
                    agent_filter,
                )
            ]

        for pagamento in pagamentos_operacionais:
            if pagamento.paid_at is None:
                continue
            pagamento_context = pagamentos_operacionais_context.get(pagamento.id, {})
            valor_associado = Decimal(str(pagamento_context.get("valor_associado") or zero))
            valor_agente = Decimal(str(pagamento_context.get("valor_agente") or zero))
            valor_total = Decimal(str(pagamento_context.get("valor_total") or zero))
            pagamentos_operacionais_total += valor_total
            pagamentos_operacionais_itens.append(
                {
                    "id": pagamento.id,
                    "data": pagamento.paid_at.date(),
                    "favorecido": pagamento.full_name,
                    "cpf_cnpj": pagamento.cpf_cnpj,
                    "agente_nome": pagamento.agente_responsavel,
                    "contrato_codigo": pagamento.contrato_codigo,
                    "origem": pagamento.origem,
                    "origem_label": pagamento.get_origem_display(),
                    "valor_associado": valor_associado,
                    "valor_agente": valor_agente,
                    "valor_total": valor_total,
                }
            )

        resumo = DespesaService._build_resultado_row(
            month=month_start,
            receitas_inadimplencia=receitas_inadimplencia,
            receitas_retorno=receitas_retorno,
            complementos_receita=complementos_receita,
            despesas_manuais=despesas_manuais,
            devolucoes=devolucoes_total,
            pagamentos_operacionais=pagamentos_operacionais_total,
        )

        return {
            "mes": month_start,
            "resumo": {key: value for key, value in resumo.items() if key != "mes"},
            "receitas": receitas_itens,
            "despesas": despesas_itens,
            "pagamentos_operacionais": pagamentos_operacionais_itens,
        }
