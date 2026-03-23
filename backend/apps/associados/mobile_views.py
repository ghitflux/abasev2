"""
Views mobile self-service — /api/v1/app/

Endpoints exclusivos para o app mobile do associado (role ASSOCIADO).
Cada view resolve o associado vinculado ao request.user via user.associado.
"""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAssociadoOrAdmin
from apps.contratos.models import Ciclo, Contrato, Parcela

from .models import Associado, Documento
from .serializers import DocumentoCreateSerializer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_associado_or_404(user) -> Associado:
    """Retorna o Associado vinculado ao user ou lança 404."""
    from rest_framework.exceptions import NotFound

    try:
        return user.associado
    except Associado.DoesNotExist:
        raise NotFound("Nenhum associado vinculado a este usuário.")


# ---------------------------------------------------------------------------
# Serializers inline (leves, voltados para mobile)
# ---------------------------------------------------------------------------

class _ParcelaMobileSerializer(serializers.Serializer):
    numero = serializers.IntegerField()
    referencia_mes = serializers.DateField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = serializers.DateField()
    status = serializers.CharField()
    data_pagamento = serializers.DateField(allow_null=True)


class _CicloMobileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    numero = serializers.IntegerField()
    data_inicio = serializers.DateField()
    data_fim = serializers.DateField()
    status = serializers.CharField()
    valor_total = serializers.DecimalField(max_digits=10, decimal_places=2)
    parcelas = _ParcelaMobileSerializer(many=True)


class _ContratoResumoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    status = serializers.CharField()
    prazo_meses = serializers.IntegerField()
    valor_mensalidade = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_primeira_mensalidade = serializers.DateField(allow_null=True)


class _AssociadoMobileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome_completo = serializers.CharField()
    cpf_cnpj = serializers.CharField()
    matricula = serializers.CharField()
    email = serializers.CharField()
    telefone = serializers.CharField()
    status = serializers.CharField()
    orgao_publico = serializers.CharField()
    cargo = serializers.CharField()


class _PendenciaMobileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.CharField()
    descricao = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()


class _ResumoFinanceiroMobileSerializer(serializers.Serializer):
    parcelas_pagas = serializers.IntegerField()
    parcelas_total = serializers.IntegerField()
    valor_mensalidade = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        allow_null=True,
    )
    proximo_vencimento = serializers.DateField(allow_null=True)
    em_atraso = serializers.IntegerField()


class _AppMeResponseSerializer(serializers.Serializer):
    associado = _AssociadoMobileSerializer()
    contratos = _ContratoResumoSerializer(many=True)
    resumo = _ResumoFinanceiroMobileSerializer()
    pendencias = _PendenciaMobileSerializer(many=True)


class _AppMensalidadesResponseSerializer(serializers.Serializer):
    ciclos = _CicloMobileSerializer(many=True)


class _AppAntecipacaoItemSerializer(serializers.Serializer):
    referencia_mes = serializers.DateField()
    valor = serializers.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = serializers.DateField(allow_null=True)
    numero_parcela = serializers.IntegerField()
    ciclo_numero = serializers.IntegerField()


class _AppAntecipacaoResponseSerializer(serializers.Serializer):
    historico = _AppAntecipacaoItemSerializer(many=True)


class _AppPendenciasResponseSerializer(serializers.Serializer):
    pendencias = _PendenciaMobileSerializer(many=True)


class _AppDocumentoUploadResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    tipo = serializers.CharField()
    status = serializers.CharField()
    observacao = serializers.CharField()


# ---------------------------------------------------------------------------
# AppMeView — GET /api/v1/app/me/
# ---------------------------------------------------------------------------

class AppMeView(APIView):
    """
    Retorna os dados consolidados do associado logado:
    dados pessoais, contratos resumidos, resumo financeiro e pendências.
    """
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: _AppMeResponseSerializer})
    def get(self, request):
        associado = _get_associado_or_404(request.user)

        contratos_qs = (
            Contrato.objects.filter(
                associado=associado,
            )
            .exclude(status=Contrato.Status.CANCELADO)
            .prefetch_related("ciclos__parcelas")
            .order_by("-created_at")
        )

        contratos_data = _ContratoResumoSerializer(contratos_qs, many=True).data

        # Resumo financeiro a partir das parcelas de todos os ciclos
        resumo = _build_resumo(associado, contratos_qs)

        # Pendências via esteira
        pendencias_data = _build_pendencias(associado)

        return Response(
            {
                "associado": _AssociadoMobileSerializer(associado).data,
                "contratos": contratos_data,
                "resumo": resumo,
                "pendencias": pendencias_data,
            }
        )


# ---------------------------------------------------------------------------
# AppMensalidadesView — GET /api/v1/app/mensalidades/
# ---------------------------------------------------------------------------

