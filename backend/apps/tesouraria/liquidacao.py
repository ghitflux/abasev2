from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado
from apps.contratos.cycle_projection import (
    build_contract_cycle_projection,
    get_associado_visual_status_payload,
)
from apps.contratos.competencia import propagate_competencia_status
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.models import Contrato, Parcela
from apps.refinanciamento.models import Refinanciamento

from .models import LiquidacaoContrato, LiquidacaoContratoAnexo, LiquidacaoContratoItem


ELIGIBLE_PARCELA_STATUSES = {
    Parcela.Status.FUTURO,
    Parcela.Status.EM_PREVISAO,
    Parcela.Status.EM_ABERTO,
    Parcela.Status.NAO_DESCONTADO,
}
LISTABLE_PARCELA_STATUSES = {
    status for status, _label in Parcela.Status.choices if status != Parcela.Status.CANCELADO
}
def _month_matches(value: date | None, competencia: date | None) -> bool:
    if value is None or competencia is None:
        return False
    return value.year == competencia.year and value.month == competencia.month


def _append_note(base: str, note: str) -> str:
    if not base:
        return note
    if note in base:
        return base
    return f"{base}\n{note}"


@dataclass(frozen=True)
class LiquidacaoListPayload:
    rows: list[dict[str, object]]
    kpis: dict[str, object]


