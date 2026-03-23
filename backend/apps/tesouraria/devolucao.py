from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.contratos.models import Contrato

from .models import DevolucaoAssociado, DevolucaoAssociadoAnexo


def _append_note(base: str, note: str) -> str:
    if not base:
        return note
    if note in base:
        return base
    return f"{base}\n{note}"


@dataclass(frozen=True)
class DevolucaoListPayload:
    rows: list[dict[str, object]]
    kpis: dict[str, object]


class DevolucaoAssociadoService:
    @staticmethod
    def _contract_queryset():
        return Contrato.objects.select_related("associado", "agente").order_by(
            "-updated_at",
            "-id",
        )

    @staticmethod
    def _history_queryset():
        return DevolucaoAssociado.objects.select_related(
            "contrato",
            "associado",
            "realizado_por",
            "revertida_por",
        ).prefetch_related("anexos").order_by("-data_devolucao", "-created_at", "-id")

    @staticmethod
    def _serialize_contract(contrato: Contrato) -> dict[str, object]:
        associado = contrato.associado
        agente = contrato.agente or getattr(associado, "agente_responsavel", None)
        return {
            "id": contrato.id,
            "contrato_id": contrato.id,
            "associado_id": associado.id,
            "nome": associado.nome_completo,
            "cpf_cnpj": associado.cpf_cnpj,
            "matricula": associado.matricula_orgao or associado.matricula or "",
            "agente_nome": agente.full_name if agente else "",
            "contrato_codigo": contrato.codigo,
            "status_contrato": contrato.status,
            "data_contrato": contrato.data_contrato,
            "mes_averbacao": contrato.mes_averbacao,
        }

    @staticmethod
    def _serialize_history(item: DevolucaoAssociado) -> dict[str, object]:
        return {
            "id": item.id,
            "devolucao_id": item.id,
            "contrato_id": item.contrato_id,
            "associado_id": item.associado_id,
            "tipo": item.tipo,
            "status_devolucao": item.status,
            "data_devolucao": item.data_devolucao,
            "quantidade_parcelas": item.quantidade_parcelas,
            "valor": item.valor,
            "motivo": item.motivo,
            "competencia_referencia": item.competencia_referencia,
            "nome": item.nome_snapshot,
            "cpf_cnpj": item.cpf_cnpj_snapshot,
            "matricula": item.matricula_snapshot,
            "agente_nome": item.agente_snapshot,
            "contrato_codigo": item.contrato_codigo_snapshot,
            "status_contrato": item.contrato.status,
            "realizado_por": item.realizado_por,
            "revertida_em": item.revertida_em,
            "revertida_por": item.revertida_por,
            "motivo_reversao": item.motivo_reversao,
            "comprovante_obj": item.comprovante,
            "nome_comprovante": item.nome_comprovante,
            "anexos_obj": list(getattr(item, "_prefetched_objects_cache", {}).get("anexos", item.anexos.all())),
        }

    @staticmethod
    def _build_contract_kpis(rows: list[dict[str, object]]) -> dict[str, object]:
        associados = {int(row["associado_id"]) for row in rows}
        return {
            "total_contratos": len(rows),
            "associados_impactados": len(associados),
            "ativos": sum(1 for row in rows if row["status_contrato"] == Contrato.Status.ATIVO),
            "encerrados": sum(
                1 for row in rows if row["status_contrato"] == Contrato.Status.ENCERRADO
            ),
            "cancelados": sum(
                1 for row in rows if row["status_contrato"] == Contrato.Status.CANCELADO
            ),
            "total_registros": 0,
            "valor_total": Decimal("0.00"),
            "registradas": 0,
            "revertidas": 0,
        }

    @staticmethod
    def _build_history_kpis(rows: list[dict[str, object]]) -> dict[str, object]:
        associados = {int(row["associado_id"]) for row in rows}
        return {
            "total_contratos": len({int(row["contrato_id"]) for row in rows}),
            "associados_impactados": len(associados),
            "ativos": 0,
            "encerrados": 0,
            "cancelados": 0,
            "total_registros": len(rows),
            "valor_total": sum((Decimal(row["valor"]) for row in rows), Decimal("0.00")),
            "registradas": sum(1 for row in rows if row["status_devolucao"] == "registrada"),
            "revertidas": sum(1 for row in rows if row["status_devolucao"] == "revertida"),
        }

    @classmethod
    def listar_contratos(
        cls,
        *,
        search: str | None = None,
        estado: str | None = None,
        competencia: date | None = None,
        contract_id: int | None = None,
    ) -> DevolucaoListPayload:
        queryset = cls._contract_queryset()
        if search:
            queryset = queryset.filter(
                Q(codigo__icontains=search)
                | Q(associado__nome_completo__icontains=search)
                | Q(associado__cpf_cnpj__icontains=search)
                | Q(associado__matricula__icontains=search)
                | Q(associado__matricula_orgao__icontains=search)
                | Q(agente__first_name__icontains=search)
                | Q(agente__last_name__icontains=search)
                | Q(agente__email__icontains=search)
            )
        if estado in {choice[0] for choice in Contrato.Status.choices}:
            queryset = queryset.filter(status=estado)
        if contract_id:
            queryset = queryset.filter(pk=contract_id)
        if competencia:
            queryset = queryset.filter(
                Q(ciclos__parcelas__referencia_mes__year=competencia.year)
                & Q(ciclos__parcelas__referencia_mes__month=competencia.month)
            )
        queryset = queryset.distinct()
        rows = [cls._serialize_contract(contrato) for contrato in queryset]
        return DevolucaoListPayload(rows=rows, kpis=cls._build_contract_kpis(rows))

    @classmethod
    def listar_historico(
        cls,
        *,
        search: str | None = None,
        tipo: str | None = None,
        status: str | None = None,
        competencia: date | None = None,
        contract_id: int | None = None,
    ) -> DevolucaoListPayload:
        queryset = cls._history_queryset()
        if search:
            queryset = queryset.filter(
                Q(nome_snapshot__icontains=search)
                | Q(cpf_cnpj_snapshot__icontains=search)
                | Q(matricula_snapshot__icontains=search)
                | Q(agente_snapshot__icontains=search)
                | Q(contrato_codigo_snapshot__icontains=search)
            )
        if tipo in {choice[0] for choice in DevolucaoAssociado.Tipo.choices}:
            queryset = queryset.filter(tipo=tipo)
        if status == "registrada":
            queryset = queryset.filter(revertida_em__isnull=True)
        elif status == "revertida":
            queryset = queryset.filter(revertida_em__isnull=False)
        if contract_id:
            queryset = queryset.filter(contrato_id=contract_id)
        if competencia:
            queryset = queryset.filter(
                competencia_referencia__year=competencia.year,
                competencia_referencia__month=competencia.month,
            )

        rows = [cls._serialize_history(item) for item in queryset]
        return DevolucaoListPayload(rows=rows, kpis=cls._build_history_kpis(rows))

    @classmethod
    def _get_contract_for_update(cls, contrato_id: int) -> Contrato:
        try:
            return cls._contract_queryset().select_for_update().get(pk=contrato_id)
        except Contrato.DoesNotExist as exc:
            raise ValidationError("Contrato não encontrado.") from exc

    @classmethod
    @transaction.atomic
    def registrar(
        cls,
        contrato_id: int,
        *,
        tipo: str,
        data_devolucao: date,
        quantidade_parcelas: int,
        valor: Decimal,
        motivo: str,
        comprovantes: list,
        competencia_referencia: date | None,
        user,
    ) -> DevolucaoAssociado:
        contrato = cls._get_contract_for_update(contrato_id)
        associado = contrato.associado
        agente = contrato.agente or getattr(associado, "agente_responsavel", None)

        if tipo == DevolucaoAssociado.Tipo.DESCONTO_INDEVIDO and competencia_referencia is None:
            raise ValidationError(
                {"competencia_referencia": "Informe a competência de referência para desconto indevido."}
            )

        if quantidade_parcelas < 1:
            raise ValidationError(
                {"quantidade_parcelas": "Informe pelo menos uma parcela."}
            )
        if not comprovantes:
            raise ValidationError({"comprovantes": "Envie pelo menos um anexo."})

        comprovante_principal = comprovantes[0]
        devolucao = DevolucaoAssociado.objects.create(
            contrato=contrato,
            associado=associado,
            tipo=tipo,
            data_devolucao=data_devolucao,
            quantidade_parcelas=quantidade_parcelas,
            valor=valor,
            motivo=motivo,
            comprovante=comprovante_principal,
            nome_comprovante=getattr(comprovante_principal, "name", "")[:255],
            competencia_referencia=competencia_referencia,
            nome_snapshot=associado.nome_completo,
            cpf_cnpj_snapshot=associado.cpf_cnpj,
            matricula_snapshot=associado.matricula_orgao or associado.matricula or "",
            agente_snapshot=agente.full_name if agente else "",
            contrato_codigo_snapshot=contrato.codigo,
            realizado_por=user,
        )
        for arquivo in comprovantes[1:]:
            DevolucaoAssociadoAnexo.objects.create(
                devolucao=devolucao,
                arquivo=arquivo,
                nome_arquivo=getattr(arquivo, "name", "")[:255],
            )
        devolucao.refresh_from_db()
        return devolucao

    @classmethod
    @transaction.atomic
    def reverter(
        cls,
        devolucao_id: int,
        *,
        motivo_reversao: str,
        user,
    ) -> DevolucaoAssociado:
        if not (getattr(user, "is_superuser", False) or user.has_role("ADMIN")):
            raise ValidationError("A reversão de devolução é restrita a administradores.")

        devolucao = (
            cls._history_queryset()
            .select_for_update()
            .filter(pk=devolucao_id, revertida_em__isnull=True)
            .first()
        )
        if devolucao is None:
            raise ValidationError("Não há devolução ativa para este registro.")

        devolucao.revertida_em = timezone.now()
        devolucao.revertida_por = user
        devolucao.motivo_reversao = motivo_reversao
        devolucao.save(
            update_fields=[
                "revertida_em",
                "revertida_por",
                "motivo_reversao",
                "updated_at",
            ]
        )
        devolucao.refresh_from_db()
        return devolucao

    @classmethod
    @transaction.atomic
    def excluir(
        cls,
        devolucao_id: int,
        *,
        motivo_exclusao: str,
        user,
    ) -> DevolucaoAssociado:
        if not (getattr(user, "is_superuser", False) or user.has_role("ADMIN")):
            raise ValidationError("A exclusão de devolução é restrita a administradores.")

        devolucao = (
            DevolucaoAssociado.all_objects.select_for_update()
            .prefetch_related("anexos")
            .filter(pk=devolucao_id, deleted_at__isnull=True)
            .first()
        )
        if devolucao is None:
            raise ValidationError("Registro de devolução não encontrado.")

        motivo = motivo_exclusao.strip()
        now = timezone.now()
        if not devolucao.revertida_em:
            devolucao.revertida_em = now
            devolucao.revertida_por = user
        devolucao.motivo_reversao = _append_note(devolucao.motivo_reversao, motivo)
        devolucao.anexos.update(deleted_at=now, updated_at=now)
        devolucao.deleted_at = now
        devolucao.save(
            update_fields=[
                "revertida_em",
                "revertida_por",
                "motivo_reversao",
                "deleted_at",
                "updated_at",
            ]
        )
        devolucao.refresh_from_db()
        return devolucao