class AppMensalidadesView(APIView):
    """
    Lista ciclos com parcelas do associado logado, agrupados por contrato.
    """
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: _AppMensalidadesResponseSerializer})
    def get(self, request):
        associado = _get_associado_or_404(request.user)

        ciclos = (
            Ciclo.objects.filter(contrato__associado=associado)
            .exclude(contrato__status=Contrato.Status.CANCELADO)
            .select_related("contrato")
            .prefetch_related("parcelas")
            .order_by("-contrato_id", "-numero")
        )

        data = _CicloMobileSerializer(ciclos, many=True).data
        return Response({"ciclos": data})


# ---------------------------------------------------------------------------
# AppAntecipacaoView — GET /api/v1/app/antecipacao/
# ---------------------------------------------------------------------------

class AppAntecipacaoView(APIView):
    """
    Histórico de parcelas descontadas (pagas) do associado logado.
    Simula o endpoint legado /api/app/antecipacao/historico.
    """
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: _AppAntecipacaoResponseSerializer})
    def get(self, request):
        associado = _get_associado_or_404(request.user)

        parcelas = (
            Parcela.objects.filter(
                ciclo__contrato__associado=associado,
                status=Parcela.Status.DESCONTADO,
            )
            .select_related("ciclo")
            .order_by("-data_pagamento", "-referencia_mes")
        )

        historico = [
            {
                "referencia_mes": p.referencia_mes,
                "valor": p.valor,
                "data_pagamento": p.data_pagamento,
                "numero_parcela": p.numero,
                "ciclo_numero": p.ciclo.numero,
            }
            for p in parcelas
        ]

        return Response({"historico": historico})


# ---------------------------------------------------------------------------
# AppPendenciasView — GET /api/v1/app/pendencias/
# ---------------------------------------------------------------------------

class AppPendenciasView(APIView):
    """
    Pendências de documentos do associado logado via esteira.
    """
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]

    @extend_schema(responses={200: _AppPendenciasResponseSerializer})
    def get(self, request):
        associado = _get_associado_or_404(request.user)
        pendencias_data = _build_pendencias(associado)
        return Response({"pendencias": pendencias_data})


# ---------------------------------------------------------------------------
# AppDocumentosView — POST /api/v1/app/documentos/
# ---------------------------------------------------------------------------

class AppDocumentosView(APIView):
    """
    Upload de documento pelo próprio associado para resolver pendência.
    Multipart: tipo, arquivo, observacao (opcional).
    """
    permission_classes = [permissions.IsAuthenticated, IsAssociadoOrAdmin]
    parser_classes = [MultiPartParser]

    @extend_schema(
        request=DocumentoCreateSerializer,
        responses={201: _AppDocumentoUploadResponseSerializer},
    )
    def post(self, request):
        associado = _get_associado_or_404(request.user)
        serializer = DocumentoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save(associado=associado)
        return Response(
            {
                "id": doc.id,
                "tipo": doc.tipo,
                "status": doc.status,
                "observacao": doc.observacao,
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _build_resumo(associado: Associado, contratos_qs) -> dict:
    """Calcula resumo financeiro a partir dos contratos/ciclos/parcelas."""
    from datetime import date

    total_parcelas = 0
    total_pagas = 0
    total_em_atraso = 0
    valor_mensalidade = None
    proximo_vencimento = None

    for contrato in contratos_qs:
        if valor_mensalidade is None:
            valor_mensalidade = contrato.valor_mensalidade
        for ciclo in contrato.ciclos.all():
            for parcela in ciclo.parcelas.all():
                total_parcelas += 1
                if parcela.status == Parcela.Status.DESCONTADO:
                    total_pagas += 1
                if (
                    parcela.status == Parcela.Status.EM_ABERTO
                    and parcela.data_vencimento < date.today()
                ):
                    total_em_atraso += 1
                # Próximo vencimento = menor data futura em aberto
                if parcela.status == Parcela.Status.EM_ABERTO:
                    if proximo_vencimento is None or parcela.data_vencimento < proximo_vencimento:
                        proximo_vencimento = parcela.data_vencimento

    return {
        "parcelas_pagas": total_pagas,
        "parcelas_total": total_parcelas,
        "valor_mensalidade": valor_mensalidade,
        "proximo_vencimento": proximo_vencimento,
        "em_atraso": total_em_atraso,
    }


def _build_pendencias(associado: Associado) -> list:
    """Retorna pendências da esteira do associado."""
    esteira = associado.esteira
    if not esteira:
        return []
    return [
        {
            "id": p.id,
            "tipo": p.tipo,
            "descricao": p.descricao,
            "status": p.status,
            "created_at": p.created_at,
        }
        for p in esteira.pendencias.all()
    ]