class LiquidacaoContratoService:
    @staticmethod
    def _parcelas_for_contract(
        contrato: Contrato,
        *,
        statuses: set[str] | None = None,
    ) -> list[Parcela]:
        prefetched_cycles = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
        parcelas: list[Parcela] = []
        if prefetched_cycles is None:
            queryset = Parcela.all_objects.filter(
                ciclo__contrato=contrato,
                deleted_at__isnull=True,
            )
            if statuses is None:
                queryset = queryset.filter(status__in=LISTABLE_PARCELA_STATUSES)
            else:
                queryset = queryset.filter(status__in=statuses)
            parcelas = list(
                queryset.select_related("ciclo").order_by("referencia_mes", "numero", "id")
            )
        else:
            for ciclo in prefetched_cycles:
                prefetched_parcelas = getattr(ciclo, "_prefetched_objects_cache", {}).get(
                    "parcelas"
                )
                if prefetched_parcelas is None:
                    queryset = ciclo.parcelas.filter(deleted_at__isnull=True)
                    if statuses is None:
                        queryset = queryset.filter(status__in=LISTABLE_PARCELA_STATUSES)
                    else:
                        queryset = queryset.filter(status__in=statuses)
                    current = list(
                        queryset.order_by("referencia_mes", "numero", "id")
                    )
                else:
                    current = [
                        parcela
                        for parcela in prefetched_parcelas
                        if parcela.deleted_at is None
                        and (
                            parcela.status in LISTABLE_PARCELA_STATUSES
                            if statuses is None
                            else parcela.status in statuses
                        )
                    ]
                    current.sort(
                        key=lambda parcela: (parcela.referencia_mes, parcela.numero, parcela.id)
                    )
                parcelas.extend(current)
        return parcelas

    @classmethod
    def _eligible_parcelas_for_contract(cls, contrato: Contrato) -> list[Parcela]:
        return cls._parcelas_for_contract(contrato, statuses=ELIGIBLE_PARCELA_STATUSES)

    @staticmethod
    def _serialize_parcela(parcela: Parcela) -> dict[str, object]:
        return {
            "id": parcela.id,
            "numero": parcela.numero,
            "referencia_mes": parcela.referencia_mes,
            "valor": parcela.valor,
            "status": parcela.status,
            "data_vencimento": parcela.data_vencimento,
            "data_pagamento": parcela.data_pagamento,
            "observacao": parcela.observacao,
        }

    @staticmethod
    def _serialize_item(
        item: LiquidacaoContratoItem,
        *,
        data_liquidacao: date,
    ) -> dict[str, object]:
        return {
            "id": item.parcela_id,
            "numero": item.numero_parcela,
            "referencia_mes": item.referencia_mes,
            "valor": item.valor,
            "status": Parcela.Status.LIQUIDADA,
            "data_vencimento": getattr(item.parcela, "data_vencimento", None),
            "data_pagamento": data_liquidacao,
            "observacao": "Parcela liquidada pela tesouraria.",
        }

    @staticmethod
    def _resolve_solicitacao_origin(
        *,
        persisted_origin: str = "",
        status_renovacao: str = "",
    ) -> str:
        if persisted_origin:
            return persisted_origin
        if status_renovacao == Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO:
            return LiquidacaoContrato.OrigemSolicitacao.RENOVACAO
        return ""

    @classmethod
    def _contracts_for_associado(cls, associado: Associado) -> list[Contrato]:
        prefetched = getattr(associado, "_prefetched_objects_cache", {}).get("contratos")
        if prefetched is None:
            return list(
                Contrato.objects.select_related("agente")
                .prefetch_related(
                    Prefetch(
                        "ciclos__parcelas",
                        queryset=Parcela.all_objects.filter(
                            deleted_at__isnull=True,
                            status__in=LISTABLE_PARCELA_STATUSES,
                        ).order_by("referencia_mes", "numero", "id"),
                    )
                )
                .filter(associado=associado)
                .order_by("-updated_at", "-id")
            )

        contratos = list(prefetched)
        contratos.sort(
            key=lambda contrato: (contrato.updated_at, contrato.id),
            reverse=True,
        )
        return contratos

    @classmethod
    def _select_operational_contracts(
        cls,
        associado: Associado,
    ) -> tuple[Contrato | None, Contrato | None]:
        contratos = cls._contracts_for_associado(associado)
        operational_contract = next(
            (
                contrato
                for contrato in contratos
                if contrato.status not in {Contrato.Status.ENCERRADO, Contrato.Status.CANCELADO}
                and cls._eligible_parcelas_for_contract(contrato)
            ),
            None,
        )
        display_contract = operational_contract or next(
            (
                contrato
                for contrato in contratos
                if contrato.status not in {Contrato.Status.ENCERRADO, Contrato.Status.CANCELADO}
            ),
            None,
        )
        if display_contract is None:
            display_contract = contratos[0] if contratos else None
        return display_contract, operational_contract

    @classmethod
    def _serialize_operational_associado(cls, associado: Associado) -> dict[str, object]:
        display_contract, operational_contract = cls._select_operational_contracts(associado)
        associado_status = get_associado_visual_status_payload(associado)
        parcelas_contrato = (
            cls._parcelas_for_contract(display_contract) if display_contract else []
        )
        parcelas = (
            cls._eligible_parcelas_for_contract(operational_contract)
            if operational_contract
            else []
        )
        projection = (
            build_contract_cycle_projection(display_contract) if display_contract else {}
        )
        status_renovacao = str(projection.get("status_renovacao") or "")
        pode_liquidar_agora = bool(parcelas)
        if pode_liquidar_agora:
            status_operacional = "elegivel_agora"
        elif display_contract:
            status_operacional = "sem_parcelas_elegiveis"
        else:
            status_operacional = "sem_contrato"
        primeira_referencia = parcelas[0].referencia_mes if parcelas else None
        ultima_referencia = parcelas[-1].referencia_mes if parcelas else None
        return {
            "id": associado.id,
            "contrato_id": display_contract.id if display_contract else None,
            "liquidacao_id": None,
            "associado_id": associado.id,
            "nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula,
            "agente_nome": (
                display_contract.agente.full_name
                if display_contract and display_contract.agente
                else ""
            ),
            "contrato_codigo": display_contract.codigo if display_contract else "",
            "quantidade_parcelas": len(parcelas),
            "quantidade_parcelas_contrato": len(parcelas_contrato),
            "valor_total": sum((parcela.valor for parcela in parcelas), Decimal("0.00")),
            "referencia_inicial": primeira_referencia,
            "referencia_final": ultima_referencia,
            "status_liquidacao": status_operacional,
            "status_operacional": status_operacional,
            "pode_liquidar_agora": pode_liquidar_agora,
            "status_associado": str(associado_status.get("status_visual_slug") or ""),
            "status_associado_label": str(associado_status.get("status_visual_label") or ""),
            "status_contrato": display_contract.status if display_contract else "",
            "status_renovacao": status_renovacao,
            "origem_solicitacao": cls._resolve_solicitacao_origin(
                status_renovacao=status_renovacao
            ),
            "data_liquidacao": None,
            "observacao": "",
            "realizado_por": None,
            "revertida_em": None,
            "revertida_por": None,
            "motivo_reversao": "",
            "comprovante_obj": None,
            "nome_comprovante": "",
            "parcelas": [
                cls._serialize_parcela(parcela) for parcela in parcelas_contrato
            ],
        }

    @classmethod
    def _serialize_liquidacao(cls, liquidacao: LiquidacaoContrato) -> dict[str, object]:
        contrato = liquidacao.contrato
        associado_status = get_associado_visual_status_payload(contrato.associado)
        projection = build_contract_cycle_projection(contrato)
        status_renovacao = str(projection.get("status_renovacao") or "")
        itens = sorted(
            list(getattr(liquidacao, "_prefetched_objects_cache", {}).get("itens", liquidacao.itens.all())),
            key=lambda item: (item.referencia_mes, item.numero_parcela, item.id),
        )
        anexos = sorted(
            list(
                getattr(liquidacao, "_prefetched_objects_cache", {}).get(
                    "anexos",
                    liquidacao.anexos.all(),
                )
            ),
            key=lambda anexo: (anexo.created_at, anexo.id),
        )
        primeira_referencia = itens[0].referencia_mes if itens else None
        ultima_referencia = itens[-1].referencia_mes if itens else None
        return {
            "id": contrato.id,
            "contrato_id": contrato.id,
            "liquidacao_id": liquidacao.id,
            "associado_id": contrato.associado_id,
            "nome": contrato.associado.nome_completo,
            "cpf_cnpj": contrato.associado.cpf_cnpj,
            "matricula": contrato.associado.matricula_orgao or contrato.associado.matricula,
            "agente_nome": contrato.agente.full_name if contrato.agente else "",
            "contrato_codigo": contrato.codigo,
            "quantidade_parcelas": len(itens),
            "quantidade_parcelas_contrato": len(itens),
            "valor_total": liquidacao.valor_total,
            "referencia_inicial": primeira_referencia,
            "referencia_final": ultima_referencia,
            "status_liquidacao": "revertida" if liquidacao.revertida_em else "liquidado",
            "status_operacional": "revertida" if liquidacao.revertida_em else "liquidado",
            "pode_liquidar_agora": False,
            "status_associado": str(associado_status.get("status_visual_slug") or ""),
            "status_associado_label": str(associado_status.get("status_visual_label") or ""),
            "status_contrato": contrato.status,
            "status_renovacao": status_renovacao,
            "origem_solicitacao": cls._resolve_solicitacao_origin(
                persisted_origin=liquidacao.origem_solicitacao,
                status_renovacao=status_renovacao,
            ),
            "data_liquidacao": liquidacao.data_liquidacao,
            "observacao": liquidacao.observacao,
            "realizado_por": liquidacao.realizado_por,
            "revertida_em": liquidacao.revertida_em,
            "revertida_por": liquidacao.revertida_por,
            "motivo_reversao": liquidacao.motivo_reversao,
            "comprovante_obj": liquidacao.comprovante,
            "nome_comprovante": liquidacao.nome_comprovante,
            "anexos_obj": anexos,
            "parcelas": [
                cls._serialize_item(item, data_liquidacao=liquidacao.data_liquidacao)
                for item in itens
            ],
        }

    @staticmethod
    def _build_kpis(rows: list[dict[str, object]]) -> dict[str, object]:
        associados = {int(row["associado_id"]) for row in rows}
        associados_por_status: dict[str, set[int]] = {}
        for row in rows:
            status_associado = str(row.get("status_associado") or "")
            if not status_associado:
                continue
            associados_por_status.setdefault(status_associado, set()).add(
                int(row["associado_id"])
            )
        return {
            "total_contratos": len(rows),
            "total_parcelas": sum(int(row["quantidade_parcelas"]) for row in rows),
            "valor_total": sum((Decimal(row["valor_total"]) for row in rows), Decimal("0.00")),
            "associados_impactados": len(associados),
            "revertidas": sum(1 for row in rows if row["status_liquidacao"] == "revertida"),
            "ativas": sum(1 for row in rows if row["status_liquidacao"] == "liquidado"),
            "liquidaveis_agora": sum(
                1 for row in rows if bool(row.get("pode_liquidar_agora"))
            ),
            "sem_parcelas_elegiveis": sum(
                1
                for row in rows
                if row.get("status_operacional") == "sem_parcelas_elegiveis"
            ),
            "por_status_associado": {
                status: len(associado_ids)
                for status, associado_ids in sorted(associados_por_status.items())
            },
        }

    @classmethod
    def listar(
        cls,
        *,
        listing_status: str,
        search: str | None = None,
        competencia: date | None = None,
        estado: str | None = None,
        contract_id: int | None = None,
    ) -> LiquidacaoListPayload:
        if listing_status == "liquidado":
            queryset = (
                LiquidacaoContrato.objects.select_related(
                    "contrato__associado",
                    "contrato__agente",
                    "realizado_por",
                    "revertida_por",
                )
                .prefetch_related(
                    Prefetch(
                        "itens",
                        queryset=LiquidacaoContratoItem.objects.select_related("parcela").order_by(
                            "referencia_mes",
                            "numero_parcela",
                            "id",
                        ),
                    ),
                    "anexos",
                )
                .order_by("-data_liquidacao", "-created_at", "-id")
            )
            if search:
                queryset = queryset.filter(
                    Q(contrato__codigo__icontains=search)
                    | Q(contrato__associado__nome_completo__icontains=search)
                    | Q(contrato__associado__cpf_cnpj__icontains=search)
                    | Q(contrato__associado__matricula__icontains=search)
                    | Q(contrato__associado__matricula_orgao__icontains=search)
                )
            if contract_id:
                queryset = queryset.filter(contrato_id=contract_id)
            if competencia:
                queryset = queryset.filter(
                    data_liquidacao__year=competencia.year,
                    data_liquidacao__month=competencia.month,
                )
            if estado == "revertida":
                queryset = queryset.filter(revertida_em__isnull=False)
            elif estado == "ativa":
                queryset = queryset.filter(revertida_em__isnull=True)

            rows = [cls._serialize_liquidacao(item) for item in queryset]
            return LiquidacaoListPayload(rows=rows, kpis=cls._build_kpis(rows))

        contract_queryset = (
            Contrato.objects.select_related("agente")
            .prefetch_related(
                Prefetch(
                    "ciclos__parcelas",
                    queryset=Parcela.all_objects.filter(
                        deleted_at__isnull=True,
                        status__in=LISTABLE_PARCELA_STATUSES,
                    ).order_by("referencia_mes", "numero", "id"),
                )
            )
            .order_by("-updated_at", "-id")
        )
        queryset = (
            Associado.objects.prefetch_related(
                Prefetch(
                    "contratos",
                    queryset=contract_queryset,
                )
            )
            .distinct()
            .order_by("nome_completo", "id")
        )
        if search:
            queryset = queryset.filter(
                Q(nome_completo__icontains=search)
                | Q(cpf_cnpj__icontains=search)
                | Q(matricula__icontains=search)
                | Q(matricula_orgao__icontains=search)
                | Q(contratos__codigo__icontains=search)
            )
        if contract_id:
            queryset = queryset.filter(contratos__pk=contract_id)
        if competencia:
            queryset = queryset.filter(
                contratos__ciclos__parcelas__referencia_mes__year=competencia.year,
                contratos__ciclos__parcelas__referencia_mes__month=competencia.month,
                contratos__ciclos__parcelas__status__in=LISTABLE_PARCELA_STATUSES,
                contratos__ciclos__parcelas__deleted_at__isnull=True,
            )

        rows = []
        for associado in queryset:
            rows.append(cls._serialize_operational_associado(associado))
        return LiquidacaoListPayload(rows=rows, kpis=cls._build_kpis(rows))

    @classmethod
    def _get_contract_for_update(cls, contrato_id: int) -> Contrato:
        try:
            return (
                Contrato.objects.select_for_update()
                .select_related("associado", "agente")
                .prefetch_related(
                    Prefetch(
                        "ciclos__parcelas",
                        queryset=Parcela.all_objects.filter(
                            deleted_at__isnull=True,
                        )
                        .exclude(status=Parcela.Status.CANCELADO)
                        .order_by("referencia_mes", "numero", "id"),
                    )
                )
                .get(pk=contrato_id)
            )
        except Contrato.DoesNotExist as exc:
            raise ValidationError("Contrato não encontrado.") from exc

    @classmethod
    @transaction.atomic
    def liquidar_contrato(
        cls,
        contrato_id: int,
        *,
        comprovantes,
        origem_solicitacao: str,
        data_liquidacao: date,
        valor_total: Decimal,
        observacao: str,
        user,
    ) -> LiquidacaoContrato:
        contrato = cls._get_contract_for_update(contrato_id)
        if contrato.status in {Contrato.Status.ENCERRADO, Contrato.Status.CANCELADO}:
            raise ValidationError("Contratos cancelados ou já encerrados não podem ser liquidados.")
        if LiquidacaoContrato.objects.filter(
            contrato=contrato,
            revertida_em__isnull=True,
        ).exists():
            raise ValidationError("Este contrato já possui uma liquidação ativa.")

        parcelas = cls._eligible_parcelas_for_contract(contrato)
        if not parcelas:
            raise ValidationError("O contrato não possui parcelas elegíveis para liquidação.")

        if not comprovantes:
            raise ValidationError("Envie pelo menos um comprovante para a liquidação.")

        comprovante_principal = comprovantes[0]
        liquidacao = LiquidacaoContrato.objects.create(
            contrato=contrato,
            realizado_por=user,
            data_liquidacao=data_liquidacao,
            valor_total=valor_total,
            comprovante=comprovante_principal,
            nome_comprovante=getattr(comprovante_principal, "name", ""),
            origem_solicitacao=origem_solicitacao,
            observacao=observacao or "",
            contrato_status_anterior=contrato.status,
            associado_status_anterior=contrato.associado.status,
        )
        for arquivo in comprovantes[1:]:
            LiquidacaoContratoAnexo.objects.create(
                liquidacao=liquidacao,
                arquivo=arquivo,
                nome_arquivo=getattr(arquivo, "name", "")[:255],
            )
        LiquidacaoContratoItem.objects.bulk_create(
            [
                LiquidacaoContratoItem(
                    liquidacao=liquidacao,
                    parcela=parcela,
                    numero_parcela=parcela.numero,
                    referencia_mes=parcela.referencia_mes,
                    status_anterior=parcela.status,
                    data_pagamento_anterior=parcela.data_pagamento,
                    observacao_anterior=parcela.observacao,
                    valor=parcela.valor,
                )
                for parcela in parcelas
            ]
        )

        note = (
            f"Parcela liquidada pela tesouraria em {data_liquidacao.strftime('%d/%m/%Y')}."
        )
        if observacao:
            note = f"{note} {observacao}"
        for parcela in parcelas:
            parcela.status = Parcela.Status.LIQUIDADA
            parcela.data_pagamento = data_liquidacao
            parcela.observacao = _append_note(parcela.observacao, note)
            parcela.save(
                update_fields=[
                    "status",
                    "data_pagamento",
                    "observacao",
                    "updated_at",
                ]
            )
            propagate_competencia_status(parcela)

        contrato.status = Contrato.Status.ENCERRADO
        contrato.save(update_fields=["status", "updated_at"])

        has_other_active_contracts = Contrato.objects.filter(
            associado=contrato.associado,
            status=Contrato.Status.ATIVO,
        ).exclude(pk=contrato.pk).exists()
        if not has_other_active_contracts and contrato.associado.status != Associado.Status.INATIVO:
            contrato.associado.status = Associado.Status.INATIVO
            contrato.associado.save(update_fields=["status", "updated_at"])

        rebuild_contract_cycle_state(contrato, execute=True)
        liquidacao.refresh_from_db()
        return liquidacao

    @classmethod
    @transaction.atomic
    def reverter_liquidacao(
        cls,
        contrato_id: int,
        *,
        motivo_reversao: str,
        user,
    ) -> LiquidacaoContrato:
        if not (getattr(user, "is_superuser", False) or user.has_role("ADMIN")):
            raise ValidationError("A reversão de liquidação é restrita a administradores.")

        liquidacao = (
            LiquidacaoContrato.objects.select_for_update()
            .select_related("contrato__associado", "revertida_por")
            .prefetch_related(
                Prefetch(
                    "itens",
                    queryset=LiquidacaoContratoItem.objects.select_related("parcela").order_by(
                        "referencia_mes",
                        "numero_parcela",
                        "id",
                    ),
                )
            )
            .filter(contrato_id=contrato_id, revertida_em__isnull=True)
            .order_by("-created_at", "-id")
            .first()
        )
        if liquidacao is None:
            raise ValidationError("Não há liquidação ativa para este contrato.")

        itens = list(liquidacao.itens.all())
        parcelas_invalidas = [
            item.referencia_mes.strftime("%m/%Y")
            for item in itens
            if item.parcela.status != Parcela.Status.LIQUIDADA
        ]
        if parcelas_invalidas:
            raise ValidationError(
                "Não é possível reverter porque parcelas da liquidação foram alteradas depois da execução."
            )

        contrato = liquidacao.contrato
        for item in itens:
            parcela = item.parcela
            parcela.status = item.status_anterior
            parcela.data_pagamento = item.data_pagamento_anterior
            parcela.observacao = item.observacao_anterior
            parcela.save(
                update_fields=[
                    "status",
                    "data_pagamento",
                    "observacao",
                    "updated_at",
                ]
            )
            propagate_competencia_status(parcela)

        contrato.status = liquidacao.contrato_status_anterior or Contrato.Status.ATIVO
        contrato.save(update_fields=["status", "updated_at"])

        associado = contrato.associado
        has_active_contract = Contrato.objects.filter(
            associado=associado,
            status=Contrato.Status.ATIVO,
        ).exists()
        associado.status = (
            Associado.Status.ATIVO
            if has_active_contract
            else liquidacao.associado_status_anterior or associado.status
        )
        associado.save(update_fields=["status", "updated_at"])

        liquidacao.revertida_em = timezone.now()
        liquidacao.revertida_por = user
        liquidacao.motivo_reversao = motivo_reversao or ""
        liquidacao.save(
            update_fields=[
                "revertida_em",
                "revertida_por",
                "motivo_reversao",
                "updated_at",
            ]
        )

        rebuild_contract_cycle_state(contrato, execute=True)
        liquidacao.refresh_from_db()
        return liquidacao

    @classmethod
    @transaction.atomic
    def excluir_liquidacao(
        cls,
        liquidacao_id: int,
        *,
        motivo_exclusao: str,
        user,
    ) -> LiquidacaoContrato:
        if not (getattr(user, "is_superuser", False) or user.has_role("ADMIN")):
            raise ValidationError("A exclusão de liquidação é restrita a administradores.")

        liquidacao = (
            LiquidacaoContrato.all_objects.select_for_update()
            .select_related("contrato__associado")
            .prefetch_related("itens", "anexos")
            .filter(pk=liquidacao_id, deleted_at__isnull=True)
            .first()
        )
        if liquidacao is None:
            raise ValidationError("Registro de liquidação não encontrado.")

        motivo = motivo_exclusao.strip()
        if not liquidacao.revertida_em:
            cls.reverter_liquidacao(
                liquidacao.contrato_id,
                motivo_reversao=motivo,
                user=user,
            )
            liquidacao = (
                LiquidacaoContrato.all_objects.select_for_update()
                .select_related("contrato__associado")
                .prefetch_related("itens", "anexos")
                .get(pk=liquidacao_id)
            )
        else:
            liquidacao.motivo_reversao = _append_note(liquidacao.motivo_reversao, motivo)
            liquidacao.save(update_fields=["motivo_reversao", "updated_at"])

        now = timezone.now()
        liquidacao.itens.update(deleted_at=now, updated_at=now)
        liquidacao.anexos.update(deleted_at=now, updated_at=now)
        liquidacao.deleted_at = now
        liquidacao.save(update_fields=["deleted_at", "updated_at"])
        liquidacao.refresh_from_db()
        return liquidacao
