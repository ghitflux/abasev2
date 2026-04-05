from __future__ import annotations

from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import IsCoordenadorOrAdmin
from core.pagination import StandardResultsSetPagination

from .duplicidade import DuplicidadeFinanceiraService
from .models import ArquivoRetorno, ArquivoRetornoItem, DuplicidadeFinanceira
from .financeiro import build_financeiro_payload
from .serializers import (
    ArquivoRetornoDetailSerializer,
    DuplicidadeFinanceiraDescartarSerializer,
    ArquivoRetornoFinanceiroPayloadSerializer,
    ArquivoRetornoItemSerializer,
    ArquivoRetornoListSerializer,
    ArquivoRetornoUploadSerializer,
    DuplicidadeFinanceiraItemSerializer,
    DuplicidadeFinanceiraKpisSerializer,
    DuplicidadeFinanceiraResolverSerializer,
    DryRunResultadoSerializer,
)
from .services import ArquivoRetornoService


class UploadArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "20/hour"


class ReprocessarArquivoRetornoRateThrottle(UserRateThrottle):
    rate = "30/hour"


def parse_competencia_query(value: str | None):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc


def parse_periodo_query(value: str | None):
    if not value:
        return None
    if value in {"mes", "trimestre"}:
        return value
    raise ValidationError("Período inválido. Use 'mes' ou 'trimestre'.")


class ArquivoRetornoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ArquivoRetorno.objects.none()

        # Arquivos aguardando confirmação são transitórios e não aparecem no histórico/última
        queryset = ArquivoRetorno.objects.select_related("uploaded_by").exclude(
            status=ArquivoRetorno.Status.AGUARDANDO_CONFIRMACAO
        )
        competencia = parse_competencia_query(
            self.request.query_params.get("competencia")
        )
        periodo = parse_periodo_query(self.request.query_params.get("periodo"))

        if periodo and not competencia:
            raise ValidationError("O parâmetro periodo exige competencia.")

        if competencia:
            if periodo == "trimestre":
                quarter_start_month = ((competencia.month - 1) // 3) * 3 + 1
                quarter_end_month = quarter_start_month + 2
                queryset = queryset.filter(
                    competencia__year=competencia.year,
                    competencia__month__gte=quarter_start_month,
                    competencia__month__lte=quarter_end_month,
                )
            else:
                queryset = queryset.filter(
                    competencia__year=competencia.year,
                    competencia__month=competencia.month,
                )

        return queryset.order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {
            "descontados",
            "nao_descontados",
            "pendencias_manuais",
            "duplicidades",
            "encerramentos",
            "novos_ciclos",
            "aptos_renovar",
        }:
            return ArquivoRetornoItemSerializer
        if self.action == "upload":
            return ArquivoRetornoUploadSerializer
        if self.action in {"retrieve", "confirmar"}:
            return ArquivoRetornoDetailSerializer
        return ArquivoRetornoListSerializer

    def get_throttles(self):
        if self.action == "upload":
            return [UploadArquivoRetornoRateThrottle()]
        if self.action in {"reprocessar", "confirmar"}:
            return [ReprocessarArquivoRetornoRateThrottle()]
        return super().get_throttles()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="competencia",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Competência base no formato YYYY-MM.",
            ),
            OpenApiParameter(
                name="periodo",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Janela de filtro: mes ou trimestre.",
            ),
        ],
        responses=ArquivoRetornoListSerializer(many=True),
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=ArquivoRetornoUploadSerializer,
        responses=ArquivoRetornoDetailSerializer,
    )
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def upload(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        arquivo_retorno = ArquivoRetornoService().upload(
            serializer.validated_data["arquivo"],
            request.user,
        )
        return Response(ArquivoRetornoDetailSerializer(arquivo_retorno).data, status=201)

    @extend_schema(responses=ArquivoRetornoDetailSerializer)
    @action(detail=False, methods=["get"])
    def ultima(self, request):
        arquivo = self.get_queryset().first()
        if not arquivo:
            return Response(status=404)
        return Response(ArquivoRetornoDetailSerializer(arquivo).data)

    @extend_schema(responses=ArquivoRetornoDetailSerializer)
    @action(detail=True, methods=["post"])
    def reprocessar(self, request, pk=None):
        try:
            arquivo = ArquivoRetornoService().reprocessar(int(pk))
        except ArquivoRetorno.DoesNotExist:
            raise NotFound("Arquivo retorno não encontrado.")
        return Response(ArquivoRetornoDetailSerializer(arquivo).data)

    @extend_schema(
        responses=ArquivoRetornoDetailSerializer,
        description=(
            "Confirma a importação de um arquivo retorno em status 'aguardando_confirmacao'. "
            "Dispara o processamento assíncrono (Celery). "
            "Retorna o arquivo com status 'pendente' ou 'processando'."
        ),
    )
    @action(detail=True, methods=["post"])
    def confirmar(self, request, pk=None):
        try:
            arquivo = ArquivoRetornoService().confirmar(int(pk))
        except ArquivoRetorno.DoesNotExist:
            raise NotFound("Arquivo retorno não encontrado.")
        return Response(ArquivoRetornoDetailSerializer(arquivo).data)

    @extend_schema(
        responses={204: None},
        description=(
            "Cancela e remove (soft-delete) um arquivo retorno em status 'aguardando_confirmacao'. "
            "Não afeta arquivos já processados ou em processamento."
        ),
    )
    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        try:
            ArquivoRetornoService().cancelar(int(pk))
        except ArquivoRetorno.DoesNotExist:
            raise NotFound("Arquivo retorno não encontrado.")
        return Response(status=204)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"])
    def descontados(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="nao-descontados")
    def nao_descontados(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="pendencias-manuais")
    def pendencias_manuais(self, request, pk=None):
        queryset = self._filtrar_itens(pk, resultado=ArquivoRetornoItem.ResultadoProcessamento.PENDENCIA_MANUAL)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"])
    def duplicidades(self, request, pk=None):
        queryset = self._filtrar_itens(
            pk,
            resultado=ArquivoRetornoItem.ResultadoProcessamento.DUPLICIDADE,
        )
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"])
    def encerramentos(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_encerramento=True)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoItemSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="novos-ciclos")
    def novos_ciclos(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_novo_ciclo=True)
        return self._paginate_items(queryset)

    @extend_schema(
        responses=ArquivoRetornoItemSerializer(many=True),
        description=(
            "Lista os itens do arquivo retorno cujo processamento gerou elegibilidade "
            "de renovação (gerou_novo_ciclo=True). Esses associados podem solicitar renovação."
        ),
    )
    @action(detail=True, methods=["get"], url_path="aptos-renovar")
    def aptos_renovar(self, request, pk=None):
        queryset = self._filtrar_itens(pk, gerou_novo_ciclo=True)
        return self._paginate_items(queryset)

    @extend_schema(responses=ArquivoRetornoFinanceiroPayloadSerializer)
    @action(detail=True, methods=["get"])
    def financeiro(self, request, pk=None):
        arquivo = self.get_object()
        payload = build_financeiro_payload(competencia=arquivo.competencia)
        return Response(ArquivoRetornoFinanceiroPayloadSerializer(payload).data)

    def _filtrar_itens(self, pk: str, *, resultado: str | None = None, gerou_encerramento: bool | None = None, gerou_novo_ciclo: bool | None = None):
        queryset = ArquivoRetornoItem.objects.filter(arquivo_retorno_id=pk).select_related(
            "associado",
            "associado__agente_responsavel",
            "parcela",
            "parcela__ciclo",
            "parcela__ciclo__contrato",
            "parcela__ciclo__contrato__agente",
        )
        if resultado:
            queryset = queryset.filter(resultado_processamento=resultado)
        if gerou_encerramento is not None:
            queryset = queryset.filter(gerou_encerramento=gerou_encerramento)
        if gerou_novo_ciclo is not None:
            queryset = queryset.filter(gerou_novo_ciclo=gerou_novo_ciclo)
        return queryset.order_by("linha_numero")

    def _paginate_items(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class DuplicidadeFinanceiraViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = DuplicidadeFinanceira.objects.none()
    serializer_class = DuplicidadeFinanceiraItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def list(self, request, *args, **kwargs):  # noqa: A003
        competencia = parse_competencia_query(request.query_params.get("competencia"))
        arquivo_retorno_id = request.query_params.get("arquivo_retorno_id")
        payload = DuplicidadeFinanceiraService.listar(
            search=(request.query_params.get("search") or "").strip() or None,
            status=(request.query_params.get("status") or "").strip() or None,
            motivo=(request.query_params.get("motivo") or "").strip() or None,
            competencia=competencia,
            agente=(request.query_params.get("agente") or "").strip() or None,
            arquivo_retorno_id=int(arquivo_retorno_id) if (arquivo_retorno_id or "").isdigit() else None,
        )
        page = self.paginate_queryset(payload.rows)
        serializer = self.get_serializer(page if page is not None else payload.rows, many=True)
        kpis = DuplicidadeFinanceiraKpisSerializer(payload.kpis).data
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="resolver-devolucao")
    def resolver_devolucao(self, request, pk=None):
        serializer = DuplicidadeFinanceiraResolverSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        duplicidade = DuplicidadeFinanceiraService.resolver_com_devolucao(
            int(pk),
            data_devolucao=serializer.validated_data["data_devolucao"],
            valor=serializer.validated_data["valor"],
            motivo=serializer.validated_data["motivo"],
            comprovantes=serializer.validated_data["comprovantes"],
            user=request.user,
        )
        payload = DuplicidadeFinanceiraService.listar().rows
        row = [item for item in payload if item["id"] == duplicidade.id]
        data = self.get_serializer(row[:1], many=True).data
        return Response(data[0] if data else {"id": duplicidade.id})

    @action(detail=True, methods=["post"], url_path="descartar")
    def descartar(self, request, pk=None):
        serializer = DuplicidadeFinanceiraDescartarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        duplicidade = DuplicidadeFinanceiraService.descartar(
            int(pk),
            motivo=serializer.validated_data["motivo"],
            user=request.user,
        )
        payload = DuplicidadeFinanceiraService.listar().rows
        row = [item for item in payload if item["id"] == duplicidade.id]
        data = self.get_serializer(row[:1], many=True).data
        return Response(data[0] if data else {"id": duplicidade.id})
