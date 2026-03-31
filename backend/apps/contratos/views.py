from __future__ import annotations

from datetime import datetime

from django.db.models import CharField, Prefetch, Q, Value
from django.db.models.functions import Concat
from django.utils.dateparse import parse_date
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ReadOnlyModelViewSet

from apps.associados.models import Associado
from apps.accounts.permissions import IsTesoureiroOrAdmin
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_contract_visual_status_payload,
)
from apps.contratos.cycle_timeline import (
    get_contract_cycle_size,
)
from apps.esteira.models import EsteiraItem
from core.pagination import StandardResultsSetPagination

from .renovacao import RenovacaoCicloService, parse_competencia_query
from .models import Contrato
from .serializers import (
    ContratoListSerializer,
    ContratoResumoCardsSerializer,
    RenovacaoCicloItemSerializer,
    RenovacaoCicloMesSerializer,
    RenovacaoCicloResumoSerializer,
)


def parse_competencia_filter(value: str | None):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc


def filter_by_status_visual(queryset, status_visual: str):
    if status_visual == "liquidado":
        return queryset.filter(status=Contrato.Status.ENCERRADO)

    contratos = list(queryset)
    filtered_ids: list[int] = []
    for contrato in contratos:
        projection = build_contract_cycle_projection(contrato)
        has_unpaid_months = bool(projection["possui_meses_nao_descontados"])
        phase_slug = str(
            get_contract_visual_status_payload(
                contrato,
                projection=projection,
            )["status_visual_slug"]
        )

        if status_visual == "inadimplente" and has_unpaid_months:
            filtered_ids.append(contrato.id)
            continue

        if status_visual == "desativado" and (
            contrato.associado.status == Associado.Status.INATIVO
            or contrato.status in {Contrato.Status.ENCERRADO, Contrato.Status.CANCELADO}
        ):
            filtered_ids.append(contrato.id)
            continue

        if status_visual == "pendente" and phase_slug == "em_analise":
            filtered_ids.append(contrato.id)
            continue

        if status_visual == "ativo" and (
            not has_unpaid_months
            and phase_slug
            in {
                "ciclo_aberto",
                "apto_a_renovar",
                "renovacao_em_analise",
                "aguardando_coordenacao",
                "aprovado_para_renovacao",
                "ciclo_renovado",
            }
        ):
            filtered_ids.append(contrato.id)
            continue

    return queryset.filter(id__in=filtered_ids)


def _contract_total_cycles(contrato: Contrato) -> int:
    projection = build_contract_cycle_projection(contrato)
    return len(projection["cycles"])


def _contract_is_renewed(contrato: Contrato) -> bool:
    projection = build_contract_cycle_projection(contrato)
    if projection.get("refinanciamento_id"):
        return True
    return len(projection.get("cycles", [])) > 1


def filter_by_etapa_fluxo(queryset, etapa_fluxo: str):
    if etapa_fluxo == "tesouraria":
        return queryset.filter(
            associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
        )

    if etapa_fluxo == "concluido":
        return queryset.filter(
            Q(associado__esteira_item__etapa_atual=EsteiraItem.Etapa.CONCLUIDO)
            | Q(associado__esteira_item__isnull=True, auxilio_liberado_em__isnull=False)
        )

    if etapa_fluxo == "analise":
        return queryset.filter(
            Q(
                associado__esteira_item__etapa_atual__in=[
                    EsteiraItem.Etapa.CADASTRO,
                    EsteiraItem.Etapa.ANALISE,
                    EsteiraItem.Etapa.COORDENACAO,
                ]
            )
            | Q(associado__esteira_item__isnull=True, auxilio_liberado_em__isnull=True)
        )

    return queryset


class ContratoResultsPagination(StandardResultsSetPagination):
    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get(self.page_size_query_param) == "all":
            self.page_size = max(queryset.count(), 1)
        return super().paginate_queryset(queryset, request, view=view)


