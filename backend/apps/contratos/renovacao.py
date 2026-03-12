from __future__ import annotations

from datetime import datetime

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem

from .models import Ciclo, Contrato, Parcela


def parse_competencia_query(value: str | None):
    if value:
        try:
            return datetime.strptime(value, "%Y-%m").date().replace(day=1)
        except ValueError as exc:
            raise ValidationError("Competência inválida. Use o formato YYYY-MM.") from exc

    ultima_importacao = (
        ArquivoRetorno.objects.filter(status=ArquivoRetorno.Status.CONCLUIDO)
        .order_by("-competencia", "-created_at")
        .first()
    )
    if ultima_importacao:
        return ultima_importacao.competencia
    return timezone.localdate().replace(day=1)


class RenovacaoCicloService:
    @staticmethod
    def _status_visual(parcela: Parcela, ciclo: Ciclo, proximo_ciclo: Ciclo | None) -> str:
        parcelas_pagas = ciclo.parcelas.filter(status=Parcela.Status.DESCONTADO).count()
        parcelas_total = ciclo.parcelas.count()

        if parcela.status == Parcela.Status.NAO_DESCONTADO:
            return "inadimplente"
        if proximo_ciclo and proximo_ciclo.status == Ciclo.Status.ABERTO:
            return "ciclo_iniciado"
        if ciclo.status == Ciclo.Status.CICLO_RENOVADO:
            return "ciclo_renovado"
        if parcelas_pagas >= parcelas_total and parcelas_total > 0:
            return "apto_a_renovar"
        if parcela.status in [Parcela.Status.EM_ABERTO, Parcela.Status.FUTURO]:
            return "em_aberto"
        return parcela.status

    @staticmethod
    def _build_row(parcela: Parcela, competencia, import_item: ArquivoRetornoItem | None) -> dict[str, object]:
        ciclo = parcela.ciclo
        contrato = ciclo.contrato
        associado = contrato.associado
        proximo_ciclo = contrato.ciclos.filter(numero=ciclo.numero + 1).first()
        parcelas_pagas = ciclo.parcelas.filter(status=Parcela.Status.DESCONTADO).count()
        parcelas_total = ciclo.parcelas.count()
        status_visual = RenovacaoCicloService._status_visual(parcela, ciclo, proximo_ciclo)

        return {
            "id": parcela.id,
            "competencia": competencia,
            "contrato_id": contrato.id,
            "contrato_codigo": contrato.codigo,
            "associado_id": associado.id,
            "nome_associado": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "orgao_publico": associado.orgao_publico,
            "ciclo_id": ciclo.id,
            "ciclo_numero": ciclo.numero,
            "status_ciclo": ciclo.status,
            "status_parcela": parcela.status,
            "status_visual": status_visual,
            "parcelas_pagas": parcelas_pagas,
            "parcelas_total": parcelas_total,
            "valor_mensalidade": contrato.valor_mensalidade,
            "valor_parcela": parcela.valor,
            "data_pagamento": parcela.data_pagamento,
            "orgao_pagto_nome": import_item.orgao_pagto_nome if import_item else "",
            "resultado_importacao": (
                import_item.resultado_processamento if import_item else "sem_importacao"
            ),
            "status_codigo_etipi": import_item.status_codigo if import_item else "",
            "gerou_encerramento": bool(import_item and import_item.gerou_encerramento),
            "gerou_novo_ciclo": bool(import_item and import_item.gerou_novo_ciclo),
        }

    @staticmethod
    def listar_detalhes(
        *,
        competencia,
        search: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        item_prefetch = Prefetch(
            "itens_retorno",
            queryset=ArquivoRetornoItem.objects.filter(
                arquivo_retorno__competencia=competencia
            ).select_related("arquivo_retorno"),
            to_attr="itens_retorno_filtrados",
        )
        parcelas = (
            Parcela.objects.select_related(
                "ciclo",
                "ciclo__contrato",
                "ciclo__contrato__associado",
            )
            .prefetch_related(
                "ciclo__parcelas",
                "ciclo__contrato__ciclos__parcelas",
                item_prefetch,
            )
            .filter(
                referencia_mes=competencia,
                ciclo__contrato__status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO],
            )
            .order_by("ciclo__contrato__associado__nome_completo")
        )

        rows: list[dict[str, object]] = []
        search_value = (search or "").strip().lower()
        for parcela in parcelas:
            itens = getattr(parcela, "itens_retorno_filtrados", [])
            import_item = itens[0] if itens else None
            row = RenovacaoCicloService._build_row(
                parcela,
                competencia.strftime("%m/%Y"),
                import_item,
            )
            if search_value and search_value not in row["nome_associado"].lower() and search_value not in row["cpf_cnpj"]:
                continue
            if status and row["status_visual"] != status:
                continue
            rows.append(row)
        return rows

    @staticmethod
    def visao_mensal(*, competencia, search: str | None = None, status: str | None = None) -> dict[str, object]:
        rows = RenovacaoCicloService.listar_detalhes(
            competencia=competencia,
            search=search,
            status=status,
        )
        resumo = {
            "competencia": competencia.strftime("%m/%Y"),
            "total_associados": len(rows),
            "ciclo_renovado": 0,
            "apto_a_renovar": 0,
            "em_aberto": 0,
            "ciclo_iniciado": 0,
            "inadimplente": 0,
        }
        for row in rows:
            if row["status_visual"] in resumo:
                resumo[row["status_visual"]] += 1
        return resumo

    @staticmethod
    def listar_meses() -> list[dict[str, str]]:
        competencias = (
            ArquivoRetorno.objects.filter(status=ArquivoRetorno.Status.CONCLUIDO)
            .order_by("-competencia")
            .values_list("competencia", flat=True)
            .distinct()
        )
        return [
            {
                "id": competencia.strftime("%Y-%m"),
                "label": competencia.strftime("%m/%Y"),
            }
            for competencia in competencias
        ]
