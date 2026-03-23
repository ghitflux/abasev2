from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.associados.models import Associado
from apps.contratos.cycle_projection import build_contract_cycle_projection
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
    def _eligible_parcelas_for_contract(contrato: Contrato) -> list[Parcela]:
        prefetched_cycles = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
        parcelas: list[Parcela] = []
        if prefetched_cycles is None:
            parcelas = list(
                Parcela.all_objects.filter(
                    ciclo__contrato=contrato,
                    deleted_at__isnull=True,
                    status__in=ELIGIBLE_PARCELA_STATUSES,
                )
                .select_related("ciclo")
                .order_by("referencia_mes", "numero", "id")
            )
        else:
            for ciclo in prefetched_cycles:
                prefetched_parcelas = getattr(ciclo, "_prefetched_objects_cache", {}).get(
                    "parcelas"
                )
                if prefetched_parcelas is None:
                    current = list(
                        ciclo.parcelas.filter(
                            deleted_at__isnull=True,
                            status__in=ELIGIBLE_PARCELA_STATUSES,
                        ).order_by("referencia_mes", "numero", "id")
                    )
                else:
                    current = [
                        parcela
                        for parcela in prefetched_parcelas
                        if parcela.deleted_at is None
                        and parcela.status in ELIGIBLE_PARCELA_STATUSES
                    ]
                    current.sort(key=lambda parcela: (parcela.referencia_mes, parcela.numero, parcela.id))
                parcelas.extend(current)
        return parcelas

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

    @classmethod
    def _serialize_eligible_contract(cls, contrato: Contrato) -> dict[str, object] | None:
        parcelas = cls._eligible_parcelas_for_contract(contrato)
        if not parcelas:
            return None
        projection = build_contract_cycle_projection(contrato)
        status_renovacao = str(projection.get("status_renovacao") or "")
        primeira_referencia = parcelas[0].referencia_mes
        ultima_referencia = parcelas[-1].referencia_mes
        return {
            "id": contrato.id,
            "contrato_id": contrato.id,
            "liquidacao_id": None,
            "associado_id": contrato.associado_id,
            "nome": contrato.associado.nome_completo,
            "cpf_cnpj": contrato.associado.cpf_cnpj,
            "matricula": contrato.associado.matricula_orgao or contrato.associado.matricula,
            "agente_nome": contrato.agente.full_name if contrato.agente else "",
            "contrato_codigo": contrato.codigo,
            "quantidade_parcelas": len(parcelas),
            "valor_total": sum((parcela.valor for parcela in parcelas), Decimal("0.00")),
            "referencia_inicial": primeira_referencia,
            "referencia_final": ultima_referencia,
            "status_liquidacao": "elegivel",
            "status_contrato": contrato.status,
            "status_renovacao": status_renovacao,
            "origem_solicitacao": (
                "renovacao"
                if status_renovacao == Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO
                else ""
            ),
            "data_liquidacao": None,
            "observacao": "",
            "realizado_por": None,
            "revertida_em": None,
            "revertida_por": None,
            "motivo_reversao": "",
            "comprovante_obj": None,
            "nome_comprovante": "",
            "parcelas": [cls._serialize_parcela(parcela) for parcela in parcelas],
        }

    @classmethod
    def _serialize_liquidacao(cls, liquidacao: LiquidacaoContrato) -> dict[str, object]:
        contrato = liquidacao.contrato
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
            "valor_total": liquidacao.valor_total,
            "referencia_inicial": primeira_referencia,
            "referencia_final": ultima_referencia,
            "status_liquidacao": "revertida" if liquidacao.revertida_em else "liquidado",
            "status_contrato": contrato.status,
            "status_renovacao": status_renovacao,
            "origem_solicitacao": (
                "renovacao"
                if status_renovacao == Refinanciamento.Status.SOLICITADO_PARA_LIQUIDACAO
                else ""
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
        return {
            "total_contratos": len(rows),
            "total_parcelas": sum(int(row["quantidade_parcelas"]) for row in rows),
            "valor_total": sum((Decimal(row["valor_total"]) for row in rows), Decimal("0.00")),
            "associados_impactados": len(associados),
            "revertidas": sum(1 for row in rows if row["status_liquidacao"] == "revertida"),
            "ativas": sum(1 for row in rows if row["status_liquidacao"] == "liquidado"),
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

        queryset = (
            Contrato.objects.select_related("associado", "agente")
            .prefetch_related(
                Prefetch(
                    "ciclos__parcelas",
                    queryset=Parcela.all_objects.filter(
                        deleted_at__isnull=True,
                        status__in=ELIGIBLE_PARCELA_STATUSES,
                    ).order_by("referencia_mes", "numero", "id"),
                )
            )
            .filter(
                status=Contrato.Status.ATIVO,
                ciclos__parcelas__deleted_at__isnull=True,
                ciclos__parcelas__status__in=ELIGIBLE_PARCELA_STATUSES,
            )
            .distinct()
            .order_by("-updated_at", "-id")
        )
        if search:
            queryset = queryset.filter(
                Q(codigo__icontains=search)
                | Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
                | Q(associado__matricula_orgao__icontains=search)
            )
        if contract_id:
            queryset = queryset.filter(pk=contract_id)
        if competencia:
            queryset = queryset.filter(
                ciclos__parcelas__referencia_mes__year=competencia.year,
                ciclos__parcelas__referencia_mes__month=competencia.month,
                ciclos__parcelas__status__in=ELIGIBLE_PARCELA_STATUSES,
                ciclos__parcelas__deleted_at__isnull=True,
            )

        rows = []
        for contrato in queryset:
            row = cls._serialize_eligible_contract(contrato)
            if row is not None:
                rows.append(row)
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
        data_liquidacao: date,
        valor_total: Decimal,
        observacao: str,
        user,
    ) -> LiquidacaoContrato:
        contrato = cls._get_contract_for_update(contrato_id)
        if contrato.status in {Contrato.Status.ENCERRADO, Contrato.Status.CANCELADO}:
            raise ValidationError("Apenas contratos ativos podem ser liquidados.")
        if contrato.status != Contrato.Status.ATIVO:
            raise ValidationError("O contrato precisa estar ativo para ser liquidado.")
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
