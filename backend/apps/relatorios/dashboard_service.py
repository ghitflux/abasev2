from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, IntegerField, OuterRef, Prefetch, Q, QuerySet, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.associados.models import Associado
from apps.associados.services import add_months
from apps.contratos.canonicalization import (
    operational_contracts_queryset,
    resolve_operational_contract_for_associado,
)
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.contratos.renovacao import RenovacaoCicloService
from apps.esteira.models import EsteiraItem
from apps.financeiro.models import Despesa
from apps.importacao.financeiro import canonicalize_pagamentos
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Refinanciamento
from apps.tesouraria.models import (
    DevolucaoAssociado,
    LiquidacaoContrato,
    Pagamento as TesourariaPagamento,
)


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
    day: date | None = None
    agent_id: int | None = None
    status: str | None = None


class AdminDashboardService:
    _RENEWAL_ID_PATTERN = re.compile(r"refi\s*#(\d+)", re.IGNORECASE)

    @staticmethod
    def build_filters(
        *,
        competencia: str | None,
        date_start: str | None,
        date_end: str | None,
        day: str | None,
        agent_id: str | None,
        status: str | None,
    ) -> DashboardFilters:
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
            day=parse_date_query(day, "day"),
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
                    queryset=operational_contracts_queryset(
                        Contrato.objects.exclude(status=Contrato.Status.CANCELADO)
                    )
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
        queryset = operational_contracts_queryset(
            Contrato.objects.select_related(
                "agente",
                "associado",
                "associado__agente_responsavel",
                "associado__esteira_item",
            ).exclude(status=Contrato.Status.CANCELADO)
        )
        if agent_id:
            queryset = queryset.filter(
                Q(agente_id=agent_id)
                | Q(agente__isnull=True, associado__agente_responsavel_id=agent_id)
            )
        return queryset

    @staticmethod
    def _payments_base(
        month: date,
        agent_id: int | None = None,
        status: str | None = None,
    ) -> list[PagamentoMensalidade]:
        queryset = PagamentoMensalidade.objects.filter(referencia_month=month).select_related(
            "associado",
            "associado__agente_responsavel",
        )
        if agent_id:
            queryset = queryset.filter(
                Q(associado__agente_responsavel_id=agent_id)
                | Q(associado__contratos__agente_id=agent_id)
            ).distinct()
        if status:
            queryset = queryset.filter(associado__status=status)
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
    def _validate_day_with_competencia(filters: DashboardFilters, *, section: str):
        if not filters.day:
            return
        if filters.day.replace(day=1) != filters.competencia:
            raise ValidationError(
                {
                    "day": (
                        f"O filtro day precisa pertencer a mesma competência selecionada "
                        f"para {section}."
                    )
                }
            )

    @staticmethod
    def _matches_day(value: date | datetime | None, day: date | None) -> bool:
        if not day:
            return True
        if value is None:
            return False
        if isinstance(value, datetime):
            return value.date() == day
        return value == day

    @staticmethod
    def _payment_matches_day(payment: PagamentoMensalidade, day: date | None) -> bool:
        if not day:
            return True
        return bool(payment.manual_paid_at and payment.manual_paid_at.date() == day)

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
        return resolve_operational_contract_for_associado(associado)

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
            "data_nascimento": associado.data_nascimento.isoformat() if associado.data_nascimento else "",
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
            "data_nascimento": associado.data_nascimento.isoformat() if associado.data_nascimento else "",
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
    def _detail_row_from_liquidacao(
        liquidacao: LiquidacaoContrato,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
    ) -> dict[str, object]:
        contrato = liquidacao.contrato
        associado = contrato.associado
        return {
            "id": f"liquidacao-{liquidacao.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "-",
            "status": associado.status,
            "agente_nome": AdminDashboardService._resolve_agent_name(
                associado=associado,
                contrato=contrato,
            ),
            "contrato_codigo": contrato.codigo,
            "etapa": "liquidacao",
            "competencia": month_label(liquidacao.data_liquidacao.replace(day=1)),
            "valor": value_or_none(valor if valor is not None else liquidacao.valor_total),
            "origem": origem,
            "data_referencia": liquidacao.data_liquidacao.isoformat(),
            "observacao": observacao or liquidacao.observacao,
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
    def _detail_row_from_tesouraria_pagamento(
        pagamento: TesourariaPagamento,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
        valor_associado: Decimal | None = None,
        valor_agente: Decimal | None = None,
        valor_total: Decimal | None = None,
    ) -> dict[str, object]:
        associado = pagamento.cadastro
        contrato = AdminDashboardService._resolve_contract_for_associado(associado)
        paid_at = pagamento.paid_at.date() if pagamento.paid_at else None
        payload = {
            "id": f"tesouraria-pagamento-{pagamento.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "-",
            "status": pagamento.status,
            "agente_nome": AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": pagamento.contrato_codigo or (contrato.codigo if contrato else ""),
            "etapa": "tesouraria",
            "competencia": month_label(paid_at.replace(day=1)) if paid_at else "",
            "valor": value_or_none(valor if valor is not None else pagamento.valor_pago),
            "origem": origem,
            "data_referencia": paid_at.isoformat() if paid_at else "",
            "observacao": observacao,
        }
        if valor_associado is not None:
            payload["valor_associado"] = value_or_none(valor_associado)
        if valor_agente is not None:
            payload["valor_agente"] = value_or_none(valor_agente)
        if valor_total is not None:
            payload["valor_total"] = value_or_none(valor_total)
        return payload

    @staticmethod
    def _detail_row_from_devolucao(
        devolucao: DevolucaoAssociado,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
    ) -> dict[str, object]:
        associado = devolucao.associado
        contrato = devolucao.contrato
        return {
            "id": f"devolucao-{devolucao.id}-{origem}",
            "associado_id": associado.id,
            "associado_nome": devolucao.nome_snapshot or associado.nome_completo,
            "cpf_cnpj": devolucao.cpf_cnpj_snapshot or associado.cpf_cnpj,
            "matricula": devolucao.matricula_snapshot or associado.matricula_orgao or associado.matricula or "-",
            "status": devolucao.status,
            "agente_nome": devolucao.agente_snapshot or AdminDashboardService._resolve_agent_name(associado=associado, contrato=contrato),
            "contrato_codigo": devolucao.contrato_codigo_snapshot or contrato.codigo,
            "etapa": "devolucao",
            "competencia": month_label(devolucao.competencia_referencia) if devolucao.competencia_referencia else "",
            "valor": value_or_none(valor if valor is not None else devolucao.valor),
            "origem": origem,
            "data_referencia": devolucao.data_devolucao.isoformat(),
            "observacao": observacao or devolucao.motivo,
        }

    @staticmethod
    def _detail_row_from_despesa(
        despesa: Despesa,
        *,
        origem: str,
        observacao: str = "",
        valor: Decimal | None = None,
    ) -> dict[str, object]:
        reference_date = despesa.data_pagamento or despesa.data_despesa
        return {
            "id": f"despesa-{despesa.id}-{origem}",
            "associado_id": None,
            "associado_nome": despesa.descricao,
            "cpf_cnpj": "",
            "matricula": despesa.categoria,
            "status": despesa.status,
            "agente_nome": "",
            "contrato_codigo": "",
            "etapa": "despesa",
            "competencia": month_label(reference_date.replace(day=1)),
            "valor": value_or_none(valor if valor is not None else despesa.valor),
            "origem": origem,
            "data_referencia": reference_date.isoformat(),
            "observacao": observacao or despesa.observacoes,
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
    def _renewal_reference_date(row: dict[str, object]) -> date | None:
        for key in ("data_pagamento", "data_solicitacao_renovacao", "data_ativacao_ciclo"):
            value = row.get(key)
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
        return None

    @staticmethod
    def _filter_renewal_rows_by_day(rows: list[dict[str, object]], day: date | None) -> list[dict[str, object]]:
        if not day:
            return rows
        return [
            row
            for row in rows
            if AdminDashboardService._renewal_reference_date(row) == day
        ]

    @staticmethod
    def _renewed_associados_for_month(
        month: date,
        *,
        agent_id: int | None = None,
        status: str | None = None,
        day: date | None = None,
    ) -> set[int]:
        rows = AdminDashboardService._filter_renewal_rows_by_agent(
            RenovacaoCicloService.listar_detalhes(
                competencia=month,
                status="ciclo_renovado",
            ),
            agent_id,
        )
        rows = AdminDashboardService._filter_renewal_rows_by_status(
            rows,
            status,
            agent_id,
        )
        rows = AdminDashboardService._filter_renewal_rows_by_day(rows, day)
        return {
            int(row["associado_id"])
            for row in rows
            if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
        }

    @staticmethod
    def _trend_months(end_month: date, count: int = 6) -> list[date]:
        start_month = add_months(end_month, -(count - 1))
        return [add_months(start_month, index) for index in range(count)]

    @staticmethod
    def _renewal_snapshot(
        months: list[date],
        *,
        agent_id: int | None = None,
        status: str | None = None,
    ) -> dict[str, dict[date | tuple[date, int], set[int]]]:
        if not months:
            return {
                "renewed_contracts": {},
                "renewed_associados": {},
                "renewed_contracts_by_agent": {},
                "apt_contracts": {},
                "apt_associados": {},
                "apt_contracts_by_agent": {},
            }

        start_month = min(months)
        end_month = add_months(max(months), 1)
        months_set = set(months)
        renewed_contracts: defaultdict[date, set[int]] = defaultdict(set)
        renewed_associados: defaultdict[date, set[int]] = defaultdict(set)
        renewed_contracts_by_agent: defaultdict[tuple[date, int], set[int]] = defaultdict(set)
        apt_contracts: defaultdict[date, set[int]] = defaultdict(set)
        apt_associados: defaultdict[date, set[int]] = defaultdict(set)
        apt_contracts_by_agent: defaultdict[tuple[date, int], set[int]] = defaultdict(set)

        relevant_cycle_ids = Parcela.objects.filter(
            referencia_mes__gte=start_month,
            referencia_mes__lt=end_month,
        ).values("ciclo_id")
        total_parcelas_subquery = (
            Parcela.objects.filter(ciclo_id=OuterRef("pk"))
            .values("ciclo_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        parcelas_pagas_subquery = (
            Parcela.objects.filter(
                ciclo_id=OuterRef("pk"),
                status=Parcela.Status.DESCONTADO,
            )
            .values("ciclo_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        cycle_rows = (
            Ciclo.objects.filter(
                id__in=relevant_cycle_ids,
                contrato__status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO],
            )
            .annotate(
                competencia_mes=TruncMonth("parcelas__referencia_mes"),
                resolved_agent_id=Coalesce(
                    "contrato__associado__agente_responsavel_id",
                    "contrato__agente_id",
                ),
                total_parcelas=Coalesce(
                    Subquery(total_parcelas_subquery, output_field=IntegerField()),
                    Value(0),
                ),
                parcelas_pagas=Coalesce(
                    Subquery(parcelas_pagas_subquery, output_field=IntegerField()),
                    Value(0),
                ),
            )
            .values(
                "competencia_mes",
                "resolved_agent_id",
                "contrato_id",
                "contrato__associado_id",
                "status",
                "total_parcelas",
                "parcelas_pagas",
            )
            .distinct()
        )
        if agent_id:
            cycle_rows = cycle_rows.filter(
                Q(contrato__agente_id=agent_id)
                | Q(contrato__associado__agente_responsavel_id=agent_id)
            )
        if status:
            cycle_rows = cycle_rows.filter(contrato__associado__status=status)

        for row in cycle_rows:
            month = row["competencia_mes"]
            if not isinstance(month, date) or month not in months_set:
                continue
            resolved_agent_id = row["resolved_agent_id"]
            contract_id = int(row["contrato_id"])
            associado_id = int(row["contrato__associado_id"])
            total_parcelas = int(row["total_parcelas"] or 0)
            parcelas_pagas = int(row["parcelas_pagas"] or 0)

            if row["status"] == Ciclo.Status.CICLO_RENOVADO:
                renewed_contracts[month].add(contract_id)
                renewed_associados[month].add(associado_id)
                if resolved_agent_id:
                    renewed_contracts_by_agent[(month, int(resolved_agent_id))].add(
                        contract_id
                    )
                continue

            parcelas_minimas = total_parcelas if total_parcelas <= 1 else total_parcelas - 1
            if (
                row["status"] in [Ciclo.Status.ABERTO, Ciclo.Status.APTO_A_RENOVAR]
                and total_parcelas > 0
                and parcelas_pagas >= parcelas_minimas
            ):
                apt_contracts[month].add(contract_id)
                apt_associados[month].add(associado_id)
                if resolved_agent_id:
                    apt_contracts_by_agent[(month, int(resolved_agent_id))].add(
                        contract_id
                    )

        encerramento_rows = (
            ArquivoRetornoItem.objects.filter(
                arquivo_retorno__competencia__gte=start_month,
                arquivo_retorno__competencia__lt=end_month,
                arquivo_retorno__status=ArquivoRetorno.Status.CONCLUIDO,
                gerou_encerramento=True,
                parcela__isnull=False,
            )
            .annotate(
                competencia_mes=TruncMonth("arquivo_retorno__competencia"),
                resolved_agent_id=Coalesce(
                    "parcela__ciclo__contrato__associado__agente_responsavel_id",
                    "parcela__ciclo__contrato__agente_id",
                ),
            )
            .values(
                "competencia_mes",
                "resolved_agent_id",
                "parcela__ciclo__contrato_id",
                "parcela__ciclo__contrato__associado_id",
            )
            .distinct()
        )
        if agent_id:
            encerramento_rows = encerramento_rows.filter(
                Q(parcela__ciclo__contrato__agente_id=agent_id)
                | Q(parcela__ciclo__contrato__associado__agente_responsavel_id=agent_id)
            )
        if status:
            encerramento_rows = encerramento_rows.filter(
                parcela__ciclo__contrato__associado__status=status
            )

        for row in encerramento_rows:
            month = row["competencia_mes"]
            if not isinstance(month, date) or month not in months_set:
                continue
            resolved_agent_id = row["resolved_agent_id"]
            contract_id = int(row["parcela__ciclo__contrato_id"])
            associado_id = int(row["parcela__ciclo__contrato__associado_id"])
            renewed_contracts[month].add(contract_id)
            renewed_associados[month].add(associado_id)
            if resolved_agent_id:
                renewed_contracts_by_agent[(month, int(resolved_agent_id))].add(
                    contract_id
                )

        return {
            "renewed_contracts": dict(renewed_contracts),
            "renewed_associados": dict(renewed_associados),
            "renewed_contracts_by_agent": dict(renewed_contracts_by_agent),
            "apt_contracts": dict(apt_contracts),
            "apt_associados": dict(apt_associados),
            "apt_contracts_by_agent": dict(apt_contracts_by_agent),
        }

    @staticmethod
    def _payments_saida_base(
        filters: DashboardFilters,
    ) -> QuerySet[TesourariaPagamento]:
        queryset = TesourariaPagamento.objects.filter(
            status=TesourariaPagamento.Status.PAGO
        ).select_related("cadastro", "cadastro__agente_responsavel")
        if filters.agent_id:
            queryset = queryset.filter(
                Q(cadastro__agente_responsavel_id=filters.agent_id)
                | Q(cadastro__contratos__agente_id=filters.agent_id)
            ).distinct()
        if filters.status:
            queryset = queryset.filter(cadastro__status=filters.status)

        queryset = queryset.filter(
            paid_at__date__year=filters.competencia.year,
            paid_at__date__month=filters.competencia.month,
        )
        if filters.day:
            queryset = queryset.filter(paid_at__date=filters.day)
        return queryset

    @staticmethod
    def _devolucoes_base(filters: DashboardFilters) -> QuerySet[DevolucaoAssociado]:
        queryset = DevolucaoAssociado.objects.filter(
            revertida_em__isnull=True,
            data_devolucao__year=filters.competencia.year,
            data_devolucao__month=filters.competencia.month,
        ).select_related(
            "associado",
            "associado__agente_responsavel",
            "contrato",
            "contrato__agente",
        )
        if filters.agent_id:
            queryset = queryset.filter(
                Q(associado__agente_responsavel_id=filters.agent_id)
                | Q(contrato__agente_id=filters.agent_id)
            ).distinct()
        if filters.status:
            queryset = queryset.filter(associado__status=filters.status)
        if filters.day:
            queryset = queryset.filter(data_devolucao=filters.day)
        return queryset

    @staticmethod
    def _despesas_base(filters: DashboardFilters) -> list[Despesa]:
        despesas = list(Despesa.objects.filter(status=Despesa.Status.PAGO).order_by("-data_pagamento", "-data_despesa"))
        filtered: list[Despesa] = []
        for despesa in despesas:
            reference_date = despesa.data_pagamento or despesa.data_despesa
            if reference_date.year != filters.competencia.year or reference_date.month != filters.competencia.month:
                continue
            if filters.day and reference_date != filters.day:
                continue
            filtered.append(despesa)
        return filtered

    @staticmethod
    def resumo_geral(filters: DashboardFilters) -> dict[str, object]:
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            *(AdminDashboardService._resolved_date_window(filters.date_start, filters.date_end, filters.day)
              if (filters.date_start or filters.date_end or filters.day)
              else (filters.date_start, filters.date_end)),
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

        trend_months = AdminDashboardService._trend_months(filters.competencia)
        renewal_snapshot = (
            AdminDashboardService._renewal_snapshot(
                list({filters.competencia, *trend_months}),
                agent_id=filters.agent_id,
                status=filters.status,
            )
            if not filters.day
            else None
        )
        if renewal_snapshot is None:
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
                RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
                filters.agent_id,
            )
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
                renewal_rows,
                filters.status,
                filters.agent_id,
            )
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_day(
                renewal_rows,
                filters.day,
            )
            renovacoes = sum(
                1
                for row in renewal_rows
                if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
            )
            aptos_renovacao = sum(
                1 for row in renewal_rows if row["status_visual"] == "apto_a_renovar"
            )
        else:
            renovacoes = len(
                renewal_snapshot["renewed_contracts"].get(filters.competencia, set())
            )
            aptos_renovacao = len(
                renewal_snapshot["apt_contracts"].get(filters.competencia, set())
            )

        effective_contracts = AdminDashboardService._contracts_base(filters.agent_id).filter(
            auxilio_liberado_em__isnull=False
        )
        effective_contracts = AdminDashboardService._filter_contracts_by_associado_status(
            effective_contracts,
            filters.status,
        )
        if filters.date_start or filters.date_end or filters.day:
            effective_contracts = AdminDashboardService._filter_queryset_by_field_range(
                effective_contracts,
                "auxilio_liberado_em",
                *AdminDashboardService._resolved_date_window(
                    filters.date_start,
                    filters.date_end,
                    filters.day,
                ),
            )

        pie_counts = {
            status_key: associados.filter(status=status_key).count()
            for status_key, _ in Associado.Status.choices
        }
        trend_points: list[dict[str, object]] = []
        for month in trend_months:
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
            if filters.day:
                month_associados = month_associados.filter(created_at__date=filters.day)
                month_effectivados = month_effectivados.filter(auxilio_liberado_em=filters.day)
            else:
                if filters.date_start:
                    month_associados = month_associados.filter(created_at__date__gte=filters.date_start)
                    month_effectivados = month_effectivados.filter(auxilio_liberado_em__gte=filters.date_start)
                if filters.date_end:
                    month_associados = month_associados.filter(created_at__date__lte=filters.date_end)
                    month_effectivados = month_effectivados.filter(auxilio_liberado_em__lte=filters.date_end)
            if renewal_snapshot is None:
                month_renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
                    RenovacaoCicloService.listar_detalhes(competencia=month),
                    filters.agent_id,
                )
                month_renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
                    month_renewal_rows,
                    filters.status,
                    filters.agent_id,
                )
                month_renewal_rows = AdminDashboardService._filter_renewal_rows_by_day(
                    month_renewal_rows,
                    filters.day,
                )
                renewed_count = sum(
                    1
                    for row in month_renewal_rows
                    if row["status_visual"] == "ciclo_renovado"
                    or row["gerou_encerramento"]
                )
            else:
                renewed_count = len(
                    renewal_snapshot["renewed_contracts"].get(month, set())
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

    @classmethod
    def _ok_payments_for_filters(
        cls,
        filters: DashboardFilters,
    ) -> list[PagamentoMensalidade]:
        return [
            payment
            for payment in cls._payments_base(
                filters.competencia,
                filters.agent_id,
                filters.status,
            )
            if cls._payment_is_ok(payment)
            and cls._payment_matches_day(payment, filters.day)
        ]

    @staticmethod
    def _liquidacoes_base(filters: DashboardFilters) -> QuerySet[LiquidacaoContrato]:
        queryset = LiquidacaoContrato.objects.filter(
            revertida_em__isnull=True,
            data_liquidacao__year=filters.competencia.year,
            data_liquidacao__month=filters.competencia.month,
        ).select_related(
            "contrato",
            "contrato__agente",
            "contrato__associado",
            "contrato__associado__agente_responsavel",
        )
        if filters.agent_id:
            queryset = queryset.filter(
                Q(contrato__agente_id=filters.agent_id)
                | Q(
                    contrato__agente__isnull=True,
                    contrato__associado__agente_responsavel_id=filters.agent_id,
                )
            ).distinct()
        if filters.status:
            queryset = queryset.filter(contrato__associado__status=filters.status)
        if filters.day:
            queryset = queryset.filter(data_liquidacao=filters.day)
        return queryset

    @staticmethod
    def _contract_auxilio_liberado_value(contrato: Contrato | None) -> Decimal:
        if contrato is None:
            return Decimal("0.00")
        for candidate in (contrato.margem_disponivel, contrato.valor_mensalidade):
            resolved = Decimal(str(candidate or "0.00"))
            if resolved > 0:
                return resolved
        return Decimal("0.00")

    @staticmethod
    def _contract_repasse_value(contrato: Contrato | None) -> Decimal:
        if contrato is None:
            return Decimal("0.00")
        repasse = contrato.comissao_agente or contrato.calculate_comissao_agente() or Decimal("0.00")
        return Decimal(str(repasse or "0.00"))

    @classmethod
    def _resolve_treasury_payment_context(
        cls,
        pagamentos: list[TesourariaPagamento],
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
            contract_id = int(contract_id_raw) if str(contract_id_raw).isdigit() else None
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

        contracts = Contrato.objects.select_related("agente", "associado").filter(
            Q(id__in=contract_ids) | Q(codigo__in=contract_codes)
        )
        contracts_by_id = {contrato.id: contrato for contrato in contracts}
        contracts_by_code = {contrato.codigo: contrato for contrato in contracts}

        refinancings = Refinanciamento.objects.select_related(
            "contrato_origem",
            "contrato_origem__agente",
            "contrato_origem__associado",
        ).filter(id__in=refinancing_ids)
        refinancings_by_id = {
            refinanciamento.id: refinanciamento for refinanciamento in refinancings
        }

        payload: dict[int, dict[str, object]] = {}
        for pagamento in pagamentos:
            refs = parsed_refs.get(pagamento.id, {})
            refinancing = (
                refinancings_by_id.get(int(refs["refinancing_id"]))
                if refs.get("refinancing_id")
                else None
            )
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

            if is_renewal:
                valor_associado = cls._contract_auxilio_liberado_value(contract)
                if valor_associado <= 0 and refinancing is not None:
                    valor_associado = Decimal(
                        str(refinancing.valor_refinanciamento or zero)
                    )
                if valor_associado <= 0:
                    valor_associado = Decimal(
                        str(
                            pagamento.contrato_margem_disponivel
                            or pagamento.valor_pago
                            or zero
                        )
                    )
                valor_agente = Decimal(
                    str(
                        (
                            refinancing.repasse_agente
                            if refinancing is not None
                            else cls._contract_repasse_value(contract)
                        )
                        or zero
                    )
                )
            else:
                valor_associado = cls._contract_auxilio_liberado_value(contract)
                if valor_associado <= 0:
                    valor_associado = Decimal(
                        str(
                            pagamento.contrato_margem_disponivel
                            or pagamento.valor_pago
                            or zero
                        )
                    )
                valor_agente = cls._contract_repasse_value(contract)

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
    def tesouraria(filters: DashboardFilters) -> dict[str, object]:
        AdminDashboardService._validate_day_with_competencia(filters, section="tesouraria")

        payments = [
            payment
            for payment in AdminDashboardService._payments_base(
                filters.competencia,
                filters.agent_id,
                filters.status,
            )
            if AdminDashboardService._payment_matches_day(payment, filters.day)
        ]
        ok_payments = AdminDashboardService._ok_payments_for_filters(filters)
        liquidacoes = list(AdminDashboardService._liquidacoes_base(filters))
        received_value = sum(
            (AdminDashboardService._payment_value(payment) for payment in ok_payments),
            Decimal("0.00"),
        ) + sum(
            (liquidacao.valor_total for liquidacao in liquidacoes),
            Decimal("0.00"),
        )
        import_count = sum(1 for payment in payments if AdminDashboardService._payment_is_imported(payment))
        manual_count = sum(1 for payment in payments if AdminDashboardService._payment_is_manual(payment))
        inadimplentes_quitados = sum(
            1
            for payment in ok_payments
            if payment.associado
            and payment.associado.status == Associado.Status.INADIMPLENTE
        )
        received_associados = {
            (
                f"id:{payment.associado_id}"
                if payment.associado_id
                else f"doc:{payment.cpf_cnpj or payment.matricula or payment.id}"
            )
            for payment in ok_payments
        }
        received_associados_count = len(received_associados)
        received_associados_label = (
            "associado" if received_associados_count == 1 else "associados"
        )

        contracts_month = AdminDashboardService._contracts_base(filters.agent_id).filter(
            data_contrato__year=filters.competencia.year,
            data_contrato__month=filters.competencia.month,
        )
        contracts_month = AdminDashboardService._filter_contracts_by_associado_status(
            contracts_month,
            filters.status,
        )
        if filters.day:
            contracts_month = contracts_month.filter(data_contrato=filters.day)
        new_contracts = contracts_month.count()

        treasury_payouts = list(AdminDashboardService._payments_saida_base(filters))
        payout_context = AdminDashboardService._resolve_treasury_payment_context(
            treasury_payouts
        )
        despesas = AdminDashboardService._despesas_base(filters)
        saidas_value = sum(
            (
                Decimal(
                    str(
                        payout_context.get(pagamento.id, {}).get("valor_total")
                        or "0.00"
                    )
                )
                for pagamento in treasury_payouts
            ),
            Decimal("0.00"),
        )
        despesas_value = sum((despesa.valor for despesa in despesas), Decimal("0.00"))
        receita_liquida = received_value - saidas_value - despesas_value

        projection_points: list[dict[str, object]] = []
        projection_total = Decimal("0.00")
        pending_current = Decimal("0.00")
        future_projection = Decimal("0.00")
        for index in range(3):
            month = add_months(filters.competencia, index)
            parcelas = list(AdminDashboardService._projection_parcelas(month, filters.agent_id))
            projected_value = sum((parcela.valor for parcela in parcelas), Decimal("0.00"))
            month_filters = DashboardFilters(
                competencia=month,
                day=filters.day,
                agent_id=filters.agent_id,
                status=filters.status,
            )
            month_received = sum(
                (
                    AdminDashboardService._payment_value(payment)
                    for payment in AdminDashboardService._ok_payments_for_filters(
                        month_filters
                    )
                ),
                Decimal("0.00"),
            ) + sum(
                (
                    liquidacao.valor_total
                    for liquidacao in AdminDashboardService._liquidacoes_base(
                        month_filters
                    )
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
                    description=(
                        "Arquivo retorno, baixas manuais e liquidacoes consolidadas. "
                        f"{received_associados_count} {received_associados_label} com desconto efetuado ou baixa manual."
                    ),
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
                    key="saidas_agentes_associados",
                    label="Saidas a agentes/associados",
                    numeric_value=saidas_value,
                    value_format="currency",
                    tone="warning",
                    detail_metric="saidas_agentes_associados",
                    description="Auxilio liberado ao associado somado ao repasse do agente nas saidas liquidadas da competencia.",
                ),
                AdminDashboardService._metric_card(
                    key="despesas",
                    label="Despesas",
                    numeric_value=despesas_value,
                    value_format="currency",
                    tone="danger",
                    detail_metric="despesas",
                    description="Despesas pagas que impactam o caixa da associacao.",
                ),
                AdminDashboardService._metric_card(
                    key="receita_liquida_associacao",
                    label="Receita liquida da associacao",
                    numeric_value=receita_liquida,
                    value_format="currency",
                    tone="positive" if receita_liquida >= 0 else "danger",
                    detail_metric="receita_liquida_associacao",
                    description="Receita recebida menos saidas liquidadas a agentes/associados e despesas.",
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
    def resumo_mensal_associacao(filters: DashboardFilters) -> dict[str, object]:
        months = AdminDashboardService._trend_months(filters.competencia, count=12)
        start_month = months[0]
        end_month = add_months(filters.competencia, 1)
        zero = Decimal("0.00")

        complementos_por_mes = {month: zero for month in months}
        despesas_pagas_por_mes = {month: zero for month in months}
        novos_associados_por_mes = {month: set() for month in months}
        liquidacoes_por_mes: dict[date, dict[str, set[int]]] = {
            month: {"associados": set(), "contratos": set()}
            for month in months
        }
        encerrados_por_mes: dict[date, set[int]] = {month: set() for month in months}
        complementos = (
            Despesa.objects.filter(
                natureza=Despesa.Natureza.COMPLEMENTO_RECEITA,
                status=Despesa.Status.PAGO,
                data_pagamento__gte=start_month,
                data_pagamento__lt=end_month,
            )
            .annotate(bucket_month=TruncMonth("data_pagamento"))
            .values("bucket_month")
            .annotate(total=Coalesce(Sum("valor"), Value(zero), output_field=DecimalField()))
        )
        for row in complementos:
            bucket_month = row["bucket_month"]
            if isinstance(bucket_month, date) and bucket_month in complementos_por_mes:
                complementos_por_mes[bucket_month] = Decimal(str(row["total"] or zero))

        despesas_pagas = (
            Despesa.objects.filter(
                natureza=Despesa.Natureza.DESPESA_OPERACIONAL,
                status=Despesa.Status.PAGO,
                data_pagamento__gte=start_month,
                data_pagamento__lt=end_month,
            )
            .annotate(bucket_month=TruncMonth("data_pagamento"))
            .values("bucket_month")
            .annotate(total=Coalesce(Sum("valor"), Value(zero), output_field=DecimalField()))
        )
        for row in despesas_pagas:
            bucket_month = row["bucket_month"]
            if isinstance(bucket_month, date) and bucket_month in despesas_pagas_por_mes:
                despesas_pagas_por_mes[bucket_month] = Decimal(str(row["total"] or zero))

        contratos_efetivados = AdminDashboardService._contracts_base(
            filters.agent_id
        ).filter(
            auxilio_liberado_em__gte=start_month,
            auxilio_liberado_em__lt=end_month,
            auxilio_liberado_em__isnull=False,
        ).values_list("associado_id", "auxilio_liberado_em")
        if filters.status:
            contratos_efetivados = contratos_efetivados.filter(
                associado__status=filters.status
            )
        if filters.day:
            contratos_efetivados = contratos_efetivados.filter(
                auxilio_liberado_em=filters.day
            )
        for associado_id, auxilio_liberado_em in contratos_efetivados:
            if auxilio_liberado_em is None:
                continue
            bucket_month = auxilio_liberado_em.replace(day=1)
            if bucket_month in novos_associados_por_mes:
                novos_associados_por_mes[bucket_month].add(int(associado_id))

        liquidacoes = LiquidacaoContrato.objects.filter(
            revertida_em__isnull=True,
            data_liquidacao__gte=start_month,
            data_liquidacao__lt=end_month,
        ).values_list("contrato__associado_id", "contrato_id", "data_liquidacao")
        if filters.agent_id:
            liquidacoes = liquidacoes.filter(
                Q(contrato__agente_id=filters.agent_id)
                | Q(contrato__associado__agente_responsavel_id=filters.agent_id)
            )
        if filters.status:
            liquidacoes = liquidacoes.filter(contrato__associado__status=filters.status)
        if filters.day:
            liquidacoes = liquidacoes.filter(data_liquidacao=filters.day)
        for associado_id, contrato_id, data_liquidacao in liquidacoes:
            bucket_month = data_liquidacao.replace(day=1)
            if bucket_month in liquidacoes_por_mes:
                liquidacoes_por_mes[bucket_month]["associados"].add(int(associado_id))
                liquidacoes_por_mes[bucket_month]["contratos"].add(int(contrato_id))

        contratos_encerrados = AdminDashboardService._contracts_base(
            filters.agent_id
        ).filter(
            status=Contrato.Status.ENCERRADO,
            updated_at__date__gte=start_month,
            updated_at__date__lt=end_month,
        ).values_list("id", "associado_id", "updated_at")
        if filters.status:
            contratos_encerrados = contratos_encerrados.filter(
                associado__status=filters.status
            )
        if filters.day:
            contratos_encerrados = contratos_encerrados.filter(
                updated_at__date=filters.day
            )
        for contrato_id, associado_id, updated_at in contratos_encerrados:
            bucket_month = updated_at.date().replace(day=1)
            if bucket_month not in encerrados_por_mes:
                continue
            liquidated_contract_ids = liquidacoes_por_mes[bucket_month]["contratos"]
            if int(contrato_id) not in liquidated_contract_ids:
                encerrados_por_mes[bucket_month].add(int(associado_id))

        renewal_snapshot = AdminDashboardService._renewal_snapshot(
            months,
            agent_id=filters.agent_id,
            status=filters.status,
        )
        renovacoes_por_mes = {
            month: (
                AdminDashboardService._renewed_associados_for_month(
                    month,
                    agent_id=filters.agent_id,
                    status=filters.status,
                    day=filters.day,
                )
                if filters.day and month == filters.day.replace(day=1)
                else (
                    renewal_snapshot["renewed_associados"].get(month, set())
                    if not filters.day
                    else set()
                )
            )
            for month in months
        }

        rows: list[dict[str, object]] = []
        for month in months:
            complementos_receita = complementos_por_mes[month]
            despesas_pagas_mes = despesas_pagas_por_mes[month]
            desvinculados = (
                liquidacoes_por_mes[month]["associados"] | encerrados_por_mes[month]
            )
            rows.append(
                {
                    "mes": month,
                    "complementos_receita": complementos_receita,
                    "saldo_positivo": max(complementos_receita - despesas_pagas_mes, zero),
                    "novos_associados": len(novos_associados_por_mes[month]),
                    "desvinculados": len(desvinculados),
                    "renovacoes_associado": len(renovacoes_por_mes[month]),
                }
            )

        return {
            "competencia": month_key(filters.competencia),
            "rows": rows,
        }

    @staticmethod
    def _resolved_date_window(
        date_start: date | None,
        date_end: date | None,
        day: date | None = None,
    ) -> tuple[date, date]:
        if day:
            return day, day
        today = timezone.localdate()
        if not date_start and not date_end:
            return today.replace(day=1), today
        return date_start or today.replace(day=1), date_end or today

    @staticmethod
    def novos_associados(filters: DashboardFilters) -> dict[str, object]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
            filters.day,
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
        AdminDashboardService._validate_day_with_competencia(filters, section="agentes")
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
            filters.day,
        )
        zero = Decimal("0.00")
        agents = list(
            User.objects.filter(
                Q(roles__codigo="AGENTE")
                | Q(associados_cadastrados__isnull=False)
                | Q(contratos_agenciados__isnull=False)
            )
            .distinct()
            .prefetch_related("roles")
            .order_by("first_name", "last_name", "email")
        )
        if filters.agent_id:
            agents = [agent for agent in agents if agent.id == filters.agent_id]

        agent_ids = [agent.id for agent in agents]
        agent_role_map = {
            agent.id: {role.codigo for role in agent.roles.all()} for agent in agents
        }
        cadastros_map: dict[int, dict[str, int]] = {}
        base_status_map: dict[int, dict[str, int]] = {}
        efetivados_map: dict[int, dict[str, Decimal]] = {}
        devolvidos_map: defaultdict[int, set[int]] = defaultdict(set)

        if agent_ids:
            cadastros_queryset = Associado.objects.filter(
                agente_responsavel_id__in=agent_ids,
                created_at__date__gte=date_start,
                created_at__date__lte=date_end,
            )
            if filters.status:
                cadastros_queryset = cadastros_queryset.filter(status=filters.status)
            cadastros_map = {
                int(row["agente_responsavel_id"]): {
                    "cadastros": int(row["cadastros"] or 0),
                    "em_processo": int(row["em_processo"] or 0),
                }
                for row in cadastros_queryset.values("agente_responsavel_id").annotate(
                    cadastros=Count("id"),
                    em_processo=Count(
                        "id",
                        filter=Q(status__in=PROCESSING_ASSOCIADO_STATUSES),
                    ),
                )
            }

            base_status_queryset = Associado.objects.filter(
                agente_responsavel_id__in=agent_ids,
            )
            if filters.status:
                base_status_queryset = base_status_queryset.filter(status=filters.status)
            base_status_map = {
                int(row["agente_responsavel_id"]): {
                    "cadastrado": int(row["cadastrado"] or 0),
                    "em_analise": int(row["em_analise"] or 0),
                    "pendente": int(row["pendente"] or 0),
                    "ativo": int(row["ativo"] or 0),
                    "inadimplente": int(row["inadimplente"] or 0),
                    "inativo": int(row["inativo"] or 0),
                }
                for row in base_status_queryset.values("agente_responsavel_id").annotate(
                    cadastrado=Count("id", filter=Q(status=Associado.Status.CADASTRADO)),
                    em_analise=Count("id", filter=Q(status=Associado.Status.EM_ANALISE)),
                    pendente=Count("id", filter=Q(status=Associado.Status.PENDENTE)),
                    ativo=Count("id", filter=Q(status=Associado.Status.ATIVO)),
                    inadimplente=Count("id", filter=Q(status=Associado.Status.INADIMPLENTE)),
                    inativo=Count("id", filter=Q(status=Associado.Status.INATIVO)),
                )
            }

            efetivados_queryset = (
                Contrato.objects.exclude(status=Contrato.Status.CANCELADO)
                .filter(
                    auxilio_liberado_em__gte=date_start,
                    auxilio_liberado_em__lte=date_end,
                    auxilio_liberado_em__isnull=False,
                )
                .annotate(
                    resolved_agent_id=Coalesce("agente_id", "associado__agente_responsavel_id"),
                    auxilio_liberado_valor=Case(
                        When(margem_disponivel__gt=0, then=F("margem_disponivel")),
                        When(valor_mensalidade__gt=0, then=F("valor_mensalidade")),
                        default=Value(zero),
                        output_field=DecimalField(),
                    ),
                )
                .filter(resolved_agent_id__in=agent_ids)
            )
            if filters.status:
                efetivados_queryset = efetivados_queryset.filter(associado__status=filters.status)
            efetivados_map = {
                int(row["resolved_agent_id"]): {
                    "efetivados": int(row["efetivados"] or 0),
                    "volume_financeiro": Decimal(str(row["volume_financeiro"] or zero)),
                }
                for row in efetivados_queryset.values("resolved_agent_id").annotate(
                    efetivados=Count("id", distinct=True),
                    volume_financeiro=Coalesce(
                        Sum("auxilio_liberado_valor"),
                        Value(zero),
                        output_field=DecimalField(),
                    ),
                )
            }

            devolucoes_queryset = DevolucaoAssociado.objects.filter(
                revertida_em__isnull=True,
                data_devolucao__year=filters.competencia.year,
                data_devolucao__month=filters.competencia.month,
            )
            if filters.status:
                devolucoes_queryset = devolucoes_queryset.filter(associado__status=filters.status)
            if filters.day:
                devolucoes_queryset = devolucoes_queryset.filter(data_devolucao=filters.day)
            for devolucao_id, associado_agent_id, contrato_agent_id in devolucoes_queryset.values_list(
                "id",
                "associado__agente_responsavel_id",
                "contrato__agente_id",
            ):
                for candidate_agent_id in {associado_agent_id, contrato_agent_id}:
                    if candidate_agent_id in agent_ids:
                        devolvidos_map[int(candidate_agent_id)].add(int(devolucao_id))

        if filters.day:
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_agent(
                RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
                filters.agent_id,
            )
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_status(
                renewal_rows,
                filters.status,
                filters.agent_id,
            )
            renewal_rows = AdminDashboardService._filter_renewal_rows_by_day(
                renewal_rows,
                filters.day,
            )
            renewal_snapshot = None
        else:
            renewal_rows = []
            renewal_snapshot = AdminDashboardService._renewal_snapshot(
                [filters.competencia],
                agent_id=filters.agent_id,
                status=filters.status,
            )

        ranking: list[dict[str, object]] = []
        for agent in agents:
            cadastros_stats = cadastros_map.get(agent.id, {})
            status_counts = base_status_map.get(agent.id, {})
            efetivados_stats = efetivados_map.get(agent.id, {})
            cadastros_total = int(cadastros_stats.get("cadastros", 0))
            em_processo = int(cadastros_stats.get("em_processo", 0))
            inadimplentes = int(status_counts.get("inadimplente", 0))
            inativos = int(status_counts.get("inativo", 0))
            efetivados_total = int(efetivados_stats.get("efetivados", 0))
            volume_financeiro = Decimal(
                str(efetivados_stats.get("volume_financeiro", zero))
            )
            if renewal_snapshot is None:
                agent_renewals = [
                    row
                    for row in renewal_rows
                    if row["agente_responsavel"] == (agent.full_name or agent.email)
                ]
                renovados = sum(
                    1
                    for row in agent_renewals
                    if row["status_visual"] == "ciclo_renovado"
                    or row["gerou_encerramento"]
                )
                aptos_renovar = sum(
                    1 for row in agent_renewals if row["status_visual"] == "apto_a_renovar"
                )
            else:
                renovados = len(
                    renewal_snapshot["renewed_contracts_by_agent"].get(
                        (filters.competencia, agent.id),
                        set(),
                    )
                )
                aptos_renovar = len(
                    renewal_snapshot["apt_contracts_by_agent"].get(
                        (filters.competencia, agent.id),
                        set(),
                    )
                )
            devolvidos = len(devolvidos_map.get(agent.id, set()))
            metrics_total = (
                cadastros_total
                + em_processo
                + inadimplentes
                + efetivados_total
                + renovados
                + aptos_renovar
                + devolvidos
                + int(volume_financeiro > 0)
            )
            if metrics_total == 0 and "AGENTE" not in agent_role_map.get(agent.id, set()):
                continue
            ranking.append(
                {
                    "agent_id": agent.id,
                    "agent_name": agent.full_name or agent.email,
                    "efetivados": efetivados_total,
                    "cadastros": cadastros_total,
                    "em_processo": em_processo,
                    "renovados": renovados,
                    "aptos_renovar": aptos_renovar,
                    "inadimplentes": inadimplentes,
                    "devolvidos": devolvidos,
                    "volume_financeiro": float(volume_financeiro),
                    "cadastrado": int(status_counts.get("cadastrado", 0)),
                    "em_analise": int(status_counts.get("em_analise", 0)),
                    "pendente": int(status_counts.get("pendente", 0)),
                    "ativo": int(status_counts.get("ativo", 0)),
                    "inadimplente": int(status_counts.get("inadimplente", 0)),
                    "inativo": int(status_counts.get("inativo", 0)),
                }
            )

        ranking.sort(
            key=lambda item: (-item["volume_financeiro"], -item["efetivados"], item["agent_name"])
        )
        total_efetivados = sum(item["efetivados"] for item in ranking)
        total_volume = sum(Decimal(str(item["volume_financeiro"])) for item in ranking)
        for item in ranking:
            item["participacao"] = round(
                ((item["efetivados"] / total_efetivados) * 100) if total_efetivados else 0,
                1,
            )
            item["participacao_volume"] = round(
                float(
                    (
                        (Decimal(str(item["volume_financeiro"])) / total_volume)
                        * Decimal("100")
                    )
                    if total_volume
                    else Decimal("0.0")
                ),
                1,
            )
            item["detail_metric"] = f"agente:{item['agent_id']}:volume"

        top_agent = ranking[0] if ranking else None
        avg_volume = round(float(total_volume / Decimal(len(ranking))), 2) if ranking else 0.0
        total_inativos = sum(item["inativo"] for item in ranking)
        total_devolvidos = sum(item["devolvidos"] for item in ranking)
        total_renovados = sum(item["renovados"] for item in ranking)
        total_aptos = sum(item["aptos_renovar"] for item in ranking)

        return {
            "competencia": month_key(filters.competencia),
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
            "cards": [
                AdminDashboardService._metric_card(
                    key="volume_total",
                    label="Volume total",
                    numeric_value=total_volume,
                    value_format="currency",
                    detail_metric="agentes:volume_total",
                    description="Soma do auxilio liberado aos associados efetivados no recorte.",
                ),
                AdminDashboardService._metric_card(
                    key="top_agente_volume",
                    label="Top agente por volume",
                    numeric_value=Decimal(str(top_agent["volume_financeiro"])) if top_agent else Decimal("0.00"),
                    value_format="currency",
                    tone="positive",
                    detail_metric=top_agent["detail_metric"] if top_agent else "agentes:volume_total",
                    description=top_agent["agent_name"] if top_agent else "Sem agente no periodo",
                ),
                AdminDashboardService._metric_card(
                    key="media_volume",
                    label="Media por agente",
                    numeric_value=avg_volume,
                    value_format="currency",
                    detail_metric="agentes:volume_total",
                    description="Media de auxilio liberado entre os agentes monitorados.",
                ),
                AdminDashboardService._metric_card(
                    key="associados_inativos",
                    label="Associados inativos",
                    numeric_value=total_inativos,
                    detail_metric="agentes:inativos",
                    description="Base atual de associados inativos vinculados aos agentes filtrados.",
                ),
                AdminDashboardService._metric_card(
                    key="com_devolucao",
                    label="Associados com devolucao",
                    numeric_value=total_devolvidos,
                    detail_metric="agentes:devolvidos",
                    description="Devolucoes registradas na competencia filtrada.",
                ),
                AdminDashboardService._metric_card(
                    key="renovados",
                    label="Associados renovados",
                    numeric_value=total_renovados,
                    tone="positive",
                    detail_metric="agentes:renovados",
                    description="Renovacoes efetivadas na competencia da secao.",
                ),
                AdminDashboardService._metric_card(
                    key="aptos_renovar",
                    label="Associados para renovar",
                    numeric_value=total_aptos,
                    detail_metric="agentes:aptos_renovar",
                    description="Associados aptos a renovar na competencia da secao.",
                ),
            ],
            "ranking": ranking[:8],
        }

    @staticmethod
    def detalhes(
        filters: DashboardFilters,
        *,
        section: str,
        metric: str,
        search: str | None = None,
    ) -> list[dict[str, object]]:
        if section == "summary":
            rows = AdminDashboardService._summary_details(filters, metric)
        elif section == "treasury":
            rows = AdminDashboardService._treasury_details(filters, metric)
        elif section == "new-associados":
            rows = AdminDashboardService._new_associados_details(filters, metric)
        elif section == "agentes":
            rows = AdminDashboardService._agents_details(filters, metric)
        else:
            raise ValidationError("section invalido.")

        normalized_search = (search or "").strip().lower()
        if not normalized_search:
            return rows

        return [
            row
            for row in rows
            if normalized_search in str(row.get("associado_nome", "")).lower()
            or normalized_search in str(row.get("cpf_cnpj", "")).lower()
            or normalized_search in str(row.get("matricula", "")).lower()
            or normalized_search in str(row.get("contrato_codigo", "")).lower()
            or normalized_search in str(row.get("origem", "")).lower()
        ]

    @staticmethod
    def _summary_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        associados = AdminDashboardService._associados_base(filters.agent_id)
        associados = AdminDashboardService._filter_queryset_by_created_range(
            associados,
            *(AdminDashboardService._resolved_date_window(
                filters.date_start,
                filters.date_end,
                filters.day,
            )
              if (filters.date_start or filters.date_end or filters.day)
              else (filters.date_start, filters.date_end)),
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
        renewal_rows = AdminDashboardService._filter_renewal_rows_by_day(
            renewal_rows,
            filters.day,
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
            if filters.date_start or filters.date_end or filters.day:
                effective_contracts = AdminDashboardService._filter_queryset_by_field_range(
                    effective_contracts,
                    "auxilio_liberado_em",
                    *AdminDashboardService._resolved_date_window(
                        filters.date_start,
                        filters.date_end,
                        filters.day,
                    ),
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
                if filters.day:
                    month_associados = month_associados.filter(created_at__date=filters.day)
                else:
                    if filters.date_start:
                        month_associados = month_associados.filter(created_at__date__gte=filters.date_start)
                    if filters.date_end:
                        month_associados = month_associados.filter(created_at__date__lte=filters.date_end)
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
                if filters.day:
                    contracts = contracts.filter(auxilio_liberado_em=filters.day)
                else:
                    if filters.date_start:
                        contracts = contracts.filter(auxilio_liberado_em__gte=filters.date_start)
                    if filters.date_end:
                        contracts = contracts.filter(auxilio_liberado_em__lte=filters.date_end)
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
                    RenovacaoCicloService.listar_detalhes(
                        competencia=month,
                        status="ciclo_renovado",
                    ),
                    filters.agent_id,
                )
                month_rows = AdminDashboardService._filter_renewal_rows_by_status(
                    month_rows,
                    filters.status,
                    filters.agent_id,
                )
                month_rows = AdminDashboardService._filter_renewal_rows_by_day(
                    month_rows,
                    filters.day,
                )
                return [
                    AdminDashboardService._detail_row_from_renewal_row(row, origem=f"Renovacao {month_label(month)}")
                    for row in month_rows
                    if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
                ]
        return []

    @staticmethod
    def _treasury_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        AdminDashboardService._validate_day_with_competencia(filters, section="tesouraria")

        def ok_rows_for_month(month: date) -> list[PagamentoMensalidade]:
            return AdminDashboardService._ok_payments_for_filters(
                DashboardFilters(
                    competencia=month,
                    day=filters.day,
                    agent_id=filters.agent_id,
                    status=filters.status,
                )
            )

        payments = [
            payment
            for payment in AdminDashboardService._payments_base(
                filters.competencia,
                filters.agent_id,
                filters.status,
            )
            if AdminDashboardService._payment_matches_day(payment, filters.day)
        ]
        if metric == "valores_recebidos":
            rows = [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Valor recebido",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Baixa consolidada na tesouraria.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_ok(payment)
            ]
            rows.extend(
                [
                    AdminDashboardService._detail_row_from_liquidacao(
                        liquidacao,
                        origem="Liquidacao de contrato",
                        valor=liquidacao.valor_total,
                        observacao="Liquidacao consolidada na tesouraria.",
                    )
                    for liquidacao in AdminDashboardService._liquidacoes_base(filters)
                ]
            )
            return rows
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
            contracts = AdminDashboardService._filter_contracts_by_associado_status(
                contracts,
                filters.status,
            )
            if filters.day:
                contracts = contracts.filter(data_contrato=filters.day)
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
            rows = [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem=f"Recebido {month_label(month)}",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Recebimento consolidado na serie de tesouraria.",
                )
                for payment in ok_rows_for_month(month)
            ]
            rows.extend(
                [
                    AdminDashboardService._detail_row_from_liquidacao(
                        liquidacao,
                        origem=f"Liquidacao {month_label(month)}",
                        valor=liquidacao.valor_total,
                        observacao="Liquidacao consolidada na serie de tesouraria.",
                    )
                    for liquidacao in AdminDashboardService._liquidacoes_base(
                        DashboardFilters(
                            competencia=month,
                            day=filters.day,
                            agent_id=filters.agent_id,
                            status=filters.status,
                        )
                    )
                ]
            )
            return rows
        if metric.startswith("projetado:"):
            month = parse_competencia_query(metric.split(":", 1)[1])
            return [
                AdminDashboardService._detail_row_from_parcela(
                    parcela,
                    origem=f"Projecao {month_label(month)}",
                )
                for parcela in AdminDashboardService._projection_parcelas(month, filters.agent_id)
            ]
        if metric == "saidas_agentes_associados":
            pagamentos = list(AdminDashboardService._payments_saida_base(filters))
            payment_context = AdminDashboardService._resolve_treasury_payment_context(
                pagamentos
            )
            rows = []
            for pagamento in pagamentos:
                context = payment_context.get(pagamento.id, {})
                valor_associado = Decimal(
                    str(context.get("valor_associado") or Decimal("0.00"))
                )
                valor_agente = Decimal(
                    str(context.get("valor_agente") or Decimal("0.00"))
                )
                origem = (
                    "Pagamento de renovacao"
                    if context.get("payment_kind") == "renovacao"
                    else "Pagamento tesouraria"
                )
                rows.append(
                    AdminDashboardService._detail_row_from_tesouraria_pagamento(
                        pagamento,
                        origem=origem,
                        valor=valor_associado,
                        valor_associado=valor_associado,
                        valor_agente=valor_agente,
                        valor_total=Decimal(
                            str(context.get("valor_total") or Decimal("0.00"))
                        ),
                        observacao=(
                            "Auxilio liberado ao associado e repasse do agente liquidados na tesouraria."
                        ),
                    )
                )
            return rows
        if metric == "despesas":
            return [
                AdminDashboardService._detail_row_from_despesa(
                    despesa,
                    origem="Despesa paga",
                    observacao="Despesa operacional paga.",
                )
                for despesa in AdminDashboardService._despesas_base(filters)
            ]
        if metric == "receita_liquida_associacao":
            rows = [
                AdminDashboardService._detail_row_from_payment(
                    payment,
                    origem="Recebimento",
                    valor=AdminDashboardService._payment_value(payment),
                    observacao="Receita recebida na tesouraria.",
                )
                for payment in payments
                if AdminDashboardService._payment_is_ok(payment)
            ]
            rows.extend(
                [
                    AdminDashboardService._detail_row_from_liquidacao(
                        liquidacao,
                        origem="Liquidacao",
                        valor=liquidacao.valor_total,
                        observacao="Liquidacao consolidada na tesouraria.",
                    )
                    for liquidacao in AdminDashboardService._liquidacoes_base(filters)
                ]
            )
            pagamentos = list(AdminDashboardService._payments_saida_base(filters))
            payment_context = AdminDashboardService._resolve_treasury_payment_context(
                pagamentos
            )
            rows.extend(
                [
                    AdminDashboardService._detail_row_from_tesouraria_pagamento(
                        pagamento,
                        origem="Saida operacional",
                        valor=-Decimal(
                            str(
                                payment_context.get(pagamento.id, {}).get("valor_total")
                                or Decimal("0.00")
                            )
                        ),
                        observacao="Auxilio liberado e repasse do agente liquidados na tesouraria.",
                    )
                    for pagamento in pagamentos
                ]
            )
            rows.extend(
                [
                    AdminDashboardService._detail_row_from_despesa(
                        despesa,
                        origem="Despesa paga",
                        valor=-despesa.valor,
                        observacao="Despesa operacional paga.",
                    )
                    for despesa in AdminDashboardService._despesas_base(filters)
                ]
            )
            return rows
        return []

    @staticmethod
    def _new_associados_details(filters: DashboardFilters, metric: str) -> list[dict[str, object]]:
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
            filters.day,
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
        AdminDashboardService._validate_day_with_competencia(filters, section="agentes")
        date_start, date_end = AdminDashboardService._resolved_date_window(
            filters.date_start,
            filters.date_end,
            filters.day,
        )
        ranking_payload = AdminDashboardService.agentes(filters)
        if metric == "agentes:volume_total":
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:volume",
                    )
                )
            return rows
        if metric == "agentes:inativos":
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:status:{Associado.Status.INATIVO}",
                    )
                )
            return rows
        if metric == "agentes:devolvidos":
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:devolvidos",
                    )
                )
            return rows
        if metric == "agentes:renovados":
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:renovados",
                    )
                )
            return rows
        if metric == "agentes:aptos_renovar":
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:aptos_renovar",
                    )
                )
            return rows
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
                    "valor": value_or_none(Decimal(str(item["volume_financeiro"]))),
                    "origem": "Agente no ranking",
                    "data_referencia": "",
                    "observacao": "Agente com atividade no periodo.",
                }
                for item in ranking_payload["ranking"]
            ]
        if metric in {"efetivacoes_total", "media_efetivacoes"}:
            rows: list[dict[str, object]] = []
            for item in ranking_payload["ranking"]:
                rows.extend(
                    AdminDashboardService._agents_details(
                        filters,
                        f"agente:{item['agent_id']}:efetivados",
                    )
                )
            return rows
        if metric.startswith("agente:"):
            metric_parts = metric.split(":")
            agent_id = metric_parts[1]
            metric_key = metric_parts[2]
            agent_filters = DashboardFilters(
                competencia=filters.competencia,
                date_start=date_start,
                date_end=date_end,
                day=filters.day,
                agent_id=int(agent_id),
                status=filters.status,
            )
            if metric_key == "volume":
                contracts = AdminDashboardService._contracts_base(int(agent_id)).filter(
                    auxilio_liberado_em__gte=date_start,
                    auxilio_liberado_em__lte=date_end,
                    auxilio_liberado_em__isnull=False,
                ).distinct()
                contracts = AdminDashboardService._filter_contracts_by_associado_status(
                    contracts,
                    filters.status,
                )
                return [
                    AdminDashboardService._detail_row_from_contract(
                        contrato,
                        origem="Auxilio liberado do agente",
                        valor=AdminDashboardService._contract_auxilio_liberado_value(
                            contrato
                        ),
                        data_referencia=contrato.auxilio_liberado_em,
                    )
                    for contrato in contracts
                ]
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
                    RenovacaoCicloService.listar_detalhes(
                        competencia=filters.competencia,
                        status="ciclo_renovado",
                    ),
                    int(agent_id),
                )
                rows = AdminDashboardService._filter_renewal_rows_by_status(
                    rows,
                    filters.status,
                    int(agent_id),
                )
                rows = AdminDashboardService._filter_renewal_rows_by_day(
                    rows,
                    filters.day,
                )
                return [
                    AdminDashboardService._detail_row_from_renewal_row(
                        row,
                        origem="Renovacao do agente",
                    )
                    for row in rows
                    if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]
                ]
            if metric_key == "aptos_renovar":
                rows = AdminDashboardService._filter_renewal_rows_by_agent(
                    RenovacaoCicloService.listar_detalhes(competencia=filters.competencia),
                    int(agent_id),
                )
                rows = AdminDashboardService._filter_renewal_rows_by_status(
                    rows,
                    filters.status,
                    int(agent_id),
                )
                rows = AdminDashboardService._filter_renewal_rows_by_day(
                    rows,
                    filters.day,
                )
                return [
                    AdminDashboardService._detail_row_from_renewal_row(
                        row,
                        origem="Apto a renovar do agente",
                    )
                    for row in rows
                    if row["status_visual"] == "apto_a_renovar"
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
            if metric_key == "devolvidos":
                return [
                    AdminDashboardService._detail_row_from_devolucao(
                        devolucao,
                        origem="Devolucao vinculada ao agente",
                    )
                    for devolucao in AdminDashboardService._devolucoes_base(agent_filters)
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
            if metric_key == "status" and len(metric_parts) == 4:
                target_status = metric_parts[3]
                associados = Associado.objects.filter(agente_responsavel_id=int(agent_id))
                if filters.status:
                    associados = associados.filter(status=filters.status)
                associados = associados.filter(status=target_status)
                return [
                    AdminDashboardService._detail_row_from_associado(
                        associado,
                        origem=f"Status {target_status} do agente",
                    )
                    for associado in associados
                ]
            return AdminDashboardService._agents_details(agent_filters, f"agente:{agent_id}:volume")
        return []


def value_or_none(value: Decimal | None) -> str:
    if value is None:
        return ""
    return f"{Decimal(str(value)):.2f}"
