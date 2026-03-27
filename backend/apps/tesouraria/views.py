from __future__ import annotations

from datetime import date, datetime

from django.db.models import Prefetch, Q
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, permissions
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from apps.accounts.permissions import (
    IsAgenteOrTesoureiroOrAdmin,
    IsCoordenadorOrTesoureiroOrAdmin,
    IsTesoureiroOrAdmin,
)
from apps.associados.models import Associado
from apps.associados.serializers import DadosBancariosSerializer
from apps.contratos.cycle_projection import build_contract_cycle_projection
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.financeiro.models import Despesa
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.tesouraria.initial_payment import build_initial_payment_payload
from apps.tesouraria.models import (
    Confirmacao,
    DevolucaoAssociado,
    LiquidacaoContrato,
    Pagamento,
    PagamentoNotificacao,
)
from apps.tesouraria.devolucao import DevolucaoAssociadoService
from apps.tesouraria.liquidacao import LiquidacaoContratoService
from core.pagination import StandardResultsSetPagination

from .serializers import (
    AgentePagamentoContratoSerializer,
    BaixaManualItemSerializer,
    ConfirmacaoLinkSerializer,
    ConfirmacaoListSerializer,
    CongelarContratoSerializer,
    DevolucaoAssociadoListSerializer,
    DevolucaoContratoListSerializer,
    DevolucaoKpisSerializer,
    DespesaAnexarSerializer,
    DespesaCategoriaSugestaoSerializer,
    DespesaKpisSerializer,
    DespesaListSerializer,
    DespesaResultadoMensalDetalheSerializer,
    DespesaResultadoMensalSerializer,
    DespesaWriteSerializer,
    DarBaixaManualSerializer,
    EfetivarContratoSerializer,
    ExcluirDevolucaoSerializer,
    ExcluirLiquidacaoSerializer,
    LiquidacaoContratoListSerializer,
    LiquidacaoKpisSerializer,
    LiquidarContratoSerializer,
    RegistrarDevolucaoSerializer,
    ReverterLiquidacaoSerializer,
    ReverterDevolucaoSerializer,
    TesourariaContratoListSerializer,
    SubstituirComprovanteSerializer,
)
from .services import (
    BaixaManualService,
    ConfirmacaoService,
    DespesaService,
    TesourariaService,
    parse_competencia,
)


def parse_month_filter(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None


def parse_date_filter(value: str | None):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


class TesourariaContratoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    GenericViewSet,
):
    serializer_class = TesourariaContratoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        competencia = parse_competencia(self.request.query_params.get("competencia"))
        return TesourariaService.listar_contratos_pendentes(
            competencia=competencia,
            data_inicio=self.request.query_params.get("data_inicio"),
            data_fim=self.request.query_params.get("data_fim"),
            search=self.request.query_params.get("search"),
            pagamento=self.request.query_params.get("pagamento"),
            agente=self.request.query_params.get("agente"),
            status_contrato=self.request.query_params.get("status_contrato"),
            situacao_esteira=self.request.query_params.get("situacao_esteira"),
        )

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser])
    def efetivar(self, request, pk=None):
        payload = EfetivarContratoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contrato = TesourariaService.efetivar_contrato(
            pk,
            payload.validated_data["comprovante_associado"],
            payload.validated_data["comprovante_agente"],
            request.user,
        )
        serializer = self.get_serializer(contrato)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser], url_path="substituir-comprovante")
    def substituir_comprovante(self, request, pk=None):
        payload = SubstituirComprovanteSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contrato = TesourariaService.substituir_comprovante(
            pk,
            papel=payload.validated_data["papel"],
            arquivo=payload.validated_data["arquivo"],
            user=request.user,
        )
        serializer = self.get_serializer(contrato)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def congelar(self, request, pk=None):
        payload = CongelarContratoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        contrato = TesourariaService.congelar_contrato(
            pk, payload.validated_data["motivo"], request.user
        )
        serializer = self.get_serializer(contrato)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="dados-bancarios")
    def dados_bancarios(self, request, pk=None):
        dados = TesourariaService.obter_dados_bancarios(pk)
        serializer = DadosBancariosSerializer(dados)
        return Response(serializer.data)


