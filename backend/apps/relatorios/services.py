from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone

from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia
from apps.importacao.models import ArquivoRetorno
from apps.refinanciamento.models import Refinanciamento

from .models import RelatorioGerado


class RelatorioService:
    @staticmethod
    def resumo() -> dict[str, object]:
        hoje = timezone.localdate()
        ultima_importacao = ArquivoRetorno.objects.order_by("-created_at").first()
        valor_baixado_mes = (
            Parcela.objects.filter(
                status=Parcela.Status.DESCONTADO,
                data_pagamento__year=hoje.year,
                data_pagamento__month=hoje.month,
            ).aggregate(total=Sum("valor"))["total"]
            or 0
        )

        return {
            "associados_ativos": Associado.objects.filter(status=Associado.Status.ATIVO).count(),
            "associados_em_analise": Associado.objects.filter(status=Associado.Status.EM_ANALISE).count(),
            "associados_inadimplentes": Associado.objects.filter(status=Associado.Status.INADIMPLENTE).count(),
            "contratos_ativos": Contrato.objects.filter(status=Contrato.Status.ATIVO).count(),
            "contratos_em_analise": Contrato.objects.filter(status=Contrato.Status.EM_ANALISE).count(),
            "pendencias_abertas": Pendencia.objects.filter(status=Pendencia.Status.ABERTA).count(),
            "esteira_aguardando": EsteiraItem.objects.filter(status=EsteiraItem.Situacao.AGUARDANDO).count(),
            "refinanciamentos_pendentes": Refinanciamento.objects.filter(
                status__in=[
                    Refinanciamento.Status.PENDENTE_APTO,
                    Refinanciamento.Status.BLOQUEADO,
                    Refinanciamento.Status.SOLICITADO,
                    Refinanciamento.Status.EM_ANALISE,
                    Refinanciamento.Status.APROVADO,
                ]
            ).count(),
            "refinanciamentos_efetivados": Refinanciamento.objects.filter(
                status__in=[
                    Refinanciamento.Status.CONCLUIDO,
                    Refinanciamento.Status.EFETIVADO,
                ]
            ).count(),
            "importacoes_concluidas": ArquivoRetorno.objects.filter(
                status=ArquivoRetorno.Status.CONCLUIDO
            ).count(),
            "baixas_mes": Parcela.objects.filter(
                status=Parcela.Status.DESCONTADO,
                data_pagamento__year=hoje.year,
                data_pagamento__month=hoje.month,
            ).count(),
            "valor_baixado_mes": valor_baixado_mes,
            "ultima_importacao": RelatorioService._serialize_importacao(ultima_importacao),
        }

    @staticmethod
    def exportar(tipo: str, formato: str) -> RelatorioGerado:
        rows = RelatorioService._rows_for_tipo(tipo)
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        file_name = f"{tipo}_{timestamp}.{formato}"
        content = RelatorioService._render_content(rows, formato)

        relatorio = RelatorioGerado(nome=file_name, formato=formato)
        relatorio.arquivo.save(file_name, ContentFile(content.encode("utf-8")), save=False)
        relatorio.save()
        return relatorio

    @staticmethod
    def download_filename(relatorio: RelatorioGerado) -> str:
        return Path(relatorio.arquivo.name or relatorio.nome).name

    @staticmethod
    def _serialize_importacao(arquivo: ArquivoRetorno | None) -> dict[str, object] | None:
        if not arquivo:
            return None
        return {
            "id": arquivo.id,
            "arquivo_nome": arquivo.arquivo_nome,
            "competencia": arquivo.competencia.strftime("%m/%Y"),
            "status": arquivo.status,
            "processado_em": arquivo.processado_em,
        }

    @staticmethod
    def _render_content(rows: list[dict[str, object]], formato: str) -> str:
        if formato == "json":
            return json.dumps(rows, ensure_ascii=True, indent=2, default=str)

        headers = list(rows[0].keys()) if rows else []
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    @staticmethod
    def _rows_for_tipo(tipo: str) -> list[dict[str, object]]:
        if tipo == "associados":
            return RelatorioService._associados_rows()
        if tipo == "tesouraria":
            return RelatorioService._tesouraria_rows()
        if tipo == "refinanciamentos":
            return RelatorioService._refinanciamentos_rows()
        if tipo == "importacao":
            return RelatorioService._importacao_rows()
        raise ValueError(f"Tipo de relatorio invalido: {tipo}")

    @staticmethod
    def _associados_rows() -> list[dict[str, object]]:
        queryset = Associado.objects.select_related("agente_responsavel").order_by("nome_completo")
        return [
            {
                "id": associado.id,
                "nome_completo": associado.nome_completo,
                "cpf_cnpj": associado.cpf_cnpj,
                "status": associado.status,
                "orgao_publico": associado.orgao_publico,
                "agente": associado.agente_responsavel.full_name if associado.agente_responsavel else "",
                "created_at": associado.created_at.isoformat(),
            }
            for associado in queryset
        ]

    @staticmethod
    def _tesouraria_rows() -> list[dict[str, object]]:
        queryset = Contrato.objects.select_related("associado", "agente").order_by("-created_at")
        return [
            {
                "id": contrato.id,
                "codigo": contrato.codigo,
                "associado": contrato.associado.nome_completo,
                "cpf_cnpj": contrato.associado.cpf_cnpj,
                "status": contrato.status,
                "valor_mensalidade": contrato.valor_mensalidade,
                "comissao_agente": contrato.comissao_agente,
                "agente": contrato.agente.full_name if contrato.agente else "",
                "auxilio_liberado_em": contrato.auxilio_liberado_em,
                "created_at": contrato.created_at.isoformat(),
            }
            for contrato in queryset
        ]

    @staticmethod
    def _refinanciamentos_rows() -> list[dict[str, object]]:
        queryset = Refinanciamento.objects.select_related(
            "associado",
            "contrato_origem",
            "solicitado_por",
        ).order_by("-created_at")
        return [
            {
                "id": refinanciamento.id,
                "associado": refinanciamento.associado.nome_completo,
                "cpf_cnpj": refinanciamento.associado.cpf_cnpj,
                "contrato": refinanciamento.contrato_origem.codigo if refinanciamento.contrato_origem else "",
                "status": refinanciamento.status,
                "valor_refinanciamento": refinanciamento.valor_refinanciamento,
                "repasse_agente": refinanciamento.repasse_agente,
                "solicitado_por": refinanciamento.solicitado_por.full_name,
                "executado_em": refinanciamento.executado_em.isoformat() if refinanciamento.executado_em else "",
                "created_at": refinanciamento.created_at.isoformat(),
            }
            for refinanciamento in queryset
        ]

    @staticmethod
    def _importacao_rows() -> list[dict[str, object]]:
        queryset = ArquivoRetorno.objects.order_by("-created_at")
        return [
            {
                "id": arquivo.id,
                "arquivo_nome": arquivo.arquivo_nome,
                "competencia": arquivo.competencia.strftime("%m/%Y"),
                "status": arquivo.status,
                "total_registros": arquivo.total_registros,
                "processados": arquivo.processados,
                "nao_encontrados": arquivo.nao_encontrados,
                "erros": arquivo.erros,
                "created_at": arquivo.created_at.isoformat(),
            }
            for arquivo in queryset
        ]
