from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.importacao.financeiro import build_financeiro_resumo
from apps.importacao.models import ArquivoRetorno, ArquivoRetornoItem
from apps.refinanciamento.models import Refinanciamento

from .canonicalization import (
    get_operational_contracts_for_associado,
    operational_contracts_queryset,
)
from .cycle_projection import (
    ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES,
    APT_LIKE_OPERATIONAL_REFINANCIAMENTO_STATUSES,
    build_contract_cycle_projection,
    is_contract_eligible_for_renewal_competencia,
    resolve_current_renewal_competencia,
)
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
    return resolve_current_renewal_competencia() or timezone.localdate().replace(day=1)


class RenovacaoCicloService:
    SUPPLEMENTAL_RENEWAL_STATUSES = {"apto_a_renovar"}
    APT_QUEUE_OPERATIONAL_STATUSES = APT_LIKE_OPERATIONAL_REFINANCIAMENTO_STATUSES
    STATUS_PRIORITY = {
        "aprovado_para_renovacao": 70,
        "apto_a_renovar": 60,
        "ciclo_iniciado": 50,
        "inadimplente": 40,
        "ciclo_renovado": 30,
        "em_aberto": 20,
        "em_previsao": 10,
    }

    @staticmethod
    def _parcelas_minimas_para_renovar(parcelas_total: int) -> int:
        if parcelas_total <= 1:
            return parcelas_total
        return max(parcelas_total - 1, 1)

    @staticmethod
    def _is_paid_status(value: object) -> bool:
        return str(value or "") in {
            Parcela.Status.DESCONTADO,
            Parcela.Status.LIQUIDADA,
            "quitada",
        }

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
        return get_operational_contracts_for_associado(contrato.associado)

    @staticmethod
    def _is_pending_reactivation_contract(contrato: Contrato) -> bool:
        return bool(
            contrato.origem_operacional == Contrato.OrigemOperacional.REATIVACAO
            and contrato.auxilio_liberado_em is None
            and contrato.status
            not in {
                Contrato.Status.ATIVO,
                Contrato.Status.CANCELADO,
                Contrato.Status.ENCERRADO,
            }
        )

    @staticmethod
    def _associado_has_pending_reactivation_flow(contrato: Contrato) -> bool:
        cached = getattr(contrato.associado, "contratos_contexto_prefetched", None)
        if cached is not None:
            return any(
                RenovacaoCicloService._is_pending_reactivation_contract(item)
                for item in cached
            )
        if RenovacaoCicloService._is_pending_reactivation_contract(contrato):
            return True
        return (
            contrato.associado.contratos.filter(
                origem_operacional=Contrato.OrigemOperacional.REATIVACAO,
                auxilio_liberado_em__isnull=True,
            )
            .exclude(
                status__in=[
                    Contrato.Status.ATIVO,
                    Contrato.Status.CANCELADO,
                    Contrato.Status.ENCERRADO,
                ]
            )
            .exists()
        )

    @staticmethod
    def _active_operational_apto_refinanciamento(
        contrato: Contrato,
    ) -> Refinanciamento | None:
        return (
            contrato.refinanciamentos.filter(
                deleted_at__isnull=True,
                legacy_refinanciamento_id__isnull=True,
                origem=Refinanciamento.Origem.OPERACIONAL,
                ciclo_destino__isnull=True,
                executado_em__isnull=True,
                data_ativacao_ciclo__isnull=True,
                status__in=RenovacaoCicloService.APT_QUEUE_OPERATIONAL_STATUSES,
            )
            .order_by("-competencia_solicitada", "-updated_at", "-created_at", "-id")
            .first()
        )

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
        competencia: date,
        parcela: Parcela,
        ciclo: Ciclo,
        proximo_ciclo: Ciclo | None,
        parcelas_ciclo: list[Parcela],
    ) -> str:
        parcelas_pagas = sum(
            1
            for ciclo_parcela in parcelas_ciclo
            if RenovacaoCicloService._is_paid_status(ciclo_parcela.status)
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
        projection = build_contract_cycle_projection(ciclo.contrato)

        # Ciclo ainda não foi ativado — em previsão
        if ciclo.status == Ciclo.Status.FUTURO and ativacao_atual.activated_at is None:
            return "em_previsao"

        if projection["possui_meses_nao_descontados"]:
            return "inadimplente"
        if proximo_ciclo and (
            proximo_ciclo.status == Ciclo.Status.ABERTO
            or (ativacao_proxima and ativacao_proxima.activated_at is not None)
        ):
            return "ciclo_iniciado"
        if (
            parcelas_total > 0
            and parcelas_pagas >= parcelas_minimas_para_renovar
            and not RenovacaoCicloService._associado_has_pending_reactivation_flow(
                ciclo.contrato
            )
            and is_contract_eligible_for_renewal_competencia(
                ciclo.contrato,
                competencia=competencia,
                parcelas=[
                    {
                        "referencia_mes": ciclo_parcela.referencia_mes,
                        "status": ciclo_parcela.status,
                        "data_pagamento": ciclo_parcela.data_pagamento,
                    }
                    for ciclo_parcela in parcelas_ciclo
                ],
            )
        ):
            return "apto_a_renovar"
        if ciclo.status in {Ciclo.Status.CICLO_RENOVADO, Ciclo.Status.FECHADO}:
            return "ciclo_renovado"
        if parcela.status == Parcela.Status.EM_PREVISAO:
            return "em_aberto"
        if parcela.status in [Parcela.Status.EM_ABERTO]:
            return "em_aberto"
        return parcela.status

    @staticmethod
    def _build_projection_only_row(
        *,
        contrato: Contrato,
        competencia,
        projection: dict[str, object],
    ) -> dict[str, object] | None:
        if RenovacaoCicloService._associado_has_pending_reactivation_flow(contrato):
            return None

        operational_apto = RenovacaoCicloService._active_operational_apto_refinanciamento(
            contrato
        )
        has_pending_operational_apto = operational_apto is not None
        associado_status_apto = str(contrato.associado.status or "") == "apto_a_renovar"
        status_renovacao = str(projection.get("status_renovacao") or "")
        if has_pending_operational_apto or associado_status_apto:
            status_renovacao = Refinanciamento.Status.APTO_A_RENOVAR
        elif status_renovacao not in RenovacaoCicloService.SUPPLEMENTAL_RENEWAL_STATUSES:
            return None

        projected_cycles = list(
            sorted(projection.get("cycles") or [], key=lambda item: item["numero"])
        )
        if not projected_cycles:
            return None

        latest_projected_cycle = projected_cycles[-1]
        ciclos = RenovacaoCicloService._resolve_ciclos(contrato)
        ciclo = next(
            (
                candidate
                for candidate in ciclos
                if candidate.numero == latest_projected_cycle["numero"]
            ),
            None,
        )
        if ciclo is None:
            return None

        parcelas_projetadas = list(latest_projected_cycle.get("parcelas") or [])
        representative = next(
            (
                parcela
                for parcela in reversed(parcelas_projetadas)
                if parcela["referencia_mes"] <= competencia
            ),
            parcelas_projetadas[-1] if parcelas_projetadas else None,
        )
        contratos_associado = RenovacaoCicloService._resolve_associado_contratos(contrato)
        associado = contrato.associado
        parcelas_pagas = sum(
            1
            for parcela in parcelas_projetadas
            if RenovacaoCicloService._is_paid_status(parcela.get("status"))
        )
        parcelas_total = len(parcelas_projetadas)
        if (
            not has_pending_operational_apto
            and not associado_status_apto
            and not is_contract_eligible_for_renewal_competencia(
                contrato,
                competencia=competencia,
                parcelas=parcelas_projetadas,
                projection=projection,
            )
        ):
            return None
        if (
            has_pending_operational_apto
            and status_renovacao not in ACTIVE_OPERATIONAL_REFINANCIAMENTO_STATUSES
        ):
            return None
        if associado_status_apto and not has_pending_operational_apto:
            status_explicacao = "Apto a renovar pelo status atual do associado."
        else:
            status_explicacao = RenovacaoCicloService._build_status_explicacao(
                contrato=contrato,
                status_visual=status_renovacao,
                parcelas_pagas=parcelas_pagas,
                parcelas_total=parcelas_total,
                contratos_associado=contratos_associado,
            )
        ciclo_activation = get_cycle_activation_payload(ciclo)
        contrato_activation = get_contract_activation_payload(contrato)

        return {
            "id": int(representative["id"] if representative else ciclo.id),
            "competencia": competencia.strftime("%m/%Y"),
            "contrato_id": contrato.id,
            "contrato_codigo": contrato.codigo,
            "associado_id": associado.id,
            "nome_associado": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "orgao_publico": associado.orgao_publico,
            "ciclo_id": ciclo.id,
            "ciclo_numero": int(latest_projected_cycle["numero"]),
            "status_ciclo": latest_projected_cycle["status"],
            "status_parcela": (
                representative["status"] if representative else Parcela.Status.EM_PREVISAO
            ),
            "status_visual": status_renovacao,
            "status_explicacao": status_explicacao,
            "data_primeiro_ciclo_ativado": contrato_activation["data_primeiro_ciclo_ativado"],
            "data_ativacao_ciclo": ciclo_activation["data_ativacao_ciclo"],
            "origem_data_ativacao": ciclo_activation["origem_data_ativacao"],
            "data_solicitacao_renovacao": ciclo_activation["data_solicitacao_renovacao"],
            "ativacao_inferida": ciclo_activation["ativacao_inferida"],
            "matricula": (
                associado.matricula_orgao
                or associado.matricula
                or contrato.codigo
            ),
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
            "valor_parcela": (
                representative["valor"] if representative else contrato.valor_mensalidade
            ),
            "data_pagamento": representative["data_pagamento"] if representative else None,
            "orgao_pagto_nome": "",
            "resultado_importacao": "sem_competencia",
            "status_codigo_etipi": "",
            "status_descricao_etipi": "",
            "gerou_encerramento": False,
            "gerou_novo_ciclo": False,
        }

    @staticmethod
    def _row_priority(row: dict[str, object]) -> tuple[int, int, int]:
        return (
            RenovacaoCicloService.STATUS_PRIORITY.get(str(row["status_visual"]), 0),
            int(row["ciclo_numero"]),
            int(row["contrato_id"]),
        )

    @staticmethod
    def _dedupe_rows_by_associado(rows: list[dict[str, object]]) -> list[dict[str, object]]:
        selected: dict[int, dict[str, object]] = {}
        for row in rows:
            associado_id = int(row["associado_id"])
            current = selected.get(associado_id)
            if current is None or RenovacaoCicloService._row_priority(row) > RenovacaoCicloService._row_priority(
                current
            ):
                selected[associado_id] = row
        return sorted(
            selected.values(),
            key=lambda item: (str(item["nome_associado"]).lower(), int(item["contrato_id"])),
        )

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
            1
            for ciclo_parcela in parcelas_ciclo
            if RenovacaoCicloService._is_paid_status(ciclo_parcela.status)
        )
        parcelas_total = len(parcelas_ciclo)
        status_visual = RenovacaoCicloService._status_visual(
            datetime.strptime(competencia, "%m/%Y").date().replace(day=1),
            parcela,
            ciclo,
            proximo_ciclo,
            parcelas_ciclo,
        )
        if import_item and (
            import_item.resultado_processamento
            == ArquivoRetornoItem.ResultadoProcessamento.NAO_DESCONTADO
            or import_item.status_codigo in {"2", "3", "S"}
        ):
            status_visual = "inadimplente"
        elif import_item and (
            import_item.gerou_encerramento or import_item.gerou_novo_ciclo
        ):
            status_visual = "ciclo_renovado"
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
        agente_id: int | None = None,
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> list[dict[str, object]]:
        renewal_only = status == "ciclo_renovado"
        search_value = (search or "").strip()
        projection_cache: dict[int, dict[str, object]] = {}

        def resolve_projection(contrato: Contrato) -> dict[str, object]:
            cached = projection_cache.get(contrato.id)
            if cached is None:
                cached = build_contract_cycle_projection(contrato)
                projection_cache[contrato.id] = cached
            return cached

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
                        "origem_operacional",
                        "auxilio_liberado_em",
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
        if renewal_only:
            parcelas = parcelas.filter(
                Q(ciclo__status=Ciclo.Status.CICLO_RENOVADO)
                | Q(
                    itens_retorno__arquivo_retorno__competencia=competencia,
                    itens_retorno__arquivo_retorno__status=ArquivoRetorno.Status.CONCLUIDO,
                    itens_retorno__gerou_novo_ciclo=True,
                )
                | Q(
                    itens_retorno__arquivo_retorno__competencia=competencia,
                    itens_retorno__arquivo_retorno__status=ArquivoRetorno.Status.CONCLUIDO,
                    itens_retorno__gerou_encerramento=True,
                )
            ).distinct()
        if search_value:
            parcelas = parcelas.filter(
                Q(ciclo__contrato__associado__nome_completo__icontains=search_value)
                | Q(ciclo__contrato__associado__cpf_cnpj__icontains=search_value)
                | Q(ciclo__contrato__associado__matricula__icontains=search_value)
                | Q(ciclo__contrato__associado__matricula_orgao__icontains=search_value)
                | Q(ciclo__contrato__codigo__icontains=search_value)
            )
        if agente_id is not None:
            parcelas = parcelas.filter(ciclo__contrato__agente_id=agente_id)
        if data_inicio:
            parcelas = parcelas.filter(ciclo__contrato__data_contrato__gte=data_inicio)
        if data_fim:
            parcelas = parcelas.filter(ciclo__contrato__data_contrato__lte=data_fim)

        rows: list[dict[str, object]] = []
        for parcela in parcelas:
            itens = getattr(parcela, "itens_retorno_filtrados", [])
            import_item = itens[0] if itens else None
            row = RenovacaoCicloService._build_row(
                parcela,
                competencia.strftime("%m/%Y"),
                import_item,
            )
            if status == "apto_a_renovar":
                projection_status = str(
                    resolve_projection(parcela.ciclo.contrato).get("status_renovacao") or ""
                )
                if projection_status != "apto_a_renovar":
                    continue
            if status and row["status_visual"] != status:
                continue
            rows.append(row)

        itens_suplementares = (
            ArquivoRetornoItem.objects.select_related(
                "associado",
                "parcela",
                "parcela__ciclo",
                "parcela__ciclo__contrato",
                "parcela__ciclo__contrato__agente",
                "parcela__ciclo__contrato__associado",
                "parcela__ciclo__contrato__associado__agente_responsavel",
            )
            .filter(
                arquivo_retorno__competencia=competencia,
                arquivo_retorno__status=ArquivoRetorno.Status.CONCLUIDO,
                associado_id__isnull=False,
                parcela_id__isnull=False,
            )
            .order_by(
                "-arquivo_retorno__processado_em",
                "-arquivo_retorno__created_at",
                "-created_at",
                "-id",
            )
        )
        if renewal_only:
            itens_suplementares = itens_suplementares.filter(
                Q(gerou_novo_ciclo=True) | Q(gerou_encerramento=True)
            )
        for import_item in itens_suplementares:
            contrato = import_item.parcela.ciclo.contrato
            if contrato.status not in [Contrato.Status.ATIVO, Contrato.Status.ENCERRADO]:
                continue
            if agente_id is not None and contrato.agente_id != agente_id:
                continue
            if data_inicio and contrato.data_contrato and contrato.data_contrato < data_inicio:
                continue
            if data_fim and contrato.data_contrato and contrato.data_contrato > data_fim:
                continue
            row = RenovacaoCicloService._build_row(
                import_item.parcela,
                competencia.strftime("%m/%Y"),
                import_item,
            )
            if status == "apto_a_renovar":
                projection_status = str(
                    resolve_projection(contrato).get("status_renovacao") or ""
                )
                if projection_status != "apto_a_renovar":
                    continue
            if status and row["status_visual"] != status:
                continue
            rows.append(row)

        contratos_suplementares = (
            operational_contracts_queryset(
                Contrato.objects.select_related(
                    "agente",
                    "associado",
                    "associado__agente_responsavel",
                ).prefetch_related(
                    Prefetch(
                        "ciclos__parcelas",
                        queryset=Parcela.objects.order_by("numero"),
                        to_attr="parcelas_prefetched",
                    ),
                    Prefetch(
                        "ciclos",
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
                        "associado__contratos",
                        queryset=Contrato.objects.exclude(status=Contrato.Status.CANCELADO).only(
                            "id",
                            "codigo",
                            "status",
                            "origem_operacional",
                            "auxilio_liberado_em",
                            "associado_id",
                        ),
                        to_attr="contratos_contexto_prefetched",
                    ),
                )
            )
            .filter(status__in=[Contrato.Status.ATIVO, Contrato.Status.ENCERRADO])
            .order_by("associado__nome_completo")
        )
        if search_value:
            contratos_suplementares = contratos_suplementares.filter(
                Q(associado__nome_completo__icontains=search_value)
                | Q(associado__cpf_cnpj__icontains=search_value)
                | Q(associado__matricula__icontains=search_value)
                | Q(associado__matricula_orgao__icontains=search_value)
                | Q(codigo__icontains=search_value)
            )
        if agente_id is not None:
            contratos_suplementares = contratos_suplementares.filter(agente_id=agente_id)
        if data_inicio:
            contratos_suplementares = contratos_suplementares.filter(data_contrato__gte=data_inicio)
        if data_fim:
            contratos_suplementares = contratos_suplementares.filter(data_contrato__lte=data_fim)

        if not renewal_only:
            for contrato in contratos_suplementares:
                projection = resolve_projection(contrato)
                row = RenovacaoCicloService._build_projection_only_row(
                    contrato=contrato,
                    competencia=competencia,
                    projection=projection,
                )
                if row is None:
                    continue
                if status and row["status_visual"] != status:
                    continue
                rows.append(row)

        return RenovacaoCicloService._dedupe_rows_by_associado(rows)

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
            if row["status_visual"] != "em_previsao" and row["resultado_importacao"] != "sem_competencia":
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
            financeiro_total = int(financeiro.get("total") or 0)
            if financeiro_total and financeiro_total >= resumo["total_associados"]:
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