class ConfirmacaoViewSet(GenericViewSet):
    queryset = Confirmacao.objects.none()
    serializer_class = ConfirmacaoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def list(self, request):
        competencia = parse_competencia(request.query_params.get("competencia"))
        search = request.query_params.get("search", "").strip().lower()
        rows = ConfirmacaoService.listar_por_competencia(competencia)
        if search:
            rows = [row for row in rows if search in row["nome"].lower()]

        page = self.paginate_queryset(rows)
        serializer = self.get_serializer(page if page is not None else rows, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def link(self, request, pk=None):
        payload = ConfirmacaoLinkSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = ConfirmacaoService.salvar_link_chamada(pk, payload.validated_data["link"])
        return Response(self.get_serializer(row).data)

    @action(detail=True, methods=["post"], url_path="confirmar-ligacao")
    def confirmar_ligacao(self, request, pk=None):
        row = ConfirmacaoService.confirmar_ligacao(pk, request.user)
        return Response(self.get_serializer(row).data)

    @action(detail=True, methods=["post"], url_path="confirmar-averbacao")
    def confirmar_averbacao(self, request, pk=None):
        row = ConfirmacaoService.confirmar_averbacao(pk, request.user)
        return Response(self.get_serializer(row).data)


class AgentePagamentoViewSet(mixins.ListModelMixin, GenericViewSet):
    serializer_class = AgentePagamentoContratoSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgenteOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Contrato.objects.none()

        competencia = parse_month_filter(self.request.query_params.get("mes"))
        queryset = (
            Contrato.objects.select_related("associado", "agente")
            .prefetch_related(
                Prefetch(
                    "comprovantes",
                    queryset=Comprovante.objects.filter(
                        refinanciamento__isnull=True
                    ).select_related("enviado_por"),
                ),
                Prefetch(
                    "ciclos",
                    queryset=Ciclo.objects.prefetch_related(
                        Prefetch(
                            "parcelas",
                            queryset=Parcela.objects.prefetch_related(
                                Prefetch(
                                    "itens_retorno",
                                    queryset=ArquivoRetornoItem.objects.select_related(
                                        "arquivo_retorno"
                                    ).order_by("-created_at"),
                                )
                            ).order_by("numero"),
                        )
                    ).order_by("numero"),
                ),
                Prefetch(
                    "associado__pagamentos_mensalidades",
                    queryset=PagamentoMensalidade.objects.order_by("-referencia_month"),
                ),
                Prefetch(
                    "associado__tesouraria_pagamentos",
                    queryset=Pagamento.all_objects.order_by("created_at", "id"),
                ),
            )
            .order_by("-created_at")
            .distinct()
        )

        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            queryset = queryset.filter(agente=user)

        search = (self.request.query_params.get("search") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(codigo__icontains=search)
                | Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
            )

        status_filter = (self.request.query_params.get("status") or "").strip()
        if status_filter in {choice[0] for choice in Contrato.Status.choices}:
            queryset = queryset.filter(status=status_filter)

        associado_status = (self.request.query_params.get("associado_status") or "").strip()
        if associado_status in {choice[0] for choice in Associado.Status.choices}:
            queryset = queryset.filter(associado__status=associado_status)

        agente_filter = (self.request.query_params.get("agente") or "").strip()
        if agente_filter and (user.has_role("ADMIN") or user.has_role("TESOUREIRO")):
            if agente_filter.isdigit():
                queryset = queryset.filter(agente_id=int(agente_filter))
            else:
                queryset = queryset.filter(
                    Q(agente__first_name__icontains=agente_filter)
                    | Q(agente__last_name__icontains=agente_filter)
                    | Q(agente__email__icontains=agente_filter)
                )

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["mes_filter"] = parse_month_filter(
            self.request.query_params.get("mes")
        )
        if hasattr(self, "_contract_projection_cache"):
            context["_contract_projection_cache"] = self._contract_projection_cache
        return context

    def _notification_queryset(self):
        user = self.request.user
        if user.has_role("AGENTE") and not user.has_role("ADMIN"):
            return PagamentoNotificacao.objects.filter(
                agente=user,
                lida_em__isnull=True,
            )
        return PagamentoNotificacao.objects.none()

    def list(self, request, *args, **kwargs):  # noqa: A003
        queryset = self.filter_queryset(self.get_queryset())
        competencia = parse_month_filter(request.query_params.get("mes"))

        contratos = list(queryset)
        projection_cache = {
            contrato.id: build_contract_cycle_projection(contrato)
            for contrato in contratos
        }
        self._contract_projection_cache = projection_cache
        initial_payment_status = (request.query_params.get("pagamento_inicial_status") or "").strip()
        ciclos_filter = (request.query_params.get("numero_ciclos") or "").strip()
        data_inicio = self.request.query_params.get("data_inicio")
        data_fim = self.request.query_params.get("data_fim")

        def parcela_no_recorte(parcela: dict[str, object]) -> bool:
            if competencia is None:
                return True
            referencia_mes = parcela["referencia_mes"]
            return (
                referencia_mes.year == competencia.year
                and referencia_mes.month == competencia.month
            )

        if competencia is not None:
            contratos = [
                contrato
                for contrato in contratos
                if any(
                    parcela_no_recorte(parcela)
                    for ciclo in projection_cache[contrato.id]["cycles"]
                    for parcela in ciclo["parcelas"]
                )
                or (
                    contrato.data_contrato.year == competencia.year
                    and contrato.data_contrato.month == competencia.month
                )
            ]

        if initial_payment_status:
            contratos = [
                contrato
                for contrato in contratos
                if build_initial_payment_payload(contrato).status == initial_payment_status
            ]

        if ciclos_filter.isdigit():
            total_ciclos = int(ciclos_filter)
            contratos = [
                contrato
                for contrato in contratos
                if len(projection_cache[contrato.id]["cycles"]) == total_ciclos
            ]

        if data_inicio or data_fim:
            data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
            data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else None

            def within_date_range(contrato: Contrato) -> bool:
                payload = build_initial_payment_payload(contrato)
                reference = payload.paid_at
                if reference is not None:
                    reference_date = timezone.localtime(reference).date()
                else:
                    reference_date = contrato.data_contrato
                if data_inicio_dt and reference_date < data_inicio_dt:
                    return False
                if data_fim_dt and reference_date > data_fim_dt:
                    return False
                return True

            contratos = [contrato for contrato in contratos if within_date_range(contrato)]

        resumo = {
            "total": len(contratos),
            "efetivados": sum(
                1 for contrato in contratos if contrato.auxilio_liberado_em is not None
            ),
            "com_anexos": sum(
                1
                for contrato in contratos
                if contrato.comprovantes.filter(refinanciamento__isnull=True).exists()
            ),
            "parcelas_pagas": sum(
                1
                for contrato in contratos
                for ciclo in projection_cache[contrato.id]["cycles"]
                for parcela in ciclo["parcelas"]
                if parcela_no_recorte(parcela)
                and parcela["status"] == Parcela.Status.DESCONTADO
            ),
            "parcelas_total": sum(
                1
                for contrato in contratos
                for ciclo in projection_cache[contrato.id]["cycles"]
                for parcela in ciclo["parcelas"]
                if parcela_no_recorte(parcela)
            ),
        }

        page = self.paginate_queryset(contratos)
        serializer = self.get_serializer(page if page is not None else contratos, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["resumo"] = resumo
            return response
        return Response({"results": serializer.data, "resumo": resumo})

    @action(detail=False, methods=["get"], url_path="notificacoes")
    def notificacoes(self, request):
        return Response({"unread_count": self._notification_queryset().count()})

    @action(detail=False, methods=["post"], url_path="notificacoes/marcar-lidas")
    def marcar_notificacoes_lidas(self, request):
        now = timezone.now()
        marked_count = self._notification_queryset().update(
            lida_em=now,
            updated_at=now,
        )
        return Response({"marked_count": marked_count})


class BaixaManualViewSet(mixins.ListModelMixin, GenericViewSet):
    serializer_class = BaixaManualItemSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        competencia = parse_month_filter(self.request.query_params.get("competencia"))
        return BaixaManualService.listar_parcelas_pendentes(
            search=self.request.query_params.get("search"),
            status_filter=self.request.query_params.get("status"),
            competencia=competencia,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        kpis = BaixaManualService.kpis()
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="dar-baixa", parser_classes=[MultiPartParser])
    def dar_baixa(self, request, pk=None):
        payload = DarBaixaManualSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        baixa = BaixaManualService.dar_baixa(
            int(pk),
            payload.validated_data["comprovante"],
            payload.validated_data["valor_pago"],
            payload.validated_data.get("observacao", ""),
            request.user,
        )
        return Response(
            {"id": baixa.id, "message": "Baixa manual registrada com sucesso."},
            status=201,
        )


class LiquidacaoContratoViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = LiquidacaoContrato.objects.none()
    serializer_class = LiquidacaoContratoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        parameters=[
            OpenApiParameter(name="status", type=OpenApiTypes.STR),
            OpenApiParameter(name="search", type=OpenApiTypes.STR),
            OpenApiParameter(name="competencia", type=OpenApiTypes.DATE),
            OpenApiParameter(name="estado", type=OpenApiTypes.STR),
            OpenApiParameter(name="contract_id", type=OpenApiTypes.INT),
            OpenApiParameter(name="agente", type=OpenApiTypes.STR),
            OpenApiParameter(name="status_associado", type=OpenApiTypes.STR),
            OpenApiParameter(name="etapa_fluxo", type=OpenApiTypes.STR),
            OpenApiParameter(name="data_inicio", type=OpenApiTypes.DATE),
            OpenApiParameter(name="data_fim", type=OpenApiTypes.DATE),
        ]
    )
    def list(self, request, *args, **kwargs):  # noqa: A003
        competencia = parse_month_filter(request.query_params.get("competencia"))
        payload = LiquidacaoContratoService.listar(
            listing_status=request.query_params.get("status") or "elegivel",
            search=(request.query_params.get("search") or "").strip() or None,
            competencia=competencia,
            estado=(request.query_params.get("estado") or "").strip() or None,
            contract_id=(
                int(request.query_params["contract_id"])
                if (request.query_params.get("contract_id") or "").isdigit()
                else None
            ),
            agente=(request.query_params.get("agente") or "").strip() or None,
            status_associado=(
                (request.query_params.get("status_associado") or "").strip() or None
            ),
            etapa_fluxo=(request.query_params.get("etapa_fluxo") or "").strip() or None,
            data_inicio=parse_date_filter(request.query_params.get("data_inicio")),
            data_fim=parse_date_filter(request.query_params.get("data_fim")),
        )
        page = self.paginate_queryset(payload.rows)
        serializer = self.get_serializer(page if page is not None else payload.rows, many=True)
        kpis = LiquidacaoKpisSerializer(payload.kpis).data
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="liquidar")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def liquidar(self, request, pk=None):
        payload = LiquidarContratoSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        payload.is_valid(raise_exception=True)
        liquidacao = LiquidacaoContratoService.liquidar_contrato(
            int(pk),
            comprovantes=payload.validated_data["comprovantes"],
            origem_solicitacao=payload.validated_data["origem_solicitacao"],
            data_liquidacao=payload.validated_data["data_liquidacao"],
            valor_total=payload.validated_data["valor_total"],
            observacao=payload.validated_data["observacao"],
            user=request.user,
        )
        row = LiquidacaoContratoService.listar(
            listing_status="liquidado",
            search=liquidacao.contrato.codigo,
            contract_id=liquidacao.contrato_id,
        ).rows
        serialized = self.get_serializer(row[:1], many=True).data
        return Response(serialized[0] if serialized else {"id": liquidacao.id}, status=201)

    @action(detail=True, methods=["post"], url_path="reverter")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def reverter(self, request, pk=None):
        payload = ReverterLiquidacaoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        liquidacao = LiquidacaoContratoService.reverter_liquidacao(
            int(pk),
            motivo_reversao=payload.validated_data["motivo_reversao"],
            user=request.user,
        )
        row = LiquidacaoContratoService.listar(
            listing_status="liquidado",
            search=liquidacao.contrato.codigo,
            contract_id=liquidacao.contrato_id,
        ).rows
        serialized = self.get_serializer(row[:1], many=True).data
        return Response(serialized[0] if serialized else {"id": liquidacao.id})

    @action(detail=True, methods=["post"], url_path="excluir")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def excluir(self, request, pk=None):
        payload = ExcluirLiquidacaoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        liquidacao = LiquidacaoContratoService.excluir_liquidacao(
            int(pk),
            motivo_exclusao=payload.validated_data["motivo_exclusao"],
            user=request.user,
        )
        return Response(
            {
                "id": liquidacao.id,
                "message": "Registro de liquidação excluído com sucesso.",
            }
        )


class DevolucaoContratoViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = Contrato.objects.none()
    serializer_class = DevolucaoContratoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def list(self, request, *args, **kwargs):  # noqa: A003
        competencia = parse_month_filter(request.query_params.get("competencia"))
        payload = DevolucaoAssociadoService.listar_contratos(
            search=(request.query_params.get("search") or "").strip() or None,
            estado=(request.query_params.get("estado") or "").strip() or None,
            competencia=competencia,
            contract_id=(
                int(request.query_params["contract_id"])
                if (request.query_params.get("contract_id") or "").isdigit()
                else None
            ),
            fluxo=(request.query_params.get("fluxo") or "").strip() or None,
        )
        page = self.paginate_queryset(payload.rows)
        serializer = self.get_serializer(page if page is not None else payload.rows, many=True)
        kpis = DevolucaoKpisSerializer(payload.kpis).data
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="registrar")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def registrar(self, request, pk=None):
        payload = RegistrarDevolucaoSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        payload.is_valid(raise_exception=True)
        devolucao = DevolucaoAssociadoService.registrar(
            int(pk),
            tipo=payload.validated_data["tipo"],
            data_devolucao=payload.validated_data["data_devolucao"],
            quantidade_parcelas=payload.validated_data["quantidade_parcelas"],
            valor=payload.validated_data["valor"],
            motivo=payload.validated_data["motivo"],
            comprovantes=payload.validated_data["comprovantes"],
            competencia_referencia=payload.validated_data.get("competencia_referencia"),
            user=request.user,
        )
        row = DevolucaoAssociadoService.listar_historico(
            contract_id=devolucao.contrato_id,
        ).rows
        matched = [item for item in row if item["devolucao_id"] == devolucao.id]
        serialized = DevolucaoAssociadoListSerializer(
            matched[:1],
            many=True,
            context=self.get_serializer_context(),
        ).data
        return Response(serialized[0] if serialized else {"id": devolucao.id}, status=201)


class DevolucaoAssociadoViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = DevolucaoAssociado.objects.none()
    serializer_class = DevolucaoAssociadoListSerializer
    permission_classes = [permissions.IsAuthenticated, IsCoordenadorOrTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def list(self, request, *args, **kwargs):  # noqa: A003
        competencia = parse_month_filter(request.query_params.get("competencia"))
        payload = DevolucaoAssociadoService.listar_historico(
            search=(request.query_params.get("search") or "").strip() or None,
            tipo=(request.query_params.get("tipo") or "").strip() or None,
            status=(request.query_params.get("status") or "").strip() or None,
            competencia=competencia,
            contract_id=(
                int(request.query_params["contract_id"])
                if (request.query_params.get("contract_id") or "").isdigit()
                else None
            ),
            fluxo=(request.query_params.get("fluxo") or "").strip() or None,
        )
        page = self.paginate_queryset(payload.rows)
        serializer = self.get_serializer(page if page is not None else payload.rows, many=True)
        kpis = DevolucaoKpisSerializer(payload.kpis).data
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    @action(detail=True, methods=["post"], url_path="reverter")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def reverter(self, request, pk=None):
        payload = ReverterDevolucaoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        devolucao = DevolucaoAssociadoService.reverter(
            int(pk),
            motivo_reversao=payload.validated_data["motivo_reversao"],
            user=request.user,
        )
        row = DevolucaoAssociadoService.listar_historico(
            contract_id=devolucao.contrato_id,
        ).rows
        matched = [item for item in row if item["devolucao_id"] == devolucao.id]
        serialized = self.get_serializer(
            matched[:1],
            many=True,
            context=self.get_serializer_context(),
        ).data
        return Response(serialized[0] if serialized else {"id": devolucao.id})

    @action(detail=True, methods=["post"], url_path="excluir")
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
            )
        ]
    )
    def excluir(self, request, pk=None):
        payload = ExcluirDevolucaoSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        devolucao = DevolucaoAssociadoService.excluir(
            int(pk),
            motivo_exclusao=payload.validated_data["motivo_exclusao"],
            user=request.user,
        )
        return Response(
            {
                "id": devolucao.id,
                "message": "Registro de devolução excluído com sucesso.",
            }
        )


