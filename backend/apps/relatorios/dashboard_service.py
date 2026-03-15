from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.associados.services import add_months
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.renovacao import RenovacaoCicloService
from apps.esteira.models import EsteiraItem
from apps.importacao.financeiro import canonicalize_pagamentos
from apps.importacao.models import PagamentoMensalidade


PROCESSING_ASSOCIADO_STATUSES = (
    Associado.Status.CADASTRADO,
    Associado.Status.EM_ANALISE,
    Associado.Status.PENDENTE,
)
IMPORT_OK_CODES = {"1", "4"}


def parse_competencia_query(value: str | None) -> date:
    if value:
        try:
            return datetime.strptime(value, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise ValidationError("Competencia invalida. Use o formato YYYY-MM.") from exc
    return timezone.localdate().replace(day=1)


def parse_date_query(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(
            f"{field_name} invalido. Use o formato YYYY-MM-DD."
        ) from exc


def month_label(value: date) -> str:
    return value.strftime("%m/%Y")


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


@dataclass(frozen=True)
class DashboardFilters:
    competencia: date
    date_start: date | None = None
    date_end: date | None = None
    agent_id: int | None = None
    status: str | None = None


class AdminDashboardService:
    @staticmethod
    def build_filters(*, competencia: str | None, date_start: str | None, date_end: str | None, agent_id: str | None, status: str | None) -> DashboardFilters:
        parsed_agent_id: int | None = None
        if agent_id:
            try:
                parsed_agent_id = int(agent_id)
            except ValueError as exc:
                raise ValidationError("agent_id invalido.") from exc

        return DashboardFilters(
            competencia=parse_competencia_query(competencia),
            date_start=parse_date_query(date_start, "date_start"),
            date_end=parse_date_query(date_end, "date_end"),
            agent_id=parsed_agent_id,
            status=(status or "").strip() or None,
        )

    @staticmethod
    def _format_metric_value(numeric_value: float | int | Decimal, value_format: str) -> str:
        if value_format == "currency":
            return f"{Decimal(str(numeric_value)):.2f}"
        return str(int(numeric_value))

    @staticmethod
    def _metric_card(
        *,
        key: str,
        label: str,
        numeric_value: float | int | Decimal,
        value_format: str = "integer",
        tone: str = "neutral",
        description: str = "",
        detail_metric: str,
    ) -> dict[str, object]:
        return {
            "key": key,
            "label": label,
            "value": AdminDashboardService._format_metric_value(numeric_value, value_format),
            "numeric_value": float(numeric_value),
            "format": value_format,
            "tone": tone,
            "description": description,
            "detail_metric": detail_metric,
        }

    @staticmethod
    def _associados_base(agent_id: int | None = None) -> QuerySet[Associado]:
        queryset = (
            Associado.objects.select_related("agente_responsavel", "esteira_item")
            .prefetch_related(
                Prefetch(
                    "contratos",
                    queryset=Contrato.objects.exclude(status=Contrato.Status.CANCELADO)
                    .select_related("agente")
                    .order_by("-created_at"),
                )
            )
            .distinct()
        )
        if agent_id:
            queryset = queryset.filter(
                Q(agente_responsavel_id=agent_id) | Q(contratos__agente_id=agent_id)
            ).distinct()
        return queryset

    @staticmethod
    def _contracts_base(agent_id: int | None = None) -> QuerySet[Contrato]:
        queryset = Contrato.objects.select_related(
            "agente",
            "associado",
            "associado__agente_responsavel",
            "associado__esteira_item",
        ).exclude(status=Contrato.Status.CANCELADO)
        if agent_id:
            queryset = queryset.filter(
                Q(agente_id=agent_id)
                | Q(agente__isnull=True, associado__agente_responsavel_id=agent_id)
            )
        return queryset

    @staticmethod
    def _payments_base(month: date, agent_id: int | None = None) -> list[PagamentoMensalidade]:
        queryset = PagamentoMensalidade.objects.filter(referencia_month=month).select_related(
            "associado",
            "associado__agente_responsavel",
        )
        if agent_id:
            queryset = queryset.filter(
                Q(associado__agente_responsavel_id=agent_id)
                | Q(associado__contratos__agente_id=agent_id)
            ).distinct()
        return canonicalize_pagamentos(list(queryset.order_by("id")))

    @staticmethod
    def _projection_parcelas(month: date, agent_id: int | None = None) -> QuerySet[Parcela]:
        queryset = Parcela.objects.select_related(
            "ciclo",
            "ciclo__contrato",
            "ciclo__contrato__agente",
            "ciclo__contrato__associado",
            "ciclo__contrato__associado__agente_responsavel",
            "ciclo__contrato__associado__esteira_item",
        ).filter(
            referencia_mes=month,
            status__in=[Parcela.Status.DESCONTADO, Parcela.Status.EM_ABERTO, Parcela.Status.FUTURO],
            ciclo__status__in=[Ciclo.Status.ABERTO, Ciclo.Status.APTO_A_RENOVAR, Ciclo.Status.FUTURO, Ciclo.Status.CICLO_RENOVADO],
            ciclo__contrato__status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO],
        )
        if agent_id:
            queryset = queryset.filter(
                Q(ciclo__contrato__agente_id=agent_id)
                | Q(
                    ciclo__contrato__agente__isnull=True,
                    ciclo__contrato__associado__agente_responsavel_id=agent_id,
                )
            )
        return queryset

    @staticmethod
    def _filter_renewal_rows_by_agent(rows: list[dict[str, object]], agent_id: int | None) -> list[dict[str, object]]:
        if not agent_id:
            return rows
        contract_ids = set(
            AdminDashboardService._contracts_base(agent_id).values_list("id", flat=True)
        )
        return [row for row in rows if row["contrato_id"] in contract_ids]

    @staticmethod
    def _filter_queryset_by_created_range(queryset, date_start: date | None, date_end: date | None):
        if date_start:
            queryset = queryset.filter(created_at__date__gte=date_start)
        if date_end:
            queryset = queryset.filter(created_at__date__lte=date_end)
        return queryset

    @staticmethod
    def _filter_queryset_by_field_range(queryset, field_name: str, date_start: date | None, date_end: date | None):
        if date_start:
            queryset = queryset.filter(**{f"{field_name}__gte": date_start})
        if date_end:
            queryset = queryset.filter(**{f"{field_name}__lte": date_end})
        return queryset

    @staticmethod
    def _filter_contracts_by_associado_status(queryset, status: str | None):
        if status:
            queryset = queryset.filter(associado__status=status)
        return queryset

    @staticmethod
    def _filter_renewal_rows_by_status(
        rows: list[dict[str, object]],
        status: str | None,
        agent_id: int | None = None,
    ) -> list[dict[str, object]]:
        if not status:
            return rows

        contract_ids = set(
            AdminDashboardService._contracts_base(agent_id)
            .filter(associado__status=status)
            .values_list("id", flat=True)
        )
        return [row for row in rows if row["contrato_id"] in contract_ids]

    @staticmethod
    def _resolve_contract_for_associado(associado: Associado) -> Contrato | None:
        contracts = getattr(associado, "_prefetched_objects_cache", {}).get("contratos")
        if contracts:
            return contracts[0]
        return associado.contratos.exclude(status=Contrato.Status.CANCELADO).select_related("agente").order_by("-created_at").first()

    @staticmethod
    def _resolve_agent_name(associado: Associado | None = None, contrato: Contrato | None = None) -> str:
        if contrato and contrato.agente:
            return contrato.agente.full_name
        if associado and associado.agente_responsavel:
            return associado.agente_responsavel.full_name
        if contrato and contrato.associado and contrato.associado.agente_responsavel:
            return contrato.associado.agente_responsavel.full_name
        return "Sem agente"

    @staticmethod
    def _resolve_etapa(associado: Associado | None, contrato: Contrato | None = None) -> str:
        if associado and getattr(associado, "esteira_item", None):
            return associado.esteira_item.etapa_atual
        if contrato and contrato.auxilio_liberado_em:
            return "concluido"
        return "-"

    @staticmethod
    def _detail_row_from_associado(
        associado: Associado,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
        competencia: date | None = None,
        data_referencia: date | None = None,
    ) -> dict[str, object]:
        contrato = AdminDashboardService._resolve_contract_for_associado(associado)
        return {
            "id": f"associado-{associado.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "-",
            "status": associado.status,
            "agente_nome": AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": contrato.codigo if contrato else "",
            "etapa": AdminDashboardService._resolve_etapa(associado, contrato),
            "competencia": month_label(competencia) if competencia else "",
            "valor": value_or_none(valor),
            "origem": origem,
            "data_referencia": data_referencia.isoformat() if data_referencia else "",
            "observacao": observacao,
        }

    @staticmethod
    def _detail_row_from_contract(
        contrato: Contrato,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
        competencia: date | None = None,
        data_referencia: date | None = None,
    ) -> dict[str, object]:
        associado = contrato.associado
        return {
            "id": f"contrato-{contrato.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "-",
            "status": associado.status,
            "agente_nome": AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": contrato.codigo,
            "etapa": AdminDashboardService._resolve_etapa(associado, contrato),
            "competencia": month_label(competencia) if competencia else "",
            "valor": value_or_none(valor if valor is not None else contrato.valor_mensalidade),
            "origem": origem,
            "data_referencia": data_referencia.isoformat() if data_referencia else contrato.data_contrato.isoformat(),
            "observacao": observacao,
        }

    @staticmethod
    def _detail_row_from_payment(
        payment: PagamentoMensalidade,
        *,
        origem: str,
        valor: Decimal,
        observacao: str,
    ) -> dict[str, object]:
        associado = payment.associado
        contrato = (
            AdminDashboardService._resolve_contract_for_associado(associado)
            if associado
            else None
        )
        associado_nome = associado.nome_completo if associado else payment.nome_relatorio or "-"
        cpf_cnpj = associado.cpf_cnpj if associado else payment.cpf_cnpj
        matricula = (
            associado.matricula_orgao or associado.matricula
            if associado
            else payment.matricula or "-"
        )
        status = associado.status if associado else "-"
        return {
            "id": f"pagamento-{payment.id}-{origem}",
            "associado_id": associado.id if associado else None,
            "associado_nome": associado_nome,
            "cpf_cnpj": cpf_cnpj,
            "matricula": matricula,
            "status": status,
            "agente_nome": AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": contrato.codigo if contrato else "",
            "etapa": AdminDashboardService._resolve_etapa(associado, contrato),
            "competencia": month_label(payment.referencia_month),
            "valor": value_or_none(valor),
            "origem": origem,
            "data_referencia": (
                payment.manual_paid_at.date().isoformat()
                if payment.manual_paid_at
                else payment.referencia_month.isoformat()
            ),
            "observacao": observacao,
        }

    @staticmethod
    def _detail_row_from_parcela(
        parcela: Parcela,
        *,
        origem: str,
        observacao: str = "",
    ) -> dict[str, object]:
        contrato = parcela.ciclo.contrato
        associado = contrato.associado
        return {
            "id": f"parcela-{parcela.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or contrato.codigo,
            "status": parcela.status,
            "agente_nome": AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": contrato.codigo,
            "etapa": AdminDashboardService._resolve_etapa(associado, contrato),
            "competencia": month_label(parcela.referencia_mes),
            "valor": value_or_none(parcela.valor),
            "origem": origem,
            "data_referencia": parcela.referencia_mes.isoformat(),
            "observacao": observacao,
        }

    @staticmethod
    def _detail_row_from_renewal_row(row: dict[str, object], *, origem: str) -> dict[str, object]:
        return {
            "id": f"renovacao-{row['id']}-{origem}",
            "associado_id": row["associado_id"],
            "associado_nome": row["nome_associado"],
            "cpf_cnpj": row["cpf_cnpj"],
            "matricula": row["matricula"],
            "status": row["status_visual"],
            "agente_nome": row["agente_responsavel"],
            "contrato_codigo": row["contrato_codigo"],
            "etapa": "renovacao",
            "competencia": str(row["competencia"]),
            "valor": value_or_none(Decimal(str(row.get("valor_parcela") or 0))),
            "origem": origem,
            "data_referencia": (
                row["data_pagamento"].isoformat()
                if isinstance(row.get("data_pagamento"), date)
                else ""
            ),
            "observacao": str(row.get("status_explicacao") or ""),
        }

    @staticmethod
    def _trend_months(end_month: date, count: int = 6) -> list[date]:
        start_month = add_months(end_month, -(count - 1))
        return [add_months(start_month, index) for index in range(count)]

    @staticmethod
    def resumo_geral(filters: DashboardFilters) -> dict[str, object]:
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            filters.date_start,
            filters.date_end,
        )
        if filters.status:
            associados = associados.filter(status=filters.status)

        total = associados.count()
        ativos = associados.filter(status=Associado.Status.ATIVO).count()
        em_processo = associados.filter(status__in=PROCESSING_ASSOCIADO_STATUSES).count()
        inadimplentes = associados.filter(status=Associado.Status.INADIMPLENTE).count()
        cadastros_pendentes = (
            associados.filter(esteira_item__isnull=False)
            .exclude(esteira_item__etapa_atual=EsteiraItem.Etapa.CONCLUIDO)
            .exclude(contratos__auxilio_liberado_em__isnull=False)
            .distinct()
            .count()
        )

        renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
            RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
            filters.agent_id,
        )
        renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
            renewal_rows,
            filters.status,
            filters.agent_id,
        )
        renovacoes = sum(
            1
            for row in renewal_rows
            if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
        )
        aptos_renovacao = sum(
            1 for row in renewal_rows if row["status_visual"] == "apto_a_renovar"
        )

        effective_contracts = AdminDashboardService._contracts_base(filters.agent_id).filter(
            auxilio_liberado_em__isnull=False
        )
        effective_contracts = AdminDashboardService._filter_contracts_by_associado_status(
            effective_contracts,
            filters.status,
        )
        if filters.date_start or filters.date_end:
            effective_contracts = AdminDashboardService._filter_queryset_by_field_range(
                effective_contracts,
                "auxilio_liberado_em",
                filters.date_start,
                filters.date_end,
            )

        pie_counts = {
            status_key: associados.filter(status=status_key).count()
            for status_key, _ in Associado.Status.choices
        }
        trend_points: list[dict[str, object]] = []
        for month in AdminDashboardService._trend_months(filters.competencia):
            month_associados = Associado.objects.filter(
                created_at__date__gte=month,
                created_at__date__lt=add_months(month, 1),
            )
            month_effectivados = Contrato.objects.exclude(
                auxilio_liberado_em__isnull=True
            ).filter(
                auxilio_liberado_em__gte=month,
                auxilio_liberado_em__lt=add_months(month, 1),
            )
            if filters.agent_id:
                month_associados = month_associados.filter(
                    Q(agente_responsavel_id=filters.agent_id)
                    | Q(contratos__agente_id=filters.agent_id)
                ).distinct()
                month_effectivados = month_effectivados.filter(
                    Q(agente_id=filters.agent_id)
                    | Q(
                        agente__isnull=True,
                        associado__agente_responsavel_id=filters.agent_id,
                    )
                )
            if filters.status:
                month_associados = month_associados.filter(status=filters.status)
                month_effectivados = month_effectivados.filter(associado__status=filters.status)
            month_renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
                RenovacaoCicloService.listar_detalhes(competencia=month),
                filters.agent_id,
            )
            month_renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
                month_renewal_rows,
                filters.status,
                filters.agent_id,
            )
            renewed_count = sum(
                1
                for row in month_renewal_rows
                if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
            )
            trend_points.append(
                {
                    "bucket": month_key(month),
                    "label": month_label(month),
                    "cadastros": month_associados.count(),
                    "efetivados": month_effectivados.distinct().count(),
                    "renovacoes": renewed_count,
                    "cadastros_metric": f"trend:cadastros:{month_key(month)}",
                    "efetivados_metric": f"trend:efetivados:{month_key(month)}",
                    "renovacoes_metric": f"trend:renovacoes:{month_key(month)}",
                }
            )

        return {
            "competencia": month_key(filters.competencia),
            "kpis": [
                AdminDashboardService._metric_card(
                    key="associados_cadastrados",
                    label="Associados cadastrados",
                    numeric_value=total,
                    detail_metric="associados_cadastrados",
                    description="Base total de associados no recorte atual.",
                ),
                AdminDashboardService._metric_card(
                    key="associados_ativos",
                    label="Associados ativos",
                    numeric_value=ativos,
                    tone="positive",
                    detail_metric="associados_ativos",
                    description="Associados com status ativo.",
                ),
                AdminDashboardService._metric_card(
                    key="em_processo_efetivacao",
                    label="Em processo de efetivacao",
                    numeric_value=em_processo,
                    tone="warning",
                    detail_metric="em_processo_efetivacao",
                    description="Cadastros ainda em andamento ate a efetivacao.",
                ),
                AdminDashboardService._metric_card(
                    key="inadimplentes",
                    label="Inadimplentes",
                    numeric_value=inadimplentes,
                    tone="danger",
                    detail_metric="inadimplentes",
                    description="Associados marcados como inadimplentes.",
                ),
                AdminDashboardService._metric_card(
                    key="renovacoes_ciclo",
                    label="Renovacoes de ciclo",
                    numeric_value=renovacoes,
                    tone="positive",
                    detail_metric="renovacoes_ciclo",
                    description="Ciclos renovados na competencia selecionada.",
                ),
                AdminDashboardService._metric_card(
                    key="aptos_renovacao",
                    label="Aptos a renovacao",
                    numeric_value=aptos_renovacao,
                    detail_metric="aptos_renovacao",
                    description="Associados prontos para abrir novo ciclo.",
                ),
                AdminDashboardService._metric_card(
                    key="cadastros_pendentes",
                    label="Cadastros pendentes",
                    numeric_value=cadastros_pendentes,
                    tone="warning",
                    detail_metric="cadastros_pendentes",
                    description="Itens ainda em esteira sem conclusao.",
                ),
            ],
            "flow_bars": [
                {
                    "key": "cadastrado",
                    "label": "Cadastrado",
                    "value": associados.filter(status=Associado.Status.CADASTRADO).count(),
                    "detail_metric": "status:cadastrado",
                },
                {
                    "key": "em_analise",
                    "label": "Em analise",
                    "value": associados.filter(status=Associado.Status.EM_ANALISE).count(),
                    "detail_metric": "status:em_analise",
                },
                {
                    "key": "em_processo",
                    "label": "Em processo",
                    "value": em_processo,
                    "detail_metric": "em_processo_efetivacao",
                },
                {
                    "key": "efetivados",
                    "label": "Efetivados",
                    "value": effective_contracts.distinct().count(),
                    "detail_metric": "efetivados",
                },
                {
                    "key": "renovacoes",
                    "label": "Renovados",
                    "value": renovacoes,
                    "detail_metric": "renovacoes_ciclo",
                },
            ],
            "status_pie": [
                {
                    "key": status_key,
                    "label": status_label,
                    "value": pie_counts[status_key],
                    "detail_metric": f"status:{status_key}",
                }
                for status_key, status_label in Associado.Status.choices
                if pie_counts[status_key] > 0
            ],
            "trend_lines": trend_points,
        }

    @staticmethod
    def _payment_value(payment: PagamentoMensalidade) -> Decimal:
        if payment.manual_status == PagamentoMensalidade.ManualStatus.PAGO:
            return payment.recebido_manual or payment.valor or Decimal("0.00")
        if (payment.status_code or "").strip() in IMPORT_OK_CODES:
            return payment.valor or Decimal("0.00")
        return Decimal("0.00")

    @staticmethod
    def _payment_is_manual(payment: PagamentoMensalidade) -> bool:
        return payment.manual_status == PagamentoMensalidade.ManualStatus.PAGO

    @staticmethod
    def _payment_is_imported(payment: PagamentoMensalidade) -> bool:
        return (payment.status_code or "").strip() in IMPORT_OK_CODES and not AdminDashboardService._payment_is_manual(payment)

    @staticmethod
    def _payment_is_ok(payment: PagamentoMensalidade) -> bool:
        return AdminDashboardService._payment_is_manual(payment) or AdminDashboardService._payment_is_imported(payment)

    @staticmethod
    def tesouraria(filters: DashboardFilters) -> dict[str, object]:
        payments = list(AdminDashboardService._payments_base(filters.competencia, filters.agent_id))
        received_value = sum(
            (AdminDashboardService._payment_value(payment) for payment in payments),
            Decimal("0.00"),
        )
        import_count = sum(1 for payment in payments if AdminDashboardService._payment_is_imported(payment))
        manual_count = sum(1 for payment in payments if AdminDashboardService._payment_is_manual(payment))
        inadimplentes_quitados = sum(
            1
            for payment in payments
            if AdminDashboardService._payment_is_ok(payment)
            and payment.associado
            and payment.associado.status == Associado.Status.INADIMPLENTE
        )

        contracts_month = AdminDashboardService._contracts_base(filters.agent_id).filter(
            data_contrato__year=filters.competencia.year,
            data_contrato__month=filters.competencia.month,
        )
        new_contracts = contracts_month.count()

        projection_points: list[dict[str, object]] = []
        projection_total = Decimal("0.00")
        pending_current = Decimal("0.00")
        future_projection = Decimal("0.00")
        for index in range(3):
            month = add_months(filters.competencia, index)
            parcelas = list(AdminDashboardService._projection_parcelas(month, filters.agent_id))
            projected_value = sum((parcela.valor for parcela in parcelas), Decimal("0.00"))
            month_received = sum(
                (
                    AdminDashboardService._payment_value(payment)
                    for payment in AdminDashboardService._payments_base(month, filters.agent_id)
                ),
                Decimal("0.00"),
            )
            projection_total += projected_value
            if index == 0:
                pending_current = max(projected_value - month_received, Decimal("0.00"))
            else:
                future_projection += projected_value
            projection_points.append(
                {
                    "bucket": month_key(month),
                    "label": month_label(month),
                    "recebido": float(month_received),
                    "projetado": float(projected_value),
                    "recebido_metric": f"recebido:{month_key(month)}",
                    "projetado_metric": f"projetado:{month_key(month)}",
                }
            )

        return {
            "competencia": month_key(filters.competencia),
            "cards": [
                AdminDashboardService._metric_card(
                    key="valores_recebidos",
                    label="Valores recebidos",
                    numeric_value=received_value,
                    value_format="currency",
                    tone="positive",
                    detail_metric="valores_recebidos",
                    description="Recebimentos consolidados da competencia.",
                ),
                AdminDashboardService._metric_card(
                    key="baixas_importacao",
                    label="Baixas por importacao",
                    numeric_value=import_count,
                    tone="neutral",
                    detail_metric="baixas_importacao",
                    description="Pagamentos conciliados automaticamente.",
                ),
                AdminDashboardService._metric_card(
                    key="baixas_manuais",
                    label="Baixas manuais",
                    numeric_value=manual_count,
                    tone="warning",
                    detail_metric="baixas_manuais",
                    description="Pagamentos liquidados por baixa manual.",
                ),
                AdminDashboardService._metric_card(
                    key="inadimplentes_quitados",
                    label="Inadimplentes quitados",
                    numeric_value=inadimplentes_quitados,
                    tone="positive",
                    detail_metric="inadimplentes_quitados",
                    description="Associados inadimplentes que quitaram na competencia.",
                ),
                AdminDashboardService._metric_card(
                    key="contratos_novos",
                    label="Contratos novos",
                    numeric_value=new_contracts,
                    detail_metric="contratos_novos",
                    description="Contratos criados no mes filtrado.",
                ),
                AdminDashboardService._metric_card(
                    key="projecao_total",
                    label="Projecao competencia + 2 ciclos",
                    numeric_value=projection_total,
                    value_format="currency",
                    tone="neutral",
                    detail_metric="projecao_total",
                    description="Receita esperada para o mes e dois ciclos seguintes.",
                ),
            ],
            "projection_area": projection_points,
            "movement_bars": [
                {
                    "key": "importacao",
                    "label": "Importacao",
                    "value": import_count,
                    "detail_metric": "baixas_importacao",
                },
                {
                    "key": "manual",
                    "label": "Manual",
                    "value": manual_count,
                    "detail_metric": "baixas_manuais",
                },
                {
                    "key": "inadimplentes_quitados",
                    "label": "Inadimplentes quitados",
                    "value": inadimplentes_quitados,
                    "detail_metric": "inadimplentes_quitados",
                },
                {
                    "key": "contratos_novos",
                    "label": "Contratos novos",
                    "value": new_contracts,
                    "detail_metric": "contratos_novos",
                },
            ],
            "composition_radial": [
                {
                    "key": "recebido_atual",
                    "label": "Recebido",
                    "value": float(received_value),
                    "detail_metric": "valores_recebidos",
                },
                {
                    "key": "pendente_atual",
                    "label": "Pendente",
                    "value": float(pending_current),
                    "detail_metric": "pendente_atual",
                },
                {
                    "key": "futuro",
                    "label": "Projecao futura",
                    "value": float(future_projection),
                    "detail_metric": "projecao_futura",
                },
            ],
        }

    @staticmethod
    def _resolved_date_window(date_start: date | None, date_end: date | None) -> tuple[date, date]:
        today = timezone.localdate()
        if not date_start and not date_end:
            return today.replace(day=1), today
        return date_start or today.replace(day=1), date_end or today

    @staticmethod
    def novos_associados(filters: DashboardFilters) -> dict[str, object]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
        )
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            date_start,
            date_end,
        )
        if filters.status:
            associados = associados.filter(status=filters.status)

        total = associados.count()
        ativos = associados.filter(status=Associado.Status.ATIVO).count()
        em_processo = associados.filter(status__in=PROCESSING_ASSOCIADO_STATUSES).count()
        inadimplentes = associados.filter(status=Associado.Status.INADIMPLENTE).count()

        months = []
        current_month = date_start.replace(day=1)
        end_month = date_end.replace(day=1)
        while current_month <= end_month:
            months.append(current_month)
            current_month = add_months(current_month, 1)

        trend_points: list[dict[str, object]] = []
        for month in months:
            bucket_associados = associados.filter(
                created_at__date__gte=month,
                created_at__date__lt=add_months(month, 1),
            )
            bucket_effectivados = associados.filter(
                contratos__auxilio_liberado_em__gte=month,
                contratos__auxilio_liberado_em__lt=add_months(month, 1),
            ).distinct()
            trend_points.append(
                {
                    "bucket": month_key(month),
                    "label": month_label(month),
                    "cadastros": bucket_associados.count(),
                    "efetivados": bucket_effectivados.count(),
                    "cadastros_metric": f"cadastros:{month_key(month)}",
                    "efetivados_metric": f"efetivados:{month_key(month)}",
                }
            )

        return {
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "cards": [
                AdminDashboardService._metric_card(
                    key="novos_cadastrados",
                    label="Novos cadastrados",
                    numeric_value=total,
                    detail_metric="novos_cadastrados",
                    description="Associados criados dentro do periodo.",
                ),
                AdminDashboardService._metric_card(
                    key="novos_ativos",
                    label="Novos ativos",
                    numeric_value=ativos,
                    tone="positive",
                    detail_metric="novos_ativos",
                    description="Novos associados ja ativos.",
                ),
                AdminDashboardService._metric_card(
                    key="novos_em_processo",
                    label="Novos em processo",
                    numeric_value=em_processo,
                    tone="warning",
                    detail_metric="novos_em_processo",
                    description="Novos associados ainda em andamento.",
                ),
                AdminDashboardService._metric_card(
                    key="novos_inadimplentes",
                    label="Novos inadimplentes",
                    numeric_value=inadimplentes,
                    tone="danger",
                    detail_metric="novos_inadimplentes",
                    description="Novos associados ja marcados como inadimplentes.",
                ),
            ],
            "trend_area": trend_points,
            "status_pie": [
                {
                    "key": status_key,
                    "label": status_label,
                    "value": associados.filter(status=status_key).count(),
                    "detail_metric": f"status:{status_key}",
                }
                for status_key, status_label in Associado.Status.choices
                if associados.filter(status=status_key).exists()
            ],
        }

    @staticmethod
    def agentes(filters: DashboardFilters) -> dict[str, object]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
        )
        agents = (
            User.objects.filter(
                Q(roles__codigo="AGENTE")
                | Q(associados_cadastrados__isnull=False)
                | Q(contratos_agenciados__isnull=False)
            )
            .distinct()
            .order_by("first_name", "last_name", "email")
        )
        if filters.agent_id:
            agents = agents.filter(id=filters.agent_id)

        ranking: list[dict[str, object]] = []
        for agent in agents:
            cadastros = Associado.objects.filter(
                agente_responsavel=agent,
                created_at__date__gte=date_start,
                created_at__date__lte=date_end,
            )
            em_processo = cadastros.filter(status__in=PROCESSING_ASSOCIADO_STATUSES)
            inadimplentes = Associado.objects.filter(
                agente_responsavel=agent,
                status=Associado.Status.INADIMPLENTE,
            )
            efetivados = AdminDashboardService._contracts_base(agent.id).filter(
                auxilio_liberado_em__gte=date_start,
                auxilio_liberado_em__lte=date_end,
                auxilio_liberado_em__isnull=False,
            ).distinct()
            renovados = Ciclo.objects.filter(
                status=Ciclo.Status.CICLO_RENOVADO,
                data_fim__gte=date_start.replace(day=1),
                data_fim__lte=date_end,
            ).filter(
                Q(contrato__agente=agent)
                | Q(
                    contrato__agente__isnull=True,
                    contrato__associado__agente_responsavel=agent,
                )
            )
            metrics_total = (
                cadastros.count()
                + em_processo.count()
                + inadimplentes.count()
                + efetivados.count()
                + renovados.count()
            )
            if metrics_total == 0 and not agent.has_role("AGENTE"):
                continue
            ranking.append(
                {
                    "agent_id": agent.id,
                    "agent_name": agent.full_name or agent.email,
                    "efetivados": efetivados.count(),
                    "cadastros": cadastros.count(),
                    "em_processo": em_processo.count(),
                    "renovados": renovados.count(),
                    "inadimplentes": inadimplentes.count(),
                }
            )

        ranking.sort(key=lambda item: (-item["efetivados"], item["agent_name"]))
        total_efetivados = sum(item["efetivados"] for item in ranking)
        for item in ranking:
            item["participacao"] = round(
                ((item["efetivados"] / total_efetivados) * 100) if total_efetivados else 0,
                1,
            )
            item["detail_metric"] = f"agente:{item['agent_id']}:efetivados"

        top_agent = ranking[0] if ranking else None
        avg_efetivados = round(total_efetivados / len(ranking), 1) if ranking else 0.0

        return {
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "cards": [
                AdminDashboardService._metric_card(
                    key="agentes_no_ranking",
                    label="Agentes monitorados",
                    numeric_value=len(ranking),
                    detail_metric="agentes_no_ranking",
                    description="Quantidade de agentes com dados no periodo.",
                ),
                AdminDashboardService._metric_card(
                    key="top_agente_efetivacoes",
                    label="Top agente",
                    numeric_value=top_agent["efetivados"] if top_agent else 0,
                    tone="positive",
                    detail_metric=top_agent["detail_metric"] if top_agent else "agentes_no_ranking",
                    description=top_agent["agent_name"] if top_agent else "Sem agente no periodo",
                ),
                AdminDashboardService._metric_card(
                    key="efetivacoes_total",
                    label="Efetivacoes totais",
                    numeric_value=total_efetivados,
                    tone="positive",
                    detail_metric="efetivacoes_total",
                    description="Soma das efetivacoes atribuidas aos agentes.",
                ),
                AdminDashboardService._metric_card(
                    key="media_efetivacoes",
                    label="Media por agente",
                    numeric_value=avg_efetivados,
                    detail_metric="media_efetivacoes",
                    description="Media de efetivacoes entre os agentes ranqueados.",
                ),
            ],
            "ranking": ranking[:8],
        }

    @staticmethod
    def detalhes(filters: DashboardFilters, *, section: str, metric: str) -> list[dict[str, object]]:
        if section == "summary":
            return AdminDashboardService._summary_details(filters, metric)
        if section == "treasury":
            return AdminDashboardService._treasury_details(filters, metric)
        if section == "new-associados":
            return AdminDashboardService._new_associados_details(filters, metric)
        if section == "agentes":
            return AdminDashboardService._agents_details(filters, metric)
        raise ValidationError("section invalido.")

    @staticmethod
    def _summary_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            filters.date_start,
            filters.date_end,
        )
        if filters.status:
            associados = associados.filter(status=filters.status)
        contracts = AdminDashboardService._contracts_base(filters.agent_id)
        contracts = AdminDashboardService._filter_contracts_by_associado_status(
            contracts,
            filters.status,
        )
        renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
            RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
            filters.agent_id,
        )
        renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
            renewal_rows,
            filters.status,
            filters.agent_id,
        )

        if metric == "associados_cadastrados":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Associado cadastrado")
                for associado in associados
            ]
        if metric == "associados_ativos":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Associado ativo")
                for associado in associados.filter(status=Associado.Status.ATIVO)
            ]
        if metric == "em_processo_efetivacao":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Em processo de efetivacao")
                for associado in associados.filter(status__in=PROCESSING_ASSOCIADO_STATUSES)
            ]
        if metric == "inadimplentes":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Associado inadimplente")
                for associado in associados.filter(status=Associado.Status.INADIMPLENTE)
            ]
        if metric == "cadastros_pendentes":
            return [
                AdminDashboardService._detail_row_from_associado(
                    associado,
                    origem="Cadastro pendente",
                    observacao="Associado ainda possui item em esteira sem conclusao.",
                )
                for associado in associados.filter(esteira_item__isnull=False)
                .exclude(esteira_item__etapa_atual=EsteiraItem.Etapa.CONCLUIDO)
                .exclude(contratos__auxilio_liberado_em__isnull=False)
                .distinct()
            ]
        if metric == "efetivados":
            effective_contracts = contracts.filter(auxilio_liberado_em__isnull=False).distinct()
            if filters.date_start or filters.date_end:
                effective_contracts = AdminDashboardService._filter_queryset_by_field_range(
                    effective_contracts,
                    "auxilio_liberado_em",
                    filters.date_start,
                    filters.date_end,
                )
            return [
                AdminDashboardService._detail_row_from_contract(
                    contrato,
                    origem="Contrato efetivado",
                    data_referencia=contrato.auxilio_liberado_em,
                )
                for contrato in effective_contracts
            ]
        if metric == "renovacoes_ciclo":
            return [
                AdminDashboardService._detail_row_from_renewal_row(row, origem="Ciclo renovado")
                for row in renewal_rows
                if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
            ]
        if metric == "aptos_renovacao":
            return [
                AdminDashboardService._detail_row_from_renewal_row(row, origem="Apto a renovacao")
                for row in renewal_rows
                if row["status_visual"] == "apto_a_renovar"
            ]
        if metric.startswith("status:"):
            status = metric.split(":", 1)[1]
            return [
                AdminDashboardService._detail_row_from_associado(
                    associado,
                    origem=f"Status {status}",
                )
                for associado in associados.filter(status=status)
            ]
        if metric.startswith("trend:"):
            _, trend_key, bucket = metric.split(":")
            month = parse_competencia_query(bucket)
            if trend_key == "cadastros":
                month_associados = AdminDashboardService._associados_base(filters.agent_id).filter(
                    created_at__date__gte=month,
                    created_at__date__lt=add_months(month, 1),
                )
                if filters.status:
                    month_associados = month_associados.filter(status=filters.status)
                return [
                    AdminDashboardService._detail_row_from_associado(
                        associado,
                        origem=f"Cadastro {month_label(month)}",
                    )
                    for associado in month_associados
                ]
            if trend_key == "efetivados":
                contracts = AdminDashboardService._contracts_base(filters.agent_id).filter(
                    auxilio_liberado_em__gte=month,
                    auxilio_liberado_em__lt=add_months(month, 1),
                    auxilio_liberado_em__isnull=False,
                )
                contracts = AdminDashboardService._filter_contracts_by_associado_status(
                    contracts,
                    filters.status,
                )
                return [
                    AdminDashboardService._detail_row_from_contract(
                        contrato,
                        origem=f"Efetivacao {month_label(month)}",
                        data_referencia=contrato.auxilio_liberado_em,
                    )
                    for contrato in contracts.distinct()
                ]
            if trend_key == "renovacoes":
                month_rows = AdminDashboardService._filter_renewal_rows_by_agent(
                    RenovacaoCicloService.listar_detalhes(competencia=month),
                    filters.agent_id,
                )
                month_rows = AdminDashboardService._filter_renewal_rows_by_status(
                    month_rows,
                    filters.status,
                    filters.agent_id,
                )
                return [
                    AdminDashboardService._detail_row_from_renewal_row(row, origem=f"Renovacao {month_label(month)}")
                    for row in month_rows
                    if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
                ]
        return []

    @staticmethod
    def _treasury_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        def ok_rows_for_month(month: date) -> list[PagamentoMensalidade]:
            return [
                payment
                for payment in AdminDashboardService._payments_base(month, filters.agent_id)
                if AdminDashboardService._payment_is_ok(payment)
            ]

        payments = list(AdminDashboardService._payments_base(filters.competencia, filters.agent_id))
        if metric == "valores_recebidos":
            return [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Valor recebido",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Baixa consolidada na tesouraria.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_ok(payment)
            ]
        if metric == "baixas_importacao":
            return [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Baixa por importacao",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Pagamento conciliado automaticamente.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_imported(payment)
            ]
        if metric == "baixas_manuais":
            return [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Baixa manual",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Pagamento confirmado manualmente.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_manual(payment)
            ]
        if metric == "inadimplentes_quitados":
            return [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Inadimplente quitado",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Associado inadimplente com baixa concluida.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_ok(payment)
                and payment.associado
                and payment.associado.status == Associado.Status.INADIMPLENTE
            ]
        if metric == "contratos_novos":
            contracts = AdminDashboardService._contracts_base(filters.agent_id).filter(
                data_contrato__year=filters.competencia.year,
                data_contrato__month=filters.competencia.month,
            )
            return [
                AdminDashboardService._detail_row_from_contract(
                    contrato,
                    origem="Contrato novo",
                    data_referencia=contrato.data_contrato,
                )
                for contrato in contracts
            ]
        if metric == "projecao_total":
            rows: list[dict[str, object]] = []
            for index in range(3):
                month = add_months(filters.competencia, index)
                rows.extend(
                    [
                        AdminDashboardService._detail_row_from_parcela(
                            parcela,
                            origem=f"Projecao {month_label(month)}",
                        )
                        for parcela in AdminDashboardService._projection_parcelas(month, filters.agent_id)
                    ]
                )
            return rows
        if metric == "pendente_atual":
            month = filters.competencia
            received_contracts = {row["contrato_codigo"] for row in AdminDashboardService._treasury_details(filters, "valores_recebidos")}
            return [
                AdminDashboardService._detail_row_from_parcela(
                    parcela,
                    origem="Pendente competencia atual",
                    observacao="Parcela esperada sem baixa consolidada.",
                )
                for parcela in AdminDashboardService._projection_parcelas(month, filters.agent_id)
                if parcela.ciclo.contrato.codigo not in received_contracts
            ]
        if metric == "projecao_futura":
            rows: list[dict[str, object]] = []
            for index in range(1, 3):
                month = add_months(filters.competencia, index)
                rows.extend(
                    [
                        AdminDashboardService._detail_row_from_parcela(
                            parcela,
                            origem=f"Projecao futura {month_label(month)}",
                        )
                        for parcela in AdminDashboardService._projection_parcelas(month, filters.agent_id)
                    ]
                )
            return rows
        if metric.startswith("recebido:"):
            month = parse_competencia_query(metric.split(":", 1)[1])
            return [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem=f"Recebido {month_label(month)}",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Recebimento consolidado na serie de tesouraria.",
                )
                for payment in ok_rows_for_month(month)
            ]
        if metric.startswith("projetado:"):
            month = parse_competencia_query(metric.split(":", 1)[1])
            return [
                AdminDashboardService._detail_row_from_parcela(
                    parcela,
                    origem=f"Projecao {month_label(month)}",
                )
                for parcela in AdminDashboardService._projection_parcelas(month, filters.agent_id)
            ]
        return []

    @staticmethod
    def _new_associados_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
        )
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            date_start,
            date_end,
        )
        if filters.status:
            associados = associados.filter(status=filters.status)
        if metric == "novos_cadastrados":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Novo associado")
                for associado in associados
            ]
        if metric == "novos_ativos":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Novo associado ativo")
                for associado in associados.filter(status=Associado.Status.ATIVO)
            ]
        if metric == "novos_em_processo":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Novo associado em processo")
                for associado in associados.filter(status__in=PROCESSING_ASSOCIADO_STATUSES)
            ]
        if metric == "novos_inadimplentes":
            return [
                AdminDashboardService._detail_row_from_associado(associado, origem="Novo associado inadimplente")
                for associado in associados.filter(status=Associado.Status.INADIMPLENTE)
            ]
        if metric.startswith("status:"):
            status = metric.split(":", 1)[1]
            return [
                AdminDashboardService._detail_row_from_associado(
                    associado,
                    origem=f"Novo associado {status}",
                )
                for associado in associados.filter(status=status)
            ]
        if metric.startswith("cadastros:"):
            month = parse_competencia_query(metric.split(":", 1)[1])
            return [
                AdminDashboardService._detail_row_from_associado(
                    associado,
                    origem=f"Cadastro {month_label(month)}",
                )
                for associado in associados.filter(
                    created_at__date__gte=month,
                    created_at__date__lt=add_months(month, 1),
                )
            ]
        if metric.startswith("efetivados:"):
            month = parse_competencia_query(metric.split(":", 1)[1])
            return [
                AdminDashboardService._detail_row_from_associado(
                    associado,
                    origem=f"Efetivado {month_label(month)}",
                )
                for associado in associados.filter(
                    contratos__auxilio_liberado_em__gte=month,
                    contratos__auxilio_liberado_em__lt=add_months(month, 1),
                ).distinct()
            ]
        return []

    @staticmethod
    def _agents_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
        )
        if metric == "agentes_no_ranking":
            return [
                {
                    "id": f"agente-{item['agent_id']}",
                    "associado_id": None,
                    "associado_nome": item["agent_name"],
                    "cpf_cnpj": "",
                    "matricula": "",
                    "status": "agente",
                    "agente_nome": item["agent_name"],
                    "contrato_codigo": "",
                    "etapa": "ranking",
                    "competencia": "",
                    "valor": value_or_none(Decimal(str(item["efetivados"]))),
                    "origem": "Agente no ranking",
                    "data_referencia": "",
                    "observacao": "Agente com atividade no periodo.",
                }
                for item in AdminDashboardService.agentes(filters)["ranking"]
            ]
        if metric in {"efetivacoes_total", "media_efetivacoes"}:
            rows: list[dict[str, object]] = []
            for item in AdminDashboardService.agentes(filters)["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:efetivados",
                    )
                )
            return rows
        if metric.startswith("agente:"):
            _, agent_id, metric_key = metric.split(":")
            agent_filters = DashboardFilters(
                competencia=filters.competencia,
                date_start=date_start,
                date_end=date_end,
                agent_id=int(agent_id),
                status=filters.status,
            )
            if metric_key == "efetivados":
                contracts = AdminDashboardService._contracts_base(int(agent_id)).filter(
                    auxilio_liberado_em__gte=date_start,
                    auxilio_liberado_em__lte=date_end,
                    auxilio_liberado_em__isnull=False,
                ).distinct()
                return [
                    AdminDashboardService._detail_row_from_contract(
                        contrato,
                        origem="Efetivacao do agente",
                        data_referencia=contrato.auxilio_liberado_em,
                    )
                    for contrato in contracts
                ]
            if metric_key == "cadastros":
                associados = AdminDashboardService._associados_base(int(agent_id)).filter(
                    agente_responsavel_id=int(agent_id),
                    created_at__date__gte=date_start,
                    created_at__date__lte=date_end,
                )
                return [
                    AdminDashboardService._detail_row_from_associado(
                        associado,
                        origem="Cadastro do agente",
                    )
                    for associado in associados
                ]
            if metric_key == "renovados":
                rows = AdminDashboardService._filter_renewal_rows_by_agent(
                    RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
                    int(agent_id),
                )
                return [
                    AdminDashboardService._detail_row_from_renewal_row(
                        row,
                        origem="Renovacao do agente",
                    )
                    for row in rows
                    if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
                ]
            if metric_key == "em_processo":
                associados = AdminDashboardService._associados_base(int(agent_id)).filter(
                    agente_responsavel_id=int(agent_id),
                    created_at__date__gte=date_start,
                    created_at__date__lte=date_end,
                    status__in=PROCESSING_ASSOCIADO_STATUSES,
                )
                return [
                    AdminDashboardService._detail_row_from_associado(
                        associado,
                        origem="Em processo do agente",
                    )
                    for associado in associados
                ]
            if metric_key == "inadimplentes":
                associados = AdminDashboardService._associados_base(int(agent_id)).filter(
                    agente_responsavel_id=int(agent_id),
                    status=Associado.Status.INADIMPLENTE,
                )
                return [
                    AdminDashboardService._detail_row_from_associado(
                        associado,
                        origem="Inadimplencia do agente",
                    )
                    for associado in associados
                ]
            return AdminDashboardService._agents_details(agent_filters, f"agente:{agent_id}:efetivados")
        return []


def value_or_none(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{Decimal(str(value)):.2f}"
