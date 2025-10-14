"""
Relatórios Router

Endpoints para geração de relatórios e exportação de dados
"""
import csv
import io
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from asgiref.sync import sync_to_async
from ninja import Router, Schema, Query
from ninja.errors import HttpError
from django.http import HttpResponse
from django.db.models import Count, Q, Sum, Avg
from django.core.paginator import Paginator

from core.models import Cadastro, Associado, EventLog
from core.models.cadastro import CadastroStatus

router = Router(tags=["relatorios"])


# Schemas
class FiltrosRelatorio(Schema):
    status: Optional[str] = None
    data_inicio: Optional[str] = None
    data_fim: Optional[str] = None
    perfil: Optional[str] = None
    limit: int = 100
    offset: int = 0


class CadastroRelatorio(Schema):
    id: int
    associado_nome: str
    associado_cpf: str
    status: str
    criado_em: str
    atualizado_em: str
    observacao: Optional[str] = None


class RelatorioResponse(Schema):
    total: int
    dados: List[CadastroRelatorio]
    filtros_aplicados: dict


class EstatisticasResponse(Schema):
    total_cadastros: int
    cadastros_por_status: dict
    cadastros_por_mes: dict
    media_tempo_aprovacao: Optional[float] = None


@router.get("/cadastros", response=RelatorioResponse)
async def relatorio_cadastros(request, filtros: FiltrosRelatorio = Query(...)):
    """
    Relatório de cadastros com filtros

    Filtros disponíveis:
    - status: Status do cadastro
    - data_inicio: Data inicial (ISO format)
    - data_fim: Data final (ISO format)
    - perfil: Filtrar por perfil do analista
    - limit: Limite de resultados
    - offset: Offset para paginação
    """
    # Construir query
    queryset = Cadastro.objects.select_related('associado').all()

    # Aplicar filtros
    if filtros.status:
        queryset = queryset.filter(status=filtros.status)

    if filtros.data_inicio:
        data_inicio = datetime.fromisoformat(filtros.data_inicio)
        queryset = queryset.filter(criado_em__gte=data_inicio)

    if filtros.data_fim:
        data_fim = datetime.fromisoformat(filtros.data_fim)
        queryset = queryset.filter(criado_em__lte=data_fim)

    # Contar total
    total = await sync_to_async(queryset.count, thread_sensitive=True)()

    # Aplicar paginação
    queryset = queryset[filtros.offset:filtros.offset + filtros.limit]

    # Buscar dados
    cadastros_list = await sync_to_async(list, thread_sensitive=True)(queryset)

    # Preparar resposta
    dados = []
    for cadastro in cadastros_list:
        dados.append({
            "id": cadastro.id,
            "associado_nome": cadastro.associado.nome,
            "associado_cpf": cadastro.associado.cpf,
            "status": cadastro.status,
            "criado_em": cadastro.criado_em.isoformat(),
            "atualizado_em": cadastro.atualizado_em.isoformat(),
            "observacao": cadastro.observacao,
        })

    return {
        "total": total,
        "dados": dados,
        "filtros_aplicados": filtros.dict(),
    }


@router.get("/estatisticas", response=EstatisticasResponse)
async def estatisticas(request):
    """
    Estatísticas agregadas do sistema

    Retorna:
    - Total de cadastros
    - Distribuição por status
    - Cadastros por mês
    - Média de tempo de aprovação
    """
    # Total de cadastros
    total_cadastros = await sync_to_async(
        Cadastro.objects.count,
        thread_sensitive=True
    )()

    # Cadastros por status
    status_counts = await sync_to_async(
        lambda: dict(
            Cadastro.objects.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')
        ),
        thread_sensitive=True
    )()

    # Cadastros por mês (últimos 12 meses)
    from django.db.models.functions import TruncMonth
    cadastros_por_mes_qs = Cadastro.objects.annotate(
        mes=TruncMonth('criado_em')
    ).values('mes').annotate(
        count=Count('id')
    ).order_by('mes')

    cadastros_por_mes_list = await sync_to_async(
        list,
        thread_sensitive=True
    )(cadastros_por_mes_qs)

    cadastros_por_mes = {
        item['mes'].strftime('%Y-%m'): item['count']
        for item in cadastros_por_mes_list
    }

    # TODO: Calcular média de tempo de aprovação
    # (requer análise de EventLog)

    return {
        "total_cadastros": total_cadastros,
        "cadastros_por_status": status_counts,
        "cadastros_por_mes": cadastros_por_mes,
        "media_tempo_aprovacao": None,
    }