class DespesaViewSet(ModelViewSet):
    queryset = Despesa.objects.none()
    permission_classes = [permissions.IsAuthenticated, IsTesoureiroOrAdmin]
    pagination_class = StandardResultsSetPagination
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        competencia_param = self.request.query_params.get("competencia")
        competencia = parse_competencia(competencia_param) if competencia_param else None
        return DespesaService.listar_despesas(
            competencia=competencia,
            search=self.request.query_params.get("search"),
            status=self.request.query_params.get("status"),
            status_anexo=self.request.query_params.get("status_anexo"),
            tipo=self.request.query_params.get("tipo"),
        )

    def get_serializer_class(self):
        if self.action in {"create", "partial_update", "update"}:
            return DespesaWriteSerializer
        return DespesaListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):  # noqa: A003
        queryset = self.filter_queryset(self.get_queryset())
        kpis = DespesaKpisSerializer(DespesaService.kpis(queryset)).data
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            response = self.get_paginated_response(serializer.data)
            response.data["kpis"] = kpis
            return response
        return Response({"results": serializer.data, "kpis": kpis})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data, status=201)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        despesa = serializer.save()
        output = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(output.data)

    @action(detail=True, methods=["post"], url_path="anexar")
    def anexar(self, request, pk=None):
        payload = DespesaAnexarSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        despesa = DespesaService.anexar(self.get_object(), payload.validated_data["anexo"])
        serializer = DespesaListSerializer(despesa, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="categorias")
    def categorias(self, request):
        payload = DespesaService.sugerir_categorias(
            (request.query_params.get("search") or "").strip() or None
        )
        serializer = DespesaCategoriaSugestaoSerializer(payload, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="resultado-mensal")
    def resultado_mensal(self, request):
        competencia_param = request.query_params.get("competencia")
        competencia = parse_competencia(competencia_param) if competencia_param else None
        payload = DespesaService.resultado_mensal(competencia=competencia)
        serializer = DespesaResultadoMensalSerializer(payload)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="resultado-mensal/detalhe")
    def resultado_mensal_detalhe(self, request):
        mes_param = request.query_params.get("mes")
        mes = parse_competencia(mes_param) if mes_param else timezone.localdate().replace(day=1)
        payload = DespesaService.resultado_mensal_detalhe(mes=mes)
        serializer = DespesaResultadoMensalDetalheSerializer(payload)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        DespesaService.excluir(self.get_object())
        return Response(status=204)
