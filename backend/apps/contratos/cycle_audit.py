from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from apps.associados.models import Associado

from .cycle_timeline import (
    get_contract_first_cycle_activation_info,
    get_destination_refinanciamento,
    get_first_cycle,
    get_refinanciamento_activation_info,
)


@dataclass(frozen=True)
class TimelineFinding:
    classification: str
    associado_id: int
    cpf_cnpj: str
    nome_associado: str
    contrato_id: int | None
    contrato_codigo: str
    ciclo_id: int | None
    ciclo_numero: int | None
    refinanciamento_id: int | None
    detail: str
    data_ativacao: str | None
    origem_data_ativacao: str
    ativacao_inferida: bool


def _serialize_dt(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _new_finding(
    *,
    classification: str,
    associado: Associado,
    contrato=None,
    ciclo=None,
    refinanciamento=None,
    detail: str,
    data_ativacao=None,
    origem_data_ativacao: str = "indisponivel",
    ativacao_inferida: bool = False,
) -> TimelineFinding:
    return TimelineFinding(
        classification=classification,
        associado_id=associado.id,
        cpf_cnpj=associado.cpf_cnpj,
        nome_associado=associado.nome_completo,
        contrato_id=getattr(contrato, "id", None),
        contrato_codigo=getattr(contrato, "codigo", ""),
        ciclo_id=getattr(ciclo, "id", None),
        ciclo_numero=getattr(ciclo, "numero", None),
        refinanciamento_id=getattr(refinanciamento, "id", None),
        detail=detail,
        data_ativacao=_serialize_dt(data_ativacao),
        origem_data_ativacao=origem_data_ativacao,
        ativacao_inferida=ativacao_inferida,
    )


def audit_associado_cycle_timeline(associado: Associado) -> dict[str, object]:
    contratos = list(associado.contratos.prefetch_related("ciclos__parcelas").order_by("created_at", "id"))
    refinanciamentos = list(
        associado.refinanciamentos.select_related(
            "contrato_origem",
            "ciclo_origem",
            "ciclo_destino",
        ).order_by("created_at", "id")
    )
    findings: list[TimelineFinding] = []
    contract_payloads: list[dict[str, object]] = []

    for contrato in contratos:
        ciclos = list(contrato.ciclos.order_by("numero").prefetch_related("parcelas"))
        first_cycle = get_first_cycle(contrato)
        first_activation = (
            get_contract_first_cycle_activation_info(contrato, allow_fallback=False)
            if first_cycle is not None
            else None
        )
        if (
            first_cycle is not None
            and first_cycle.status != first_cycle.Status.FUTURO
            and first_activation is not None
            and first_activation.activated_at is None
        ):
            findings.append(
                _new_finding(
                    classification="dados_insuficientes_para_ativacao",
                    associado=associado,
                    contrato=contrato,
                    ciclo=first_cycle,
                    detail="Ciclo 1 sem pagamento de tesouraria coerente para ativação.",
                )
            )

        contract_payloads.append(
            {
                "contrato_id": contrato.id,
                "contrato_codigo": contrato.codigo,
                "primeiro_ciclo_id": first_cycle.id if first_cycle else None,
                "primeiro_ciclo_ativado_em": _serialize_dt(
                    first_activation.activated_at if first_activation else None
                ),
                "primeiro_ciclo_origem": first_activation.source if first_activation else "indisponivel",
                "ciclos": [
                    {
                        "ciclo_id": ciclo.id,
                        "numero": ciclo.numero,
                        "status": ciclo.status,
                    }
                    for ciclo in ciclos
                ],
            }
        )

        for ciclo in ciclos:
            if ciclo.numero <= 1:
                continue
            refinanciamento = get_destination_refinanciamento(ciclo)
            if refinanciamento is None:
                findings.append(
                    _new_finding(
                        classification="ciclo_extra_inconsistente",
                        associado=associado,
                        contrato=contrato,
                        ciclo=ciclo,
                        detail="Ciclo > 1 materializado sem vínculo de refinanciamento.",
                    )
                )
                continue

            activation = get_refinanciamento_activation_info(refinanciamento)
            if refinanciamento.executado_em is None and activation.activated_at is not None:
                findings.append(
                    _new_finding(
                        classification="ativacao_inferida_tesouraria",
                        associado=associado,
                        contrato=contrato,
                        ciclo=ciclo,
                        refinanciamento=refinanciamento,
                        detail="Ciclo ativado por inferência do pagamento da tesouraria.",
                        data_ativacao=activation.activated_at,
                        origem_data_ativacao=activation.source,
                        ativacao_inferida=activation.inferred,
                    )
                )
            if refinanciamento.executado_em is None and ciclo.status != ciclo.Status.FUTURO:
                findings.append(
                    _new_finding(
                        classification="ciclo_ativado_antes_da_efetivacao",
                        associado=associado,
                        contrato=contrato,
                        ciclo=ciclo,
                        refinanciamento=refinanciamento,
                        detail="Ciclo destino não está em previsão apesar de faltar efetivação.",
                        data_ativacao=activation.activated_at,
                        origem_data_ativacao=activation.source,
                        ativacao_inferida=activation.inferred,
                    )
                )

    for refinanciamento in refinanciamentos:
        activation = get_refinanciamento_activation_info(refinanciamento)
        if refinanciamento.ciclo_destino_id is None:
            findings.append(
                _new_finding(
                    classification="ciclo_futuro_ausente",
                    associado=associado,
                    contrato=refinanciamento.contrato_origem,
                    refinanciamento=refinanciamento,
                    detail="Refinanciamento sem ciclo futuro materializado.",
                    data_ativacao=activation.activated_at,
                    origem_data_ativacao=activation.source,
                    ativacao_inferida=activation.inferred,
                )
            )
            if activation.activated_at is not None:
                findings.append(
                    _new_finding(
                        classification="ativacao_inferida_tesouraria",
                        associado=associado,
                        contrato=refinanciamento.contrato_origem,
                        refinanciamento=refinanciamento,
                        detail="Refinanciamento sem executado_em, mas com ativação inferida pela tesouraria.",
                        data_ativacao=activation.activated_at,
                        origem_data_ativacao=activation.source,
                        ativacao_inferida=activation.inferred,
                    )
                )

    classifications = sorted({finding.classification for finding in findings})
    if not classifications:
        classifications = ["ok"]

    return {
        "associado_id": associado.id,
        "cpf_cnpj": associado.cpf_cnpj,
        "nome_associado": associado.nome_completo,
        "classifications": classifications,
        "contratos": contract_payloads,
        "findings": [asdict(finding) for finding in findings],
    }


def build_cycle_timeline_audit(*, cpf: str | None = None) -> dict[str, object]:
    queryset = Associado.objects.prefetch_related(
        "tesouraria_pagamentos",
        "contratos__ciclos__parcelas",
        "refinanciamentos__ciclo_destino",
        "refinanciamentos__contrato_origem",
    ).order_by("nome_completo", "id")
    if cpf:
        queryset = queryset.filter(cpf_cnpj=cpf)

    associados = [audit_associado_cycle_timeline(associado) for associado in queryset]
    counter: Counter[str] = Counter()
    with_findings = 0
    for associado in associados:
        classes = associado["classifications"]
        if classes != ["ok"]:
            with_findings += 1
        for classification in classes:
            counter[classification] += 1

    return {
        "summary": {
            "total_associados": len(associados),
            "associados_com_achados": with_findings,
            "classifications": dict(counter),
        },
        "associados": associados,
    }


def write_cycle_timeline_audit_json(report: dict[str, object], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target


def write_cycle_timeline_audit_csv(report: dict[str, object], output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        finding
        for associado in report["associados"]
        for finding in associado["findings"]
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "classification",
                "associado_id",
                "cpf_cnpj",
                "nome_associado",
                "contrato_id",
                "contrato_codigo",
                "ciclo_id",
                "ciclo_numero",
                "refinanciamento_id",
                "detail",
                "data_ativacao",
                "origem_data_ativacao",
                "ativacao_inferida",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return target
