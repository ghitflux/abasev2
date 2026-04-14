from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone
from openpyxl import Workbook

from apps.associados.models import Associado
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import EsteiraItem, Pendencia
from apps.importacao.models import ArquivoRetorno
from apps.refinanciamento.models import Refinanciamento

from .models import RelatorioGerado


@dataclass(frozen=True)
class ReportColumn:
    key: str
    header: str
    width: float = 1.0


@dataclass(frozen=True)
class ReportDefinition:
    tipo: str
    title: str
    description: str
    columns: tuple[ReportColumn, ...]


class RelatorioService:
    LEGACY_TYPE_TO_ROUTE = {
        "associados": "/associados",
        "tesouraria": "/tesouraria",
        "refinanciamentos": "/tesouraria/refinanciamentos",
        "importacao": "/importacao",
    }

    @staticmethod
    def _definitions() -> dict[str, ReportDefinition]:
        return {
            "/analise": ReportDefinition(
                tipo="/analise",
                title="Relatorio do Dashboard de Analise",
                description="Fila consolidada da analise operacional conforme os filtros ativos.",
                columns=(
                    ReportColumn("nome", "Associado", 2.3),
                    ReportColumn("cpf_cnpj", "CPF/CNPJ", 1.3),
                    ReportColumn("matricula", "Matricula", 1.2),
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("etapa", "Etapa", 1.0),
                    ReportColumn("status", "Status", 1.1),
                    ReportColumn("agente", "Agente", 1.8),
                    ReportColumn("criado_em", "Atualizado em", 1.3),
                ),
            ),
            "/associados": ReportDefinition(
                tipo="/associados",
                title="Relatorio de Associados",
                description="Base cadastral com status do associado, orgao publico e agente responsavel.",
                columns=(
                    ReportColumn("nome_completo", "Associado", 2.5),
                    ReportColumn("cpf_cnpj", "CPF/CNPJ", 1.3),
                    ReportColumn("status", "Status", 1.0),
                    ReportColumn("orgao_publico", "Orgao", 1.8),
                    ReportColumn("agente", "Agente responsavel", 2.0),
                    ReportColumn("created_at", "Criado em", 1.3),
                ),
            ),
            "/tesouraria": ReportDefinition(
                tipo="/tesouraria",
                title="Relatorio de Tesouraria",
                description="Espelha as secoes operacionais de novos contratos da tesouraria com anexos, dados bancarios e status.",
                columns=(
                    ReportColumn("anexos", "Anexos", 2.0),
                    ReportColumn("dados_bancarios", "Dados bancarios", 2.0),
                    ReportColumn("chave_pix", "Chave PIX", 1.2),
                    ReportColumn("acao", "Acao", 1.6),
                    ReportColumn("nome", "Nome", 2.0),
                    ReportColumn("matricula_cpf", "Matricula / CPF", 1.8),
                    ReportColumn("agente", "Agente", 1.6),
                    ReportColumn("auxilio_comissao", "Aux. / Comissao", 1.6),
                    ReportColumn("data_solicitacao", "Data da solicitacao", 1.5),
                    ReportColumn("data_anexo_associado", "Anexo associado", 1.3),
                    ReportColumn("data_anexo_agente", "Anexo agente", 1.3),
                    ReportColumn("data_pagamento_associado", "Pagamento associado", 1.4),
                    ReportColumn("data_pagamento_agente", "Pagamento agente", 1.4),
                    ReportColumn("status", "Status", 1.1),
                ),
            ),
            "/tesouraria/refinanciamentos": ReportDefinition(
                tipo="/tesouraria/refinanciamentos",
                title="Relatorio de Refinanciamentos",
                description="Solicitacoes de refinanciamento com status, valor, repasse e responsavel pela acao.",
                columns=(
                    ReportColumn("associado_nome", "Associado", 2.3),
                    ReportColumn("cpf_cnpj", "CPF/CNPJ", 1.3),
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("data_solicitacao", "Data da solicitacao", 1.3),
                    ReportColumn("data_anexo_associado", "Anexo associado", 1.3),
                    ReportColumn("data_anexo_agente", "Anexo agente", 1.3),
                    ReportColumn("data_pagamento_associado", "Pagamento associado", 1.4),
                    ReportColumn("data_pagamento_agente", "Pagamento agente", 1.4),
                    ReportColumn("status", "Status", 1.2),
                    ReportColumn("valor_refinanciamento", "Valor", 1.1),
                    ReportColumn("repasse_agente", "Repasse agente", 1.1),
                    ReportColumn("pagamento_status", "Pagamento", 1.0),
                    ReportColumn("data_ativacao_ciclo", "Efetivacao", 1.2),
                ),
            ),
            "/agentes/meus-contratos": ReportDefinition(
                tipo="/agentes/meus-contratos",
                title="Relatorio de Meus Contratos",
                description="Contratos do agente conforme os filtros aplicados na tela.",
                columns=(
                    ReportColumn("codigo", "Contrato", 1.4),
                    ReportColumn("associado", "Associado", 2.4),
                    ReportColumn("status_visual_label", "Status", 1.2),
                    ReportColumn("etapa_fluxo", "Fluxo", 1.0),
                    ReportColumn("valor_disponivel", "Valor disponível", 1.1),
                    ReportColumn("status_renovacao", "Renovacao", 1.2),
                    ReportColumn("cancelamento_tipo", "Cancelamento", 1.1),
                    ReportColumn("cancelamento_motivo", "Motivo", 2.2),
                ),
            ),
            "/agentes/pagamentos": ReportDefinition(
                tipo="/agentes/pagamentos",
                title="Relatorio de Pagamentos",
                description="Pagamentos exibidos na rota de pagamentos do agente ou tesouraria.",
                columns=(
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("nome", "Associado", 2.3),
                    ReportColumn("agente_nome", "Agente", 1.8),
                    ReportColumn("data_solicitacao", "Solicitacao", 1.3),
                    ReportColumn("status_visual_label", "Status", 1.2),
                    ReportColumn("pagamento_inicial_status_label", "Pagamento", 1.2),
                    ReportColumn("pagamento_inicial_valor", "Valor pago", 1.1),
                    ReportColumn("cancelamento_tipo", "Cancelamento", 1.1),
                ),
            ),
            "/agentes/refinanciados": ReportDefinition(
                tipo="/agentes/refinanciados",
                title="Relatorio de Renovações do Agente",
                description="Solicitacoes e historico de renovacoes do agente.",
                columns=(
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("associado_nome", "Associado", 2.3),
                    ReportColumn("status", "Status", 1.2),
                    ReportColumn("data_solicitacao", "Solicitacao", 1.3),
                    ReportColumn("valor_refinanciamento", "Valor", 1.1),
                    ReportColumn("repasse_agente", "Repasse", 1.0),
                    ReportColumn("analista_note", "Nota analista", 1.8),
                    ReportColumn("coordenador_note", "Nota coordenacao", 1.8),
                ),
            ),
            "/analise/aptos": ReportDefinition(
                tipo="/analise/aptos",
                title="Relatorio de Fila Analítica",
                description="Renovacoes visiveis para a analise conforme os filtros ativos.",
                columns=(
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("associado_nome", "Associado", 2.3),
                    ReportColumn("status", "Status", 1.2),
                    ReportColumn("motivo_apto_renovacao", "Motivo", 2.4),
                    ReportColumn("analista_note", "Nota analista", 1.8),
                    ReportColumn("coordenador_note", "Nota coordenacao", 1.8),
                    ReportColumn("data_pagamento_associado", "Pagamento associado", 1.4),
                ),
            ),
            "/coordenacao/refinanciamento": ReportDefinition(
                tipo="/coordenacao/refinanciamento",
                title="Relatorio de Coordenação de Renovações",
                description="Fila da coordenação conforme os filtros ativos.",
                columns=(
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("associado_nome", "Associado", 2.3),
                    ReportColumn("status", "Status", 1.2),
                    ReportColumn("analista_note", "Nota analista", 1.8),
                    ReportColumn("coordenador_note", "Nota coordenacao", 1.8),
                    ReportColumn("data_solicitacao", "Solicitacao", 1.3),
                    ReportColumn("data_pagamento_associado", "Pagamento associado", 1.4),
                ),
            ),
            "/coordenacao/refinanciados": ReportDefinition(
                tipo="/coordenacao/refinanciados",
                title="Relatorio de Coordenação de Renovados",
                description="Historico consolidado das renovacoes efetivadas e em liquidacao visiveis para a coordenação.",
                columns=(
                    ReportColumn("contrato_codigo", "Contrato", 1.3),
                    ReportColumn("associado_nome", "Associado", 2.3),
                    ReportColumn("status", "Status", 1.2),
                    ReportColumn("data_solicitacao", "Solicitacao", 1.3),
                    ReportColumn("executado_em", "Executado em", 1.3),
                    ReportColumn("data_pagamento_associado", "Pagamento associado", 1.4),
                    ReportColumn("valor_refinanciamento", "Valor", 1.1),
                    ReportColumn("repasse_agente", "Repasse", 1.0),
                    ReportColumn("analista_note", "Nota analista", 1.8),
                    ReportColumn("coordenador_note", "Nota coordenacao", 1.8),
                ),
            ),
            "/importacao": ReportDefinition(
                tipo="/importacao",
                title="Relatorio de Importacao",
                description="Historico de arquivos retorno com competencia, processamento e inconsistencias.",
                columns=(
                    ReportColumn("arquivo_nome", "Arquivo", 2.6),
                    ReportColumn("competencia", "Competencia", 1.0),
                    ReportColumn("status", "Status", 1.1),
                    ReportColumn("total_registros", "Total", 0.8),
                    ReportColumn("processados", "Processados", 0.9),
                    ReportColumn("nao_encontrados", "Nao encontrados", 1.1),
                    ReportColumn("erros", "Erros", 0.7),
                    ReportColumn("created_at", "Importado em", 1.4),
                ),
            ),
        }

    @staticmethod
    def definition_payload(
        rota: str | None = None,
        tipo: str | None = None,
    ) -> dict[str, object] | list[dict[str, object]]:
        definitions = RelatorioService._definitions()
        if rota or tipo:
            route = RelatorioService._resolve_route_key(rota or tipo or "")
            try:
                definition = definitions[route]
            except KeyError as exc:
                raise ValueError(f"Rota de relatorio invalida: {route}") from exc
            return RelatorioService._serialize_definition(definition)
        return [
            RelatorioService._serialize_definition(definition)
            for definition in definitions.values()
        ]

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
    def exportar(rota: str, formato: str, filtros: dict[str, object] | None = None) -> RelatorioGerado:
        resolved_filters = filtros or {}
        rows = RelatorioService._rows_for_route(rota, resolved_filters)
        timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
        file_key = RelatorioService._resolve_route_key(rota).strip("/").replace("/", "_") or "relatorio"
        extension = "xlsx" if formato == "xlsx" else formato
        file_name = f"{file_key}_{timestamp}.{extension}"
        content = RelatorioService._render_content(rota, rows, formato, resolved_filters)

        relatorio = RelatorioGerado(nome=file_name, formato=formato)
        relatorio.arquivo.save(file_name, ContentFile(content), save=False)
        relatorio.save()
        return relatorio

    @staticmethod
    def download_filename(relatorio: RelatorioGerado) -> str:
        return Path(relatorio.arquivo.name or relatorio.nome).name

    @staticmethod
    def content_type(formato: str) -> str:
        return {
            "csv": "text/csv; charset=utf-8",
            "json": "application/json; charset=utf-8",
            "pdf": "application/pdf",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }.get(formato, "application/octet-stream")

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
    def _serialize_definition(definition: ReportDefinition) -> dict[str, object]:
        return {
            "tipo": definition.tipo,
            "title": definition.title,
            "description": definition.description,
            "columns": [
                {
                    "key": column.key,
                    "header": column.header,
                    "width": column.width,
                }
                for column in definition.columns
            ],
        }

    @staticmethod
    def _selected_columns(
        rota: str,
        filtros: dict[str, object] | None = None,
    ) -> tuple[ReportColumn, ...]:
        definition = RelatorioService._definition_for_route(rota)
        raw_columns = filtros.get("columns") if isinstance(filtros, dict) else None
        if not isinstance(raw_columns, list):
            return definition.columns
        available = {column.key: column for column in definition.columns}
        selected = [
            available[key]
            for key in raw_columns
            if isinstance(key, str) and key in available
        ]
        return tuple(selected) or definition.columns

    @staticmethod
    def _project_rows(
        rows: list[dict[str, object]],
        columns: tuple[ReportColumn, ...],
    ) -> list[dict[str, object]]:
        return [{column.key: row.get(column.key) for column in columns} for row in rows]

    @staticmethod
    def _render_content(
        rota: str,
        rows: list[dict[str, object]],
        formato: str,
        filtros: dict[str, object] | None = None,
    ) -> bytes:
        selected_columns = RelatorioService._selected_columns(rota, filtros or {})
        projected_rows = RelatorioService._project_rows(rows, selected_columns)
        if formato == "pdf":
            return RelatorioService._render_pdf(
                rota,
                projected_rows,
                filtros or {},
                selected_columns,
            )

        if formato == "xlsx":
            return RelatorioService._render_xlsx(
                rota,
                projected_rows,
                filtros or {},
                selected_columns,
            )

        if formato == "json":
            return json.dumps(
                projected_rows,
                ensure_ascii=True,
                indent=2,
                default=str,
            ).encode("utf-8")

        headers = [column.key for column in selected_columns]
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(projected_rows)
        return output.getvalue().encode("utf-8")

    @staticmethod
    def _resolve_route_key(rota: str) -> str:
        return RelatorioService.LEGACY_TYPE_TO_ROUTE.get(rota, rota)

    @staticmethod
    def _rows_for_route(
        rota: str,
        filtros: dict[str, object],
    ) -> list[dict[str, object]]:
        rows = filtros.get("rows")
        if isinstance(rows, list):
            return [RelatorioService._normalize_row(row) for row in rows if isinstance(row, dict)]

        legacy_tipo = next(
            (
                tipo
                for tipo, route in RelatorioService.LEGACY_TYPE_TO_ROUTE.items()
                if route == RelatorioService._resolve_route_key(rota)
            ),
            None,
        )
        if legacy_tipo is not None:
            return [RelatorioService._normalize_row(row) for row in RelatorioService._rows_for_tipo(legacy_tipo)]
        raise ValueError(f"Rota de relatório inválida: {rota}")

    @staticmethod
    def _normalize_row(row: dict[str, object]) -> dict[str, object]:
        return {str(key): RelatorioService._normalize_cell_value(value) for key, value in row.items()}

    @staticmethod
    def _normalize_cell_value(value: object) -> object:
        if isinstance(value, dict):
            return ", ".join(
                f"{key}: {RelatorioService._format_pdf_value(inner)}"
                for key, inner in value.items()
            )
        if isinstance(value, list):
            return " | ".join(RelatorioService._format_pdf_value(item) for item in value)
        return value

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

    @staticmethod
    def _definition_for_route(rota: str) -> ReportDefinition:
        route = RelatorioService._resolve_route_key(rota)
        try:
            return RelatorioService._definitions()[route]
        except KeyError as exc:
            raise ValueError(f"Rota de relatorio invalida: {route}") from exc

    @staticmethod
    def _summary_for_route(
        rota: str,
        rows: list[dict[str, object]],
        filtros: dict[str, object] | None = None,
    ) -> list[tuple[str, str]]:
        summary = [
            ("Rota", RelatorioService._resolve_route_key(rota)),
            ("Total registros", str(len(rows))),
        ]
        totais = filtros.get("totais") if isinstance(filtros, dict) else None
        if isinstance(totais, dict):
            for label, value in totais.items():
                if value in (None, "", [], {}):
                    continue
                pretty_label = str(label).replace("_", " ").strip().title()
                summary.append((pretty_label, RelatorioService._format_pdf_value(value)))
        return summary

    @staticmethod
    def _render_pdf(
        rota: str,
        rows: list[dict[str, object]],
        filtros: dict[str, object] | None = None,
        columns: tuple[ReportColumn, ...] | None = None,
    ) -> bytes:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        definition = RelatorioService._definition_for_route(rota)
        selected_columns = columns or definition.columns
        summary = RelatorioService._summary_for_route(rota, rows, filtros or {})
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=12 * mm,
            bottomMargin=12 * mm,
            title=definition.title,
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "RelatorioTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=20,
            textColor=colors.HexColor("#111827"),
            spaceAfter=4,
        )
        description_style = ParagraphStyle(
            "RelatorioDescription",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
        )
        meta_style = ParagraphStyle(
            "RelatorioMeta",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748B"),
        )
        cell_style = ParagraphStyle(
            "RelatorioCell",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
        )
        header_style = ParagraphStyle(
            "RelatorioHeader",
            parent=cell_style,
            fontName="Helvetica-Bold",
            textColor=colors.white,
        )

        generated_at = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
        story = [
            Paragraph(escape(definition.title), title_style),
            Paragraph(escape(definition.description), description_style),
            Spacer(1, 4 * mm),
            Paragraph(
                escape(f"Gerado em {generated_at} | Total de registros: {len(rows)}"),
                meta_style,
            ),
        ]

        if summary:
            summary_rows: list[list[Paragraph]] = []
            chunk: list[Paragraph] = []
            for label, value in summary:
                chunk.append(
                    Paragraph(
                        f"<b>{escape(str(label))}:</b> {escape(RelatorioService._format_pdf_value(value))}",
                        meta_style,
                    )
                )
                if len(chunk) == 2:
                    summary_rows.append(chunk)
                    chunk = []
            if chunk:
                chunk.append(Paragraph("", meta_style))
                summary_rows.append(chunk)

            summary_table = Table(summary_rows, colWidths=[document.width / 2, document.width / 2])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend([Spacer(1, 4 * mm), summary_table])

        story.append(Spacer(1, 5 * mm))

        table_rows: list[list[Paragraph]] = [
            [Paragraph(escape(column.header), header_style) for column in selected_columns]
        ]

        if rows:
            for row in rows:
                table_rows.append(
                    [
                        Paragraph(
                            escape(RelatorioService._format_pdf_value(row.get(column.key))),
                            cell_style,
                        )
                        for column in selected_columns
                    ]
                )
        else:
            table_rows.append(
                [
                    Paragraph("Nenhum registro encontrado para este relatorio.", cell_style),
                    *[Paragraph("", cell_style) for _ in selected_columns[1:]],
                ]
            )

        total_weight = sum(column.width for column in selected_columns) or 1
        col_widths = [
            document.width * (column.width / total_weight) for column in selected_columns
        ]
        table = Table(table_rows, repeatRows=1, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                    ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#0F172A")),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#1E293B")),
                    ("GRID", (0, 1), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(table)
        if summary:
            footer_summary_table = Table(
                summary_rows,
                colWidths=[document.width / 2, document.width / 2],
            )
            footer_summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.extend(
                [
                    Spacer(1, 5 * mm),
                    Paragraph("Totais do relatório", description_style),
                    Spacer(1, 2 * mm),
                    footer_summary_table,
                ]
            )
        document.build(story)
        return buffer.getvalue()

    @staticmethod
    def _render_xlsx(
        rota: str,
        rows: list[dict[str, object]],
        filtros: dict[str, object] | None = None,
        columns: tuple[ReportColumn, ...] | None = None,
    ) -> bytes:
        definition = RelatorioService._definition_for_route(rota)
        selected_columns = columns or definition.columns
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Relatorio"
        headers = [column.header for column in selected_columns]
        sheet.append(headers)
        for row in rows:
            sheet.append(
                [
                    RelatorioService._format_pdf_value(row.get(column.key))
                    for column in selected_columns
                ]
            )
        summary = RelatorioService._summary_for_route(rota, rows, filtros or {})
        if summary:
            sheet.append([])
            sheet.append(["Totais do relatório", ""])
            for label, value in summary:
                sheet.append([label, value])
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    @staticmethod
    def _format_pdf_value(value: object) -> str:
        if value is None or value == "":
            return "-"
        if isinstance(value, Decimal):
            return RelatorioService._format_number(value)
        if isinstance(value, bool):
            return "Sim" if value else "Nao"
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.strftime("%d/%m/%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, str):
            formatted = RelatorioService._format_iso_string(value)
            return formatted if formatted is not None else value
        return str(value)

    @staticmethod
    def _format_number(value: Decimal) -> str:
        normalized = f"{value:,.2f}"
        return normalized.replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def _format_iso_string(value: str) -> str | None:
        if "T" in value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
            if timezone.is_aware(parsed):
                parsed = timezone.localtime(parsed)
            return parsed.strftime("%d/%m/%Y %H:%M")
        if len(value) == 10:
            try:
                parsed_date = date.fromisoformat(value)
            except ValueError:
                return None
            return parsed_date.strftime("%d/%m/%Y")
        return None
