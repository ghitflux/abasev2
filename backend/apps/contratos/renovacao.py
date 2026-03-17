from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.importacao.financeiro import build_financeiro_resumo
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem

from .cycle_timeline import (
    get_contract_activation_payload,
    get_cycle_activation_info,
    get_cycle_activation_payload,
)
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
    def _parcelas_minimas_para_renovar(parcelas_total: int) -> int:
        if parcelas_total <= 1:
            return parcelas_total
        return max(parcelas_total - 1, 1)

    @staticmethod
    def _resolve_parcelas(ciclo: Ciclo) -> list[Parcela]:
        cached = getattr(ciclo, "parcelas_prefetched", None)
        if cached is not None:
            return list(cached)
        return list(ciclo.parcelas.all())

    @staticmethod
    def _resolve_ciclos(contrato: Contrato) -> list[Ciclo]:
        cached = getattr(contrato, "ciclos_prefetched", None)
        if cached is not None:
            return list(cached)
        return list(contrato.ciclos.all())

    @staticmethod
    def _resolve_associado_contratos(contrato: Contrato) -> list[Contrato]:
        associado = contrato.associado
        cached = getattr(associado, "contratos_contexto_prefetched", None)
        if cached is not None:
            return list(cached)
        return list(associado.contratos.exclude(status=Contrato.Status.CANCELADO))

    @staticmethod
    def _resolve_agente_responsavel(contrato: Contrato) -> str:
        associado = contrato.associado
        agente = associado.agente_responsavel or contrato.agente
        return agente.full_name if agente else "Sem agente vinculado"

    @staticmethod
    def _resolve_matricula(parcela: Parcela, import_item: ArquivoRetornoItem | None) -> str:
        associado = parcela.ciclo.contrato.associado
        return (
            associado.matricula_orgao
            or associado.matricula
            or (import_item.matricula_servidor if import_item else "")
            or parcela.ciclo.contrato.codigo
        )

    @staticmethod
    def _status_visual(
        parcela: Parcela,
        ciclo: Ciclo,
        proximo_ciclo: Ciclo | None,
        parcelas_ciclo: list[Parcela],
    ) -> str:
        parcelas_pagas = sum(
            1 for ciclo_parcela in parcelas_ciclo if ciclo_parcela.status == Parcela.Status.DESCONTADO
        )
        parcelas_total = len(parcelas_ciclo)
        parcelas_minimas_para_renovar = RenovacaoCicloService._parcelas_minimas_para_renovar(
            parcelas_total
        )
        ativacao_atual = get_cycle_activation_info(ciclo, allow_fallback=False)
        ativacao_proxima = (
            get_cycle_activation_info(proximo_ciclo, allow_fallback=False)
            if proximo_ciclo
            else None
        )

        # Ciclo ainda não foi ativado — em previsão
        if ciclo.status == Ciclo.Status.FUTURO and ativacao_atual.activated_at is None:
            return "em_previsao"

        if parcela.status == Parcela.Status.NAO_DESCONTADO:
            return "inadimplente"
        if ciclo.status == Ciclo.Status.CICLO_RENOVADO:
            return "ciclo_renovado"
        if proximo_ciclo and (
            proximo_ciclo.status == Ciclo.Status.ABERTO
            or (ativacao_proxima and ativacao_proxima.activated_at is not None)
        ):
            return "ciclo_iniciado"
        if parcelas_total > 0 and parcelas_pagas >= parcelas_minimas_para_renovar:
            return "apto_a_renovar"
        if parcela.status in [Parcela.Status.EM_ABERTO]:
            return "em_aberto"
        return parcela.status

    @staticmethod
    def _build_status_explicacao(
        *,
        contrato: Contrato,
        status_visual: str,
        parcelas_pagas: int,
        parcelas_total: int,
        contratos_associado: list[Contrato],
    ) -> str:
        if status_visual != "apto_a_renovar":
            return ""

        explicacao = (
            f"Apto a renovar porque o contrato {contrato.codigo} atingiu "
            f"{parcelas_pagas}/{parcelas_total} parcelas baixadas."
        )
        outros_contratos = [
            item
            for item in contratos_associado
            if item.id != contrato.id and item.status != Contrato.Status.CANCELADO
        ]
        if outros_contratos:
            explicacao += (
                " O associado possui outros contratos; este indicador considera apenas "
                f"o contrato de referência {contrato.codigo}."
            )
        return explicacao

    @staticmethod
    def _build_row(parcela: Parcela, competencia, import_item: ArquivoRetornoItem | None) -> dict[str, object]:
        ciclo = parcela.ciclo
        contrato = ciclo.contrato
        associado = contrato.associado
        parcelas_ciclo = RenovacaoCicloService._resolve_parcelas(ciclo)
        contrato_ciclos = RenovacaoCicloService._resolve_ciclos(contrato)
        contratos_associado = RenovacaoCicloService._resolve_associado_contratos(contrato)
        proximo_ciclo = next(
            (candidate for candidate in contrato_ciclos if candidate.numero == ciclo.numero + 1),
            None,
        )
        parcelas_pagas = sum(
            1 for ciclo_parcela in parcelas_ciclo if ciclo_parcela.status == Parcela.Status.DESCONTADO
        )
        parcelas_total = len(parcelas_ciclo)
        status_visual = RenovacaoCicloService._status_visual(
            parcela,
            ciclo,
            proximo_ciclo,
            parcelas_ciclo,
        )
        status_explicacao = RenovacaoCicloService._build_status_explicacao(
            contrato=contrato,
            status_visual=status_visual,
            parcelas_pagas=parcelas_pagas,
            parcelas_total=parcelas_total,
            contratos_associado=contratos_associado,
        )
        ciclo_activation = get_cycle_activation_payload(ciclo)
        contrato_activation = get_contract_activation_payload(contrato)

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
            "status_explicacao": status_explicacao,
            "data_primeiro_ciclo_ativado": contrato_activation["data_primeiro_ciclo_ativado"],
            "data_ativacao_ciclo": ciclo_activation["data_ativacao_ciclo"],
            "origem_data_ativacao": ciclo_activation["origem_data_ativacao"],
            "data_solicitacao_renovacao": ciclo_activation["data_solicitacao_renovacao"],
            "ativacao_inferida": ciclo_activation["ativacao_inferida"],
            "matricula": RenovacaoCicloService._resolve_matricula(parcela, import_item),
            "agente_responsavel": RenovacaoCicloService._resolve_agente_responsavel(contrato),
            "parcelas_pagas": parcelas_pagas,
            "parcelas_total": parcelas_total,
            "contrato_referencia_renovacao_id": contrato.id,
            "contrato_referencia_renovacao_codigo": contrato.codigo,
            "possui_multiplos_contratos": len(
                [
                    item
                    for item in contratos_associado
                    if item.status != Contrato.Status.CANCELADO
                ]
            )
            > 1,
            "valor_mensalidade": contrato.valor_mensalidade,
            "valor_parcela": parcela.valor,
            "data_pagamento": parcela.data_pagamento,
            "orgao_pagto_nome": import_item.orgao_pagto_nome if import_item else "",
            "resultado_importacao": (
                import_item.resultado_processamento if import_item else "sem_importacao"
            ),
            "status_codigo_etipi": import_item.status_codigo if import_item else "",
            "status_descricao_etipi": import_item.status_descricao if import_item else "",
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
                arquivo_retorno__competencia=competencia,
                arquivo_retorno__status=ArquivoRetorno.Status.CONCLUIDO,
            )
            .select_related("arquivo_retorno")
            .order_by(
                "-arquivo_retorno__processado_em",
                "-arquivo_retorno__created_at",
                "-created_at",
                "-id",
            ),
            to_attr="itens_retorno_filtrados",
        )
        parcelas = (
            Parcela.objects.select_related(
                "ciclo",
                "ciclo__contrato",
                "ciclo__contrato__agente",
                "ciclo__contrato__associado",
                "ciclo__contrato__associado__agente_responsavel",
            )
            .prefetch_related(
                Prefetch(
                    "ciclo__parcelas",
                    queryset=Parcela.objects.order_by("numero"),
                    to_attr="parcelas_prefetched",
                ),
                Prefetch(
                    "ciclo__contrato__ciclos",
                    queryset=Ciclo.objects.order_by("numero").prefetch_related(
                        Prefetch(
                            "parcelas",
                            queryset=Parcela.objects.order_by("numero"),
                            to_attr="parcelas_prefetched",
                        )
                    ),
                    to_attr="ciclos_prefetched",
                ),
                Prefetch(
                    "ciclo__contrato__associado__contratos",
                    queryset=Contrato.objects.exclude(status=Contrato.Status.CANCELADO).only(
                        "id",
                        "codigo",
                        "status",
                        "associado_id",
                    ),
                    to_attr="contratos_contexto_prefetched",
                ),
                item_prefetch,
            )
            .filter(
                referencia_mes=competencia,
                ciclo__contrato__status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO],
            )
            .order_by("ciclo__contrato__associado__nome_completo")
        )

        search_value = (search or "").strip()
        if search_value:
            parcelas = parcelas.filter(
                Q(ciclo__contrato__associado__nome_completo__icontains=search_value)
                | Q(ciclo__contrato__associado__cpf_cnpj__icontains=search_value)
                | Q(ciclo__contrato__associado__matricula__icontains=search_value)
                | Q(ciclo__contrato__associado__matricula_orgao__icontains=search_value)
                | Q(ciclo__contrato__codigo__icontains=search_value)
            )

        rows: list[dict[str, object]] = []
        for parcela in parcelas:
            itens = getattr(parcela, "itens_retorno_filtrados", [])
            import_item = itens[0] if itens else None
            row = RenovacaoCicloService._build_row(
                parcela,
                competencia.strftime("%m/%Y"),
                import_item,
            )
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
            "em_previsao": 0,
            "esperado_total": Decimal("0.00"),
            "arrecadado_total": Decimal("0.00"),
            "percentual_arrecadado": 0.0,
        }
        for row in rows:
            if row["status_visual"] == "ciclo_renovado" or row["gerou_encerramento"]:
                resumo["ciclo_renovado"] += 1
            if row["status_visual"] == "apto_a_renovar":
                resumo["apto_a_renovar"] += 1
            if row["status_visual"] == "em_aberto":
                resumo["em_aberto"] += 1
            if row["status_visual"] == "ciclo_iniciado" or row["gerou_novo_ciclo"]:
                resumo["ciclo_iniciado"] += 1
            if row["status_visual"] == "inadimplente":
                resumo["inadimplente"] += 1
            if row["status_visual"] == "em_previsao":
                resumo["em_previsao"] += 1

            # Only count active cycles in financial totals (exclude em_previsao)
            if row["status_visual"] != "em_previsao":
                valor_parcela = Decimal(str(row.get("valor_parcela") or 0))
                resumo["esperado_total"] += valor_parcela
                if row["resultado_importacao"] == ArquivoRetornoItem.ResultadoProcessamento.BAIXA_EFETUADA or row[
                    "status_parcela"
                ] == Parcela.Status.DESCONTADO:
                    resumo["arrecadado_total"] += valor_parcela
        if resumo["esperado_total"] > 0:
            resumo["percentual_arrecadado"] = float(
                (resumo["arrecadado_total"] / resumo["esperado_total"]) * Decimal("100")
            )

        if not (search or "").strip() and not (status or "").strip():
            financeiro = build_financeiro_resumo(competencia=competencia)
            if financeiro.get("total"):
                resumo["total_associados"] = int(financeiro["total"])
                resumo["esperado_total"] = Decimal(str(financeiro["esperado"]))
                resumo["arrecadado_total"] = Decimal(str(financeiro["recebido"]))
                resumo["percentual_arrecadado"] = float(financeiro.get("percentual") or 0.0)
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
