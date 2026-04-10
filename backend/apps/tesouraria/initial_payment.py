from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from django.db import models
from django.utils import timezone

from apps.contratos.models import Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento
from apps.tesouraria.models import Pagamento
from core.file_references import build_filefield_reference, build_storage_reference


def _payment_display_value(pagamento: Pagamento | None) -> Decimal | None:
    if pagamento is None:
        return None
    return pagamento.valor_pago or pagamento.contrato_margem_disponivel


def _payment_status_label(pagamento: Pagamento | None) -> str:
    if pagamento is None:
        return "Sem pagamento inicial"
    return pagamento.get_status_display()


def _is_renewal_payment(pagamento: Pagamento) -> bool:
    notes = (pagamento.notes or "").lower()
    return "renova" in notes and "tesouraria" in notes


def _candidate_initial_payments(contrato: Contrato) -> list[Pagamento]:
    related = getattr(contrato.associado, "tesouraria_pagamentos", None)
    if related is not None:
        pagamentos = [
            pagamento
            for pagamento in related.all()
            if pagamento.contrato_codigo == contrato.codigo
        ]
    else:
        pagamentos = list(
            Pagamento.all_objects.filter(
                cadastro=contrato.associado,
                contrato_codigo=contrato.codigo,
            ).order_by("created_at", "id")
        )

    initial = [pagamento for pagamento in pagamentos if not _is_renewal_payment(pagamento)]
    if initial:
        pagamentos = initial
    pagamentos.sort(
        key=lambda pagamento: (
            0 if pagamento.legacy_tesouraria_pagamento_id else 1,
            pagamento.created_at,
            pagamento.id,
        )
    )
    return pagamentos


def get_initial_payment_for_contract(contrato: Contrato) -> Pagamento | None:
    pagamentos = _candidate_initial_payments(contrato)
    return pagamentos[0] if pagamentos else None


def _payment_reference_entry(
    *,
    pagamento: Pagamento,
    papel: str,
    tipo: str,
    nome: str,
    path: str,
    request=None,
) -> dict[str, object]:
    reference = build_storage_reference(
        path,
        request=request,
        missing_type="legado_sem_arquivo",
    )
    return {
        "id": f"pagamento-{pagamento.id}-{papel}",
        "nome": nome,
        "url": reference.url,
        "arquivo_referencia": reference.arquivo_referencia,
        "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
        "tipo_referencia": reference.tipo_referencia,
        "origem": "efetivacao_contrato",
        "papel": papel,
        "tipo": tipo,
        "status": pagamento.status,
        "competencia": None,
        "created_at": pagamento.paid_at or pagamento.updated_at or pagamento.created_at,
    }


def _payment_placeholder_entry(
    *,
    pagamento: Pagamento,
    papel: str,
    tipo: str,
    nome: str,
) -> dict[str, object]:
    if pagamento.paid_at:
        paid_at = timezone.localtime(pagamento.paid_at).strftime("%d/%m/%Y %H:%M")
        referencia = f"Pagamento recebido em {paid_at}"
    else:
        referencia = "Pagamento recebido"
    return {
        "id": f"pagamento-placeholder-{pagamento.id}-{papel}",
        "nome": nome,
        "url": "",
        "arquivo_referencia": referencia,
        "arquivo_disponivel_localmente": False,
        "tipo_referencia": "placeholder_recebido",
        "origem": "efetivacao_contrato",
        "papel": papel,
        "tipo": tipo,
        "status": pagamento.status,
        "competencia": None,
        "created_at": pagamento.paid_at or pagamento.updated_at or pagamento.created_at,
    }


def _contract_comprovantes(contrato: Contrato) -> Iterable[Comprovante]:
    related = getattr(contrato, "comprovantes", None)
    if related is not None:
        comprovantes = [
            comprovante
            for comprovante in related.all()
            if comprovante.refinanciamento_id is None
            and (
                comprovante.origem == Comprovante.Origem.EFETIVACAO_CONTRATO
                or (
                    comprovante.origem == Comprovante.Origem.LEGADO
                    and comprovante.tipo
                    in {
                        Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                        Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
                    }
                )
                or (
                    comprovante.ciclo_id is not None
                    and comprovante.papel == Comprovante.Papel.OPERACIONAL
                )
            )
        ]
    else:
        comprovantes = list(
            Comprovante.all_objects.filter(
                contrato=contrato,
                refinanciamento__isnull=True,
            )
            .filter(
                (
                    models.Q(
                        tipo__in=[
                            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
                        ],
                        origem__in=[
                            Comprovante.Origem.EFETIVACAO_CONTRATO,
                            Comprovante.Origem.LEGADO,
                        ],
                    )
                )
                | models.Q(
                    ciclo__isnull=False,
                    papel=Comprovante.Papel.OPERACIONAL,
                )
            )
            .select_related("enviado_por")
            .order_by("created_at", "id")
        )
    return comprovantes