class ContratoViewSet(ReadOnlyModelViewSet):
    serializer_class = ContratoListSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ContratoResultsPagination
    search_fields = [
        "codigo",
        "associado__nome_completo",
        "associado__cpf_cnpj",
        "associado__matricula",
    ]
    ordering_fields = ["created_at", "data_contrato", "codigo", "valor_mensalidade"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Contrato.objects.none()

        queryset = (
            Contrato.objects.select_related("associado", "associado__esteira_item", "agente")
            .prefetch_related(
                Prefetch("ciclos__parcelas"),
                Prefetch("associado__refinanciamentos"),
                Prefetch("associado__pagamentos_mensalidades__refi_itens"),
                Prefetch("associado__tesouraria_pagamentos"),
            )
            .annotate(
                agente_nome=Concat(
                    "agente__first_name",
                    Value(" "),
                    "agente__last_name",
                    output_field=CharField(),
                ),
            )
        )

        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(agente=user)

        associado_filter = self.request.query_params.get("associado")
        if associado_filter:
            queryset = queryset.filter(
                Q(codigo__icontains=associado_filter)
                | Q(associado__nome_completo__icontains=associado_filter)
                | Q(associado__cpf_cnpj__icontains=associado_filter)
                | Q(associado__matricula__icontains=associado_filter)
                | Q(associado__matricula_orgao__icontains=associado_filter)
            )

        agente_filter = self.request.query_params.get("agente")
        if agente_filter and user.has_role("ADMIN"):
            if agente_filter.isdigit():
                queryset = queryset.filter(agente_id=int(agente_filter))
            else:
                queryset = queryset.filter(
                    Q(agente_nome__icontains=agente_filter)
                    | Q(agente__email__icontains=agente_filter)
                )

        status_visual_filter = self.request.query_params.get("status_visual")
        if status_visual_filter in {
            "pendente",
            "ativo",
            "desativado",
            "inadimplente",
            "liquidado",
        }:
            queryset = filter_by_status_visual(queryset, status_visual_filter)

        status_filter = self.request.query_params.get("status")
        if status_filter in {choice[0] for choice in Contrato.Status.choices}:
            queryset = queryset.filter(status=status_filter)

        etapa_fluxo = self.request.query_params.get("etapa_fluxo")
        if etapa_fluxo in {"analise", "tesouraria", "concluido"}:
            queryset = filter_by_etapa_fluxo(queryset, etapa_fluxo)

        competencia = parse_competencia_filter(
            self.request.query_params.get("competencia")
        )
        if competencia:
            queryset = queryset.filter(
                data_contrato__year=competencia.year,
                data_contrato__month=competencia.month,
            )

        data_inicio = parse_date(self.request.query_params.get("data_inicio") or "")
        if data_inicio:
            queryset = queryset.filter(data_contrato__gte=data_inicio)

        data_fim = parse_date(self.request.query_params.get("data_fim") or "")
        if data_fim:
            queryset = queryset.filter(data_contrato__lte=data_fim)

        mensalidades = self.request.query_params.get("mensalidades")
        if mensalidades and mensalidades.isdigit():
            mensalidades_count = int(mensalidades)
            contratos_filtrados = list(queryset)
            ids_filtrados: list[int] = []
            for contrato in contratos_filtrados:
                total = get_contract_cycle_size(contrato)
                projection = build_contract_cycle_projection(contrato)
                cycles = list(sorted(projection["cycles"], key=lambda item: item["numero"]))
                current_cycle = cycles[-1] if cycles else None
                pagas = (
                    sum(
                        1
                        for parcela in current_cycle["parcelas"]
                        if parcela["status"] == "descontado"
                    )
                    if current_cycle
                    else 0
                )
                if mensalidades_count >= total:
                    if pagas >= total:
                        ids_filtrados.append(contrato.id)
                elif pagas == mensalidades_count:
                        ids_filtrados.append(contrato.id)
            queryset = queryset.filter(id__in=ids_filtrados)

        numero_ciclos = self.request.query_params.get("numero_ciclos")
        if numero_ciclos and numero_ciclos.isdigit():
            contratos_filtrados = list(queryset)
            queryset = queryset.filter(
                id__in=[
                    contrato.id
                    for contrato in contratos_filtrados
                    if _contract_total_cycles(contrato) == int(numero_ciclos)
                ]
            )

        perfil_ciclo = (self.request.query_params.get("perfil_ciclo") or "").strip().lower()
        if perfil_ciclo in {"novo", "renovado"}:
            contratos_filtrados = list(queryset)
            filtered_ids = []
            for contrato in contratos_filtrados:
                renovado = _contract_is_renewed(contrato)
                if perfil_ciclo == "renovado" and renovado:
                    filtered_ids.append(contrato.id)
                if perfil_ciclo == "novo" and not renovado:
                    filtered_ids.append(contrato.id)
            queryset = queryset.filter(id__in=filtered_ids)

        raw_status_renovacao = self.request.query_params.getlist("status_renovacao")
        if len(raw_status_renovacao) == 1 and "," in raw_status_renovacao[0]:
            raw_status_renovacao = [
                item.strip()
                for item in raw_status_renovacao[0].split(",")
                if item.strip()
            ]
        status_renovacao_values = [item for item in raw_status_renovacao if item]
        if status_renovacao_values:
            contratos_filtrados = list(queryset)
            queryset = queryset.filter(
                id__in=[
                    contrato.id
                    for contrato in contratos_filtrados
                    if str(build_contract_cycle_projection(contrato)["status_renovacao"])
                    in status_renovacao_values
                ]
            )

        return queryset

    @action(detail=False, methods=["get"])
    def resumo(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        total = queryset.count()
        ativos = filter_by_status_visual(queryset, "ativo").count()
        pendentes = filter_by_status_visual(queryset, "pendente").count()
        inadimplentes = filter_by_status_visual(queryset, "inadimplente").count()
        liquidados = filter_by_status_visual(queryset, "liquidado").count()
        concluidos = queryset.filter(
            status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO]
        ).count()
        payload = {
            "total": total,
            "concluidos": concluidos,
            "ativos": ativos,
            "pendentes": pendentes,
            "inadimplentes": inadimplentes,
            "liquidados": liquidados,
        }
        return Response(ContratoResumoCardsSerializer(payload).data)


class RenovacaoCicloViewSet(GenericViewSet):
    queryset = Contrato.objects.none()
    serializer_class = RenovacaoCicloItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == "visao_mensal":
            return RenovacaoCicloResumoSerializer
        if self.action == "meses":
            return RenovacaoCicloMesSerializer
        return RenovacaoCicloItemSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="competencia", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="search", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="status", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="page", type=int, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="page_size", type=int, location=OpenApiParameter.QUERY),
        ],
        responses=RenovacaoCicloItemSerializer(many=True),
    )
    def list(self, request):
        competencia = parse_competencia_query(request.query_params.get("competencia"))
        rows = RenovacaoCicloService.listar_detalhes(
            competencia=competencia,
            search=request.query_params.get("search"),
            status=request.query_params.get("status"),
        )
        page = self.paginate_queryset(rows)
        serializer = RenovacaoCicloItemSerializer(page if page is not None else rows, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(name="competencia", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="search", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="status", type=str, location=OpenApiParameter.QUERY),
        ],
        responses=RenovacaoCicloResumoSerializer,
    )
    @action(detail=False, methods=["get"], url_path="visao-mensal")
    def visao_mensal(self, request):
        competencia = parse_competencia_query(request.query_params.get("competencia"))
        payload = RenovacaoCicloService.visao_mensal(
            competencia=competencia,
            search=request.query_params.get("search"),
            status=request.query_params.get("status"),
        )
        return Response(RenovacaoCicloResumoSerializer(payload).data)

    @extend_schema(responses=RenovacaoCicloMesSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def meses(self, request):
        payload = RenovacaoCicloService.listar_meses()
        return Response(RenovacaoCicloMesSerializer(payload, many=True).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(name="competencia", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="search", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="status", type=str, location=OpenApiParameter.QUERY),
        ],
    )
    @action(detail=False, methods=["get"])
    def exportar(self, request):
        competencia = parse_competencia_query(request.query_params.get("competencia"))
        rows = RenovacaoCicloService.listar_detalhes(
            competencia=competencia,
            search=request.query_params.get("search"),
            status=request.query_params.get("status"),
        )
        payload = {
            "competencia": competencia.strftime("%m/%Y"),
            "total": len(rows),
            "rows": rows,
        }
        return Response(payload)
