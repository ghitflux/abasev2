from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado, Documento
from apps.associados.services import add_months
from apps.contratos.models import Contrato
from apps.tesouraria.models import Pagamento

from .models import DocIssue, DocReupload, EsteiraItem, Pendencia


class AnaliseService:
    FILA_SECOES = (
        "novos_contratos",
        "ver_todos",
        "pendencias",
        "pendencias_corrigidas",
        "enviado_tesouraria",
        "enviado_coordenacao",
        "efetivados",
        "cancelados",
    )

    @staticmethod
    def _parse_competencia(competencia: str | None) -> date:
        if not competencia:
            today = timezone.localdate()
            base = today.replace(day=1)
            if today.day <= 5:
                base = add_months(base, -1)
            return base

        try:
            return datetime.strptime(competencia, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc

    @staticmethod
    def competencia_window(competencia: str | None) -> tuple[date, datetime, datetime]:
        competencia_date = AnaliseService._parse_competencia(competencia)
        start_date = competencia_date.replace(day=6)
        next_month = add_months(competencia_date, 1)
        end_date = next_month.replace(day=6)
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
        end = timezone.make_aware(datetime.combine(end_date, time.min), tz)
        return competencia_date, start, end

    @staticmethod
    def competencia_meta(competencia: str | None) -> dict[str, str]:
        competencia_date, start, end = AnaliseService.competencia_window(competencia)
        finish = timezone.localtime(end - timedelta(seconds=1))
        return {
            "mes": competencia_date.strftime("%Y-%m"),
            "inicio": timezone.localtime(start).isoformat(),
            "fim": finish.isoformat(),
            "intervalo_label": (
                f"{timezone.localtime(start).strftime('%d/%m/%Y %H:%M')} - "
                f"{finish.strftime('%d/%m/%Y %H:%M')}"
            ),
        }

    @staticmethod
    def _esteira_base_queryset(user, search: str | None = None):
        latest_contract = Contrato.objects.filter(
            associado_id=OuterRef("associado_id")
        ).order_by("-created_at", "-id")
        queryset = (
            EsteiraItem.objects.select_related(
                "associado",
                "associado__agente_responsavel",
                "associado__contato_historico",
                "analista_responsavel",
            )
            .prefetch_related(
                Prefetch("associado__documentos"),
                Prefetch("associado__doc_issues"),
                Prefetch("associado__contratos__ciclos__parcelas"),
                Prefetch("pendencias"),
                Prefetch("transicoes__realizado_por"),
            )
            .annotate(
                has_documents=Exists(
                    Documento.objects.filter(associado_id=OuterRef("associado_id")).exclude(
                        tipo__in=Documento.free_attachment_types()
                    )
                ),
                has_pending_document=Exists(
                    Documento.objects.filter(associado_id=OuterRef("associado_id"))
                    .exclude(tipo__in=Documento.free_attachment_types())
                    .exclude(status=Documento.Status.APROVADO)
                ),
                has_open_pendencia=Exists(
                    Pendencia.objects.filter(
                        esteira_item_id=OuterRef("pk"),
                        status=Pendencia.Status.ABERTA,
                    )
                ),
                has_resolved_pendencia=Exists(
                    Pendencia.objects.filter(
                        esteira_item_id=OuterRef("pk"),
                        status=Pendencia.Status.RESOLVIDA,
                    )
                ),
                has_open_doc_issue=Exists(
                    DocIssue.objects.filter(
                        associado_id=OuterRef("associado_id"),
                        status=DocIssue.Status.INCOMPLETO,
                    )
                ),
                has_any_reupload=Exists(
                    DocReupload.objects.filter(associado_id=OuterRef("associado_id"))
                ),
                has_received_reupload=Exists(
                    DocReupload.objects.filter(
                        associado_id=OuterRef("associado_id"),
                        status=DocReupload.Status.RECEBIDO,
                    )
                ),
                has_payment=Exists(
                    Pagamento.objects.filter(cadastro_id=OuterRef("associado_id"))
                ),
                latest_contract_status=Subquery(latest_contract.values("status")[:1]),
                resolved_pendencias_count=Count(
                    "pendencias",
                    filter=Q(pendencias__status=Pendencia.Status.RESOLVIDA),
                    distinct=True,
                ),
            )
            .order_by("-created_at")
        )

        if user.has_role("ANALISTA") and not user.has_role("ADMIN"):
            queryset = queryset.filter(
                Q(analista_responsavel=user)
                | Q(analista_responsavel__isnull=True)
            )

        if search:
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
                | Q(associado__contratos__codigo__icontains=search)
            ).distinct()

        return queryset

    @staticmethod
    def _apply_dashboard_filters(
        queryset,
        *,
        agente: str | None = None,
        analista: str | None = None,
        etapa: str | None = None,
        status: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ):
        if agente:
            agente_term = agente.strip()
            if agente_term:
                if agente_term.isdigit():
                    queryset = queryset.filter(associado__agente_responsavel_id=int(agente_term))
                else:
                    queryset = queryset.filter(
                        Q(associado__agente_responsavel__first_name__icontains=agente_term)
                        | Q(associado__agente_responsavel__last_name__icontains=agente_term)
                        | Q(associado__agente_responsavel__email__icontains=agente_term)
                    )

        if analista:
            analista_term = analista.strip()
            if analista_term == "sem_responsavel":
                queryset = queryset.filter(analista_responsavel__isnull=True)
            elif analista_term.isdigit():
                queryset = queryset.filter(analista_responsavel_id=int(analista_term))
            else:
                queryset = queryset.filter(
                    Q(analista_responsavel__first_name__icontains=analista_term)
                    | Q(analista_responsavel__last_name__icontains=analista_term)
                    | Q(analista_responsavel__email__icontains=analista_term)
                )

        if etapa in {choice[0] for choice in EsteiraItem.Etapa.choices}:
            queryset = queryset.filter(etapa_atual=etapa)
        if status in {choice[0] for choice in EsteiraItem.Situacao.choices}:
            queryset = queryset.filter(status=status)

        if data_inicio:
            try:
                queryset = queryset.filter(created_at__date__gte=date.fromisoformat(data_inicio))
            except ValueError:
                raise ValidationError("Data inicial inválida. Use o formato YYYY-MM-DD.")
        if data_fim:
            try:
                queryset = queryset.filter(created_at__date__lte=date.fromisoformat(data_fim))
            except ValueError:
                raise ValidationError("Data final inválida. Use o formato YYYY-MM-DD.")

        return queryset

    @staticmethod
    def fila_queryset(
        secao: str,
        user,
        search: str | None = None,
        *,
        agente: str | None = None,
        analista: str | None = None,
        etapa: str | None = None,
        status: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ):
        if secao not in AnaliseService.FILA_SECOES:
            raise ValidationError("Seção inválida para o módulo de análise.")

        queryset = AnaliseService._esteira_base_queryset(user, search)
        queryset = AnaliseService._apply_dashboard_filters(
            queryset,
            agente=agente,
            analista=analista,
            etapa=etapa,
            status=status,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        if secao == "ver_todos":
            # Exclui itens que foram removidos operacionalmente via "excluir preservando
            # histórico" (etapa=CONCLUIDO + status=REJEITADO sem contrato cancelado).
            # Contratos cancelados têm latest_contract_status=CANCELADO e permanecem
            # visíveis para rastreabilidade histórica.
            return queryset.exclude(
                Q(etapa_atual=EsteiraItem.Etapa.CONCLUIDO)
                & Q(status=EsteiraItem.Situacao.REJEITADO)
                & ~Q(latest_contract_status=Contrato.Status.CANCELADO)
            ).order_by("-updated_at", "-created_at")

        if secao == "pendencias":
            return queryset.filter(
                etapa_atual__in=[EsteiraItem.Etapa.CADASTRO, EsteiraItem.Etapa.ANALISE]
            ).filter(
                Q(has_open_pendencia=True)
                | Q(has_open_doc_issue=True)
                | (Q(has_documents=False) & Q(has_any_reupload=False))
            ).order_by("-updated_at", "-created_at")

        if secao == "novos_contratos":
            # Inclui contratos novos na etapa de análise independentemente da
            # situação documental (com ou sem pendência de documento).
            # Exclui apenas: pendência aberta pelo analista, ciclo de correção
            # iniciado (reupload recebido / pendência já resolvida) e associados
            # já efetivados (ativo / inadimplente / inativo).
            return queryset.filter(
                etapa_atual=EsteiraItem.Etapa.ANALISE
            ).exclude(
                Q(has_open_pendencia=True)
                | Q(has_received_reupload=True)
                | Q(resolved_pendencias_count__gt=0)
                | Q(associado__status__in=[
                    Associado.Status.ATIVO,
                    Associado.Status.INADIMPLENTE,
                    Associado.Status.INATIVO,
                ])
            ).order_by("-updated_at", "-created_at")

        if secao == "pendencias_corrigidas":
            return queryset.filter(
                etapa_atual=EsteiraItem.Etapa.ANALISE
            ).filter(
                Q(has_received_reupload=True) | Q(resolved_pendencias_count__gt=0)
            ).order_by("-updated_at", "-created_at")

        if secao == "enviado_tesouraria":
            return queryset.filter(
                etapa_atual=EsteiraItem.Etapa.TESOURARIA
            ).order_by("-updated_at", "-created_at")

        if secao == "enviado_coordenacao":
            return queryset.filter(
                etapa_atual=EsteiraItem.Etapa.COORDENACAO
            ).order_by("-updated_at", "-created_at")

        if secao == "efetivados":
            return queryset.filter(
                etapa_atual=EsteiraItem.Etapa.CONCLUIDO
            ).exclude(
                associado__status=Associado.Status.INATIVO
            ).order_by("-concluido_em", "-updated_at", "-created_at")

        return queryset.filter(
            latest_contract_status=Contrato.Status.CANCELADO
        ).order_by("-created_at")

    @staticmethod
    def resumo(
        user,
        search: str | None = None,
        competencia: str | None = None,
        *,
        agente: str | None = None,
        analista: str | None = None,
        etapa: str | None = None,
        status: str | None = None,
        data_inicio: str | None = None,
        data_fim: str | None = None,
    ) -> dict[str, object]:
        filas = {
            secao: AnaliseService.fila_queryset(
                secao,
                user,
                search,
                agente=agente,
                analista=analista,
                etapa=etapa,
                status=status,
                data_inicio=data_inicio,
                data_fim=data_fim,
            ).count()
            for secao in AnaliseService.FILA_SECOES
        }
        ajustes_qs = AnaliseService.ajustes_queryset(competencia, search)
        margem_qs = AnaliseService.margem_queryset(competencia, search)
        dados_qs = AnaliseService.dados_queryset(search)
        ajustes_total = ajustes_qs.aggregate(
            total=Coalesce(
                Sum("valor_pago"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )["total"]
        margem_totais = AnaliseService.margem_totais(margem_qs)

        return {
            "competencia": AnaliseService.competencia_meta(competencia),
            "filas": filas,
            "ajustes": {
                "count": ajustes_qs.count(),
                "total_pago": ajustes_total,
            },
            "margem": {
                "count": margem_qs.count(),
                "soma_margem": margem_totais["soma_margem"],
                "soma_antecipacao": margem_totais["soma_antecipacao"],
            },
            "dados": {
                "count": dados_qs.count(),
            },
        }

    @staticmethod
    def ajustes_queryset(competencia: str | None = None, search: str | None = None):
        _, start, end = AnaliseService.competencia_window(competencia)
        queryset = (
            Pagamento.objects.select_related("cadastro", "created_by")
            .annotate(referencia_at=Coalesce("paid_at", "created_at"))
            .filter(referencia_at__gte=start, referencia_at__lt=end)
            .order_by("referencia_at", "id")
        )

        if search:
            digits = "".join(ch for ch in search if ch.isdigit())
            filters = (
                Q(full_name__icontains=search)
                | Q(contrato_codigo__icontains=search)
                | Q(agente_responsavel__icontains=search)
            )
            if digits:
                filters |= Q(cpf_cnpj__icontains=digits)
            queryset = queryset.filter(filters)

        return queryset

    @staticmethod
    def margem_queryset(competencia: str | None = None, search: str | None = None):
        _, start, end = AnaliseService.competencia_window(competencia)
        decimal_output = DecimalField(max_digits=14, decimal_places=2)
        zero = Value(Decimal("0.00"), output_field=decimal_output)
        percent = Value(Decimal("0.30"), output_field=DecimalField(max_digits=4, decimal_places=2))
        prazo = Coalesce(F("prazo_meses"), Value(3))

        queryset = (
            Contrato.objects.select_related("associado", "agente")
            .filter(created_at__gte=start, created_at__lt=end)
            .annotate(
                calc_trinta_bruto=ExpressionWrapper(
                    Coalesce(F("valor_bruto"), zero) * percent,
                    output_field=decimal_output,
                ),
                calc_margem=ExpressionWrapper(
                    Coalesce(F("valor_liquido"), zero)
                    - (Coalesce(F("valor_bruto"), zero) * percent),
                    output_field=decimal_output,
                ),
                calc_valor_antecipacao=ExpressionWrapper(
                    Coalesce(F("valor_mensalidade"), zero) * prazo,
                    output_field=decimal_output,
                ),
            )
            .annotate(
                calc_doacao_fundo=ExpressionWrapper(
                    F("calc_valor_antecipacao") * percent,
                    output_field=decimal_output,
                ),
                calc_pode_prosseguir=Case(
                    When(calc_margem__gt=0, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
            )
            .order_by("-created_at")
        )

        if search:
            digits = "".join(ch for ch in search if ch.isdigit())
            queryset = queryset.filter(
                Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=digits or search)
                | Q(codigo__icontains=search)
                | Q(agente__first_name__icontains=search)
                | Q(agente__last_name__icontains=search)
            )

        return queryset

    @staticmethod
    def margem_totais(queryset) -> dict[str, Decimal]:
        totals = queryset.aggregate(
            soma_valor_bruto=Coalesce(
                Sum("valor_bruto"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_valor_liquido=Coalesce(
                Sum("valor_liquido"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_mensalidade=Coalesce(
                Sum("valor_mensalidade"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_trinta_bruto=Coalesce(
                Sum("calc_trinta_bruto"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_margem=Coalesce(
                Sum("calc_margem"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_antecipacao=Coalesce(
                Sum("calc_valor_antecipacao"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            soma_doacao=Coalesce(
                Sum("calc_doacao_fundo"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        return totals

    @staticmethod
    def dados_queryset(search: str | None = None):
        queryset = (
            Associado.objects.select_related("agente_responsavel")
            .prefetch_related(
                Prefetch("contratos", queryset=Contrato.objects.order_by("-created_at"))
            )
            .order_by("-created_at")
        )

        if search:
            digits = "".join(ch for ch in search if ch.isdigit())
            queryset = queryset.filter(
                Q(nome_completo__icontains=search)
                | Q(cpf_cnpj__icontains=digits or search)
                | Q(matricula__icontains=search)
                | Q(contratos__codigo__icontains=search)
            ).distinct()

        return queryset

    @staticmethod
    @transaction.atomic
    def atualizar_data_pagamento(pagamento_id: int, new_value: str):
        try:
            pagamento = Pagamento.objects.select_for_update().get(pk=pagamento_id)
        except Pagamento.DoesNotExist as exc:
            raise ValidationError("Pagamento não encontrado.") from exc

        if pagamento.status != Pagamento.Status.PAGO:
            raise ValidationError(
                'Somente pagamentos com status "pago" podem ser ajustados.'
            )

        raw = (new_value or "").strip()
        if not raw:
            raise ValidationError("A nova data do pagamento é obrigatória.")

        parsed: datetime
        try:
            if "T" in raw:
                parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
            else:
                parsed = datetime.strptime(raw, "%Y-%m-%d").replace(hour=12, minute=0)
        except ValueError as exc:
            raise ValidationError("Formato de data inválido.") from exc

        pagamento.paid_at = timezone.make_aware(
            parsed,
            timezone.get_current_timezone(),
        )
        pagamento.save(update_fields=["paid_at", "updated_at"])
        return pagamento

    @staticmethod
    @transaction.atomic
    def excluir_pagamento(pagamento_id: int):
        try:
            pagamento = Pagamento.objects.select_for_update().get(pk=pagamento_id)
        except Pagamento.DoesNotExist as exc:
            raise ValidationError("Pagamento não encontrado.") from exc

        if pagamento.status == Pagamento.Status.PAGO:
            raise ValidationError('Pagamentos com status "pago" não podem ser excluídos.')

        pagamento.delete()

    @staticmethod
    @transaction.atomic
    def atualizar_nome_associado(associado_id: int, nome_completo: str):
        try:
            associado = Associado.objects.select_related("contato_historico").get(pk=associado_id)
        except Associado.DoesNotExist as exc:
            raise ValidationError("Associado não encontrado.") from exc

        nome = (nome_completo or "").strip()
        if not nome:
            raise ValidationError("O nome completo é obrigatório.")

        associado.nome_completo = nome.upper()
        associado.save(update_fields=["nome_completo", "updated_at"])

        contato = associado._safe_related("contato_historico")
        if contato and contato.nome_contato:
            contato.nome_contato = associado.nome_completo
            contato.save(update_fields=["nome_contato", "updated_at"])

        return associado