def _candidate_refinanciamentos_for_payment(
    contrato: Contrato,
    *,
    pagamento: Pagamento | None,
) -> list[Refinanciamento]:
    related = getattr(contrato.associado, "refinanciamentos", None)
    if related is not None:
        refinanciamentos = [
            refinanciamento
            for refinanciamento in related.all()
            if refinanciamento.contrato_origem_id == contrato.id
            and refinanciamento.status
            in {
                Refinanciamento.Status.EFETIVADO,
                Refinanciamento.Status.CONCLUIDO,
                Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
            }
        ]
    else:
        refinanciamentos = list(
            Refinanciamento.all_objects.filter(
                associado=contrato.associado,
                contrato_origem=contrato,
                status__in=[
                    Refinanciamento.Status.EFETIVADO,
                    Refinanciamento.Status.CONCLUIDO,
                    Refinanciamento.Status.APROVADO_PARA_RENOVACAO,
                ],
            )
            .prefetch_related("comprovantes")
            .order_by("-executado_em", "-data_ativacao_ciclo", "-created_at", "-id")
        )

    def sort_key(refinanciamento: Refinanciamento):
        reference_at = (
            refinanciamento.executado_em
            or refinanciamento.data_ativacao_ciclo
            or refinanciamento.created_at
        )
        if pagamento is not None and pagamento.paid_at is not None and reference_at is not None:
            delta = abs((reference_at - pagamento.paid_at).total_seconds())
        else:
            delta = float("inf")
        return (
            delta,
            -(reference_at.timestamp() if reference_at is not None else 0),
            -refinanciamento.id,
        )

    return sorted(refinanciamentos, key=sort_key)


def _payment_refinanciamento_comprovantes(
    contrato: Contrato,
    *,
    pagamento: Pagamento | None,
) -> list[Comprovante]:
    for refinanciamento in _candidate_refinanciamentos_for_payment(
        contrato,
        pagamento=pagamento,
    ):
        comprovantes = [
            comprovante
            for comprovante in refinanciamento.comprovantes.all()
            if comprovante.tipo
            in {
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            }
        ]
        if comprovantes:
            comprovantes.sort(key=lambda item: (item.created_at, item.id))
            return comprovantes
    return []


def _comprovante_reference_timestamp(
    comprovante: Comprovante,
    pagamento: Pagamento | None,
):
    return (
        comprovante.data_pagamento
        or (pagamento.paid_at if pagamento is not None else None)
        or comprovante.created_at
    )