@router.get("/exportar/csv")
async def exportar_csv(request, filtros: FiltrosRelatorio = Query(...)):
    """
    Exporta relatório de cadastros em CSV

    Usa os mesmos filtros do endpoint /relatorios/cadastros
    """
    # Construir query (mesma lógica do relatório)
    queryset = Cadastro.objects.select_related('associado').all()

    if filtros.status:
        queryset = queryset.filter(status=filtros.status)

    if filtros.data_inicio:
        data_inicio = datetime.fromisoformat(filtros.data_inicio)
        queryset = queryset.filter(criado_em__gte=data_inicio)

    if filtros.data_fim:
        data_fim = datetime.fromisoformat(filtros.data_fim)
        queryset = queryset.filter(criado_em__lte=data_fim)

    # Limitar a 10000 registros para exportação
    queryset = queryset[:10000]

    # Buscar dados
    cadastros_list = await sync_to_async(list, thread_sensitive=True)(queryset)

    # Criar CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'ID',
        'Associado Nome',
        'CPF',
        'Status',
        'Data Criação',
        'Data Atualização',
        'Observação',
    ])

    # Dados
    for cadastro in cadastros_list:
        writer.writerow([
            cadastro.id,
            cadastro.associado.nome,
            cadastro.associado.cpf,
            cadastro.status,
            cadastro.criado_em.strftime('%Y-%m-%d %H:%M:%S'),
            cadastro.atualizado_em.strftime('%Y-%m-%d %H:%M:%S'),
            cadastro.observacao or '',
        ])

    # Preparar response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="relatorio_cadastros_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    return response


@router.get("/exportar/eventos/csv")
async def exportar_eventos_csv(
    request,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    event_type: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    limit: int = 10000
):
    """
    Exporta eventos (EventLog) em CSV

    Filtros:
    - entity_type: Tipo de entidade (Cadastro, User, etc)
    - entity_id: ID da entidade
    - event_type: Tipo de evento
    - data_inicio/data_fim: Período
    """
    # Construir query
    queryset = EventLog.objects.all()

    if entity_type:
        queryset = queryset.filter(entity_type=entity_type)

    if entity_id:
        queryset = queryset.filter(entity_id=entity_id)

    if event_type:
        queryset = queryset.filter(event_type=event_type)

    if data_inicio:
        data_inicio_dt = datetime.fromisoformat(data_inicio)
        queryset = queryset.filter(created_at__gte=data_inicio_dt)

    if data_fim:
        data_fim_dt = datetime.fromisoformat(data_fim)
        queryset = queryset.filter(created_at__lte=data_fim_dt)

    # Limitar
    queryset = queryset.order_by('-created_at')[:limit]

    # Buscar dados
    eventos_list = await sync_to_async(list, thread_sensitive=True)(queryset)

    # Criar CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'ID',
        'Tipo Entidade',
        'ID Entidade',
        'Tipo Evento',
        'Ator',
        'Data/Hora',
        'Payload',
    ])

    # Dados
    for evento in eventos_list:
        writer.writerow([
            evento.id,
            evento.entity_type,
            evento.entity_id,
            evento.event_type,
            evento.actor_id or '',
            evento.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            str(evento.payload),
        ])

    # Preparar response
    output.seek(0)
    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="eventos_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    return response


@router.get("/dashboard")
async def dashboard_data(request):
    """
    Dados agregados para dashboard

    Retorna métricas principais para visualização
    """
    # Cadastros por status
    total_cadastros = await sync_to_async(
        Cadastro.objects.count,
        thread_sensitive=True
    )()

    # Contar por status
    status_counts = {}
    for status in CadastroStatus.choices:
        count = await sync_to_async(
            lambda s: Cadastro.objects.filter(status=s).count(),
            thread_sensitive=True
        )(status[0])
        status_counts[status[0]] = count

    # Cadastros criados hoje
    hoje = datetime.now().date()
    cadastros_hoje = await sync_to_async(
        lambda: Cadastro.objects.filter(criado_em__date=hoje).count(),
        thread_sensitive=True
    )()

    # Cadastros em análise
    em_analise = await sync_to_async(
        lambda: Cadastro.objects.filter(status=CadastroStatus.ENVIADO_ANALISE).count(),
        thread_sensitive=True
    )()

    # Cadastros aprovados (últimos 7 dias)
    from datetime import timedelta
    sete_dias_atras = datetime.now() - timedelta(days=7)
    aprovados_semana = await sync_to_async(
        lambda: Cadastro.objects.filter(
            status=CadastroStatus.APROVADO_ANALISE,
            atualizado_em__gte=sete_dias_atras
        ).count(),
        thread_sensitive=True
    )()

    # Total de associados
    total_associados = await sync_to_async(
        Associado.objects.count,
        thread_sensitive=True
    )()

    return {
        "total_cadastros": total_cadastros,
        "total_associados": total_associados,
        "cadastros_hoje": cadastros_hoje,
        "em_analise": em_analise,
        "aprovados_ultima_semana": aprovados_semana,
        "por_status": status_counts,
        "timestamp": datetime.now().isoformat(),
    }