def build_initial_payment_evidences(
    contrato: Contrato,
    *,
    request=None,
) -> list[dict[str, object]]:
    pagamento = get_initial_payment_for_contract(contrato)
    expected_roles = {
        Comprovante.Papel.ASSOCIADO: (
            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
            "Comprovante associada",
        ),
        Comprovante.Papel.AGENTE: (
            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
            "Comprovante agente",
        ),
    }
    comprovantes = list(_contract_comprovantes(contrato))
    if not comprovantes:
        comprovantes = _payment_refinanciamento_comprovantes(
            contrato,
            pagamento=pagamento,
        )
    if comprovantes:
        evidence_rows: list[dict[str, object]] = []
        for comprovante in comprovantes:
            reference = build_filefield_reference(
                comprovante.arquivo,
                request=request,
                missing_type="legado_sem_arquivo",
            )
            origem = (
                "admin_editor"
                if comprovante.ciclo_id is not None
                and comprovante.papel == Comprovante.Papel.OPERACIONAL
                else (comprovante.origem or "efetivacao_contrato")
            )
            evidence_rows.append(
                {
                    "id": f"contrato-{comprovante.id}",
                    "nome": (
                        comprovante.nome_original
                        or comprovante.get_tipo_display()
                        or f"Comprovante {comprovante.get_papel_display()}"
                    ),
                    "url": reference.url,
                    "arquivo_referencia": comprovante.arquivo_referencia,
                    "arquivo_disponivel_localmente": reference.arquivo_disponivel_localmente,
                    "tipo_referencia": reference.tipo_referencia,
                    "origem": origem,
                    "papel": comprovante.papel,
                    "tipo": comprovante.tipo,
                    "status": (
                        pagamento.status
                        if pagamento
                        else Pagamento.Status.PAGO
                    ),
                    "competencia": None,
                    "created_at": _comprovante_reference_timestamp(
                        comprovante,
                        pagamento,
                    ),
                }
            )
        if pagamento and pagamento.status == Pagamento.Status.PAGO:
            present_roles = {str(item["papel"]) for item in evidence_rows}
            for papel, (tipo, nome) in expected_roles.items():
                if papel not in present_roles:
                    evidence_rows.append(
                        _payment_placeholder_entry(
                            pagamento=pagamento,
                            papel=papel,
                            tipo=tipo,
                            nome=nome,
                        )
                    )
        return evidence_rows

    if pagamento is None:
        return []

    evidence_rows = []
    present_roles: set[str] = set()
    if pagamento.comprovante_associado_path:
        evidence_rows.append(
            _payment_reference_entry(
                pagamento=pagamento,
                papel=Comprovante.Papel.ASSOCIADO,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                nome="Comprovante associada",
                path=pagamento.comprovante_associado_path,
                request=request,
            )
        )
        present_roles.add(Comprovante.Papel.ASSOCIADO)
    if pagamento.comprovante_agente_path:
        evidence_rows.append(
            _payment_reference_entry(
                pagamento=pagamento,
                papel=Comprovante.Papel.AGENTE,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
                nome="Comprovante agente",
                path=pagamento.comprovante_agente_path,
                request=request,
            )
        )
        present_roles.add(Comprovante.Papel.AGENTE)
    if evidence_rows:
        if pagamento.status == Pagamento.Status.PAGO:
            for papel, (tipo, nome) in expected_roles.items():
                if papel not in present_roles:
                    evidence_rows.append(
                        _payment_placeholder_entry(
                            pagamento=pagamento,
                            papel=papel,
                            tipo=tipo,
                            nome=nome,
                        )
                    )
        return evidence_rows

    if pagamento.status == Pagamento.Status.PAGO:
        return [
            _payment_placeholder_entry(
                pagamento=pagamento,
                papel=Comprovante.Papel.ASSOCIADO,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO,
                nome="Comprovante associada",
            ),
            _payment_placeholder_entry(
                pagamento=pagamento,
                papel=Comprovante.Papel.AGENTE,
                tipo=Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE,
                nome="Comprovante agente",
            ),
        ]
    return []


@dataclass(frozen=True)
class InitialPaymentPayload:
    status: str
    status_label: str
    valor: Decimal | None
    paid_at: object
    evidencia_status: str
    evidencias: list[dict[str, object]]


def build_initial_payment_payload(
    contrato: Contrato,
    *,
    request=None,
) -> InitialPaymentPayload:
    pagamento = get_initial_payment_for_contract(contrato)
    evidencias = build_initial_payment_evidences(contrato, request=request)
    evidencia_status = ""
    if evidencias:
        if any(bool(item["arquivo_disponivel_localmente"]) for item in evidencias):
            evidencia_status = "arquivo_local"
        elif any(item["tipo_referencia"] == "placeholder_recebido" for item in evidencias):
            evidencia_status = "placeholder_recebido"
        else:
            evidencia_status = "referencia_legado"
    paid_at = pagamento.paid_at if pagamento else None
    status = pagamento.status if pagamento else "sem_pagamento_inicial"
    status_label = _payment_status_label(pagamento)
    if pagamento is None and (evidencias or contrato.auxilio_liberado_em is not None):
        status = Pagamento.Status.PAGO
        status_label = Pagamento.Status.PAGO.label
        if evidencias:
            paid_at = next(
                (
                    item["created_at"]
                    for item in evidencias
                    if item.get("created_at") is not None
                ),
                None,
            )
        if paid_at is None and contrato.auxilio_liberado_em is not None:
            paid_at = timezone.make_aware(
                datetime.combine(
                    contrato.auxilio_liberado_em,
                    datetime.min.time(),
                )
            )
    return InitialPaymentPayload(
        status=status,
        status_label=status_label,
        valor=_payment_display_value(pagamento),
        paid_at=paid_at,
        evidencia_status=evidencia_status,
        evidencias=evidencias,
    )
