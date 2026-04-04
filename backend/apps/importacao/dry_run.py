"""Simulação read-only do arquivo retorno (dry-run).

Executa toda a lógica de reconciliação SEM escrever no banco, retornando
um dict estruturado com KPIs e items prontos para armazenar no JSONField
`dry_run_resultado` do modelo ArquivoRetorno.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from apps.associados.models import Associado, only_digits
from apps.contratos.competencia import resolve_processing_competencia_parcela
from apps.contratos.models import Ciclo, Parcela

from .matching import find_associado

VALORES_3050 = {Decimal("30.00"), Decimal("50.00")}
MENSALIDADE_MIN = Decimal("100.00")


def _parse_competencia(value: str) -> date:
    return datetime.strptime(value, "%m/%Y").date().replace(day=1)


def _to_decimal(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _categorizar_valor(valor) -> str:
    v = _to_decimal(valor)
    if v in VALORES_3050:
        return "valores_30_50"
    if v >= MENSALIDADE_MIN:
        return "mensalidades"
    return "outros"


def _determine_resultado(raw: dict, parcela: Parcela) -> str:
    cod = raw.get("status_codigo", "")
    valor = _to_decimal(raw.get("valor_descontado", "0"))

    if cod == "1":
        if parcela.status == Parcela.Status.LIQUIDADA:
            return "pendencia_manual"
        if valor != parcela.valor:
            return "pendencia_manual"
        return "baixa_efetuada"

    if cod == "4":
        # permitir_diferenca=True — divergência sinalizada mas efetivado
        return "baixa_efetuada"

    if cod in ("2", "3", "S"):
        return "nao_descontado"

    if cod in ("5", "6"):
        return "pendencia_manual"

    return "erro"


def _simular_apto_renovar(parcela: Parcela, resultado: str) -> bool:
    if resultado != "baixa_efetuada":
        return False

    ciclo = parcela.ciclo
    parcelas_ciclo = list(ciclo.parcelas.only("id", "status").all())
    total = len(parcelas_ciclo)
    if total == 0:
        return False

    threshold = max(total - 1, 1)
    pagas = sum(1 for p in parcelas_ciclo if p.status == Parcela.Status.DESCONTADO)

    # Simula: esta parcela seria DESCONTADA depois
    pagas_depois = pagas if parcela.status == Parcela.Status.DESCONTADO else pagas + 1
    return pagas_depois >= threshold


def _simular_status_associado(status_atual: str | None, resultado: str) -> str | None:
    if resultado == "nao_descontado":
        return Associado.Status.INADIMPLENTE
    return status_atual


def _simular_status_ciclo(status_atual: str | None, resultado: str, apto: bool) -> str | None:
    if resultado != "baixa_efetuada":
        return status_atual
    if apto:
        return Ciclo.Status.APTO_A_RENOVAR
    return status_atual


def _simular_item(raw: dict, competencia: date) -> dict:
    cpf = only_digits(raw.get("cpf_cnpj", ""))

    base = {
        "linha_numero": raw.get("linha_numero"),
        "cpf_cnpj": cpf,
        "nome_servidor": raw.get("nome_servidor", ""),
        "matricula_servidor": raw.get("matricula_servidor", ""),
        "orgao_pagto_nome": raw.get("orgao_pagto_nome", ""),
        "valor_descontado": str(_to_decimal(raw.get("valor_descontado", "0"))),
        "status_codigo": raw.get("status_codigo", ""),
        "categoria": _categorizar_valor(raw.get("valor_descontado")),
    }

    associado = find_associado(
        cpf=cpf,
        matricula=raw.get("matricula_servidor"),
        nome=raw.get("nome_servidor"),
        orgao=raw.get("orgao_pagto_nome"),
        orgao_alternativo=raw.get("orgao_pagto_codigo"),
        orgao_codigo=raw.get("orgao_codigo"),
    )

    if not associado:
        return {
            **base,
            "resultado": "nao_encontrado",
            "associado_id": None,
            "associado_nome": raw.get("nome_servidor", ""),
            "associado_status_antes": None,
            "associado_status_depois": Associado.Status.IMPORTADO,
            "ciclo_status_antes": None,
            "ciclo_status_depois": None,
            "ficara_apto_renovar": False,
        }

    parcela = resolve_processing_competencia_parcela(
        associado_id=associado.id,
        referencia_mes=competencia,
        for_update=False,
    )

    if not parcela:
        return {
            **base,
            "resultado": "ciclo_aberto",
            "associado_id": associado.id,
            "associado_nome": associado.nome_completo,
            "associado_status_antes": associado.status,
            "associado_status_depois": associado.status,
            "ciclo_status_antes": None,
            "ciclo_status_depois": None,
            "ficara_apto_renovar": False,
        }

    resultado = _determine_resultado(raw, parcela)
    apto = _simular_apto_renovar(parcela, resultado)
    assoc_depois = _simular_status_associado(associado.status, resultado)
    ciclo_antes = parcela.ciclo.status
    ciclo_depois = _simular_status_ciclo(ciclo_antes, resultado, apto)

    return {
        **base,
        "resultado": resultado,
        "associado_id": associado.id,
        "associado_nome": associado.nome_completo,
        "associado_status_antes": associado.status,
        "associado_status_depois": assoc_depois,
        "ciclo_status_antes": ciclo_antes,
        "ciclo_status_depois": ciclo_depois,
        "ficara_apto_renovar": apto,
    }


def _build_kpis(resultados: list[dict]) -> dict:
    total = len(resultados)
    baixa = [r for r in resultados if r["resultado"] == "baixa_efetuada"]
    nao_desc = [r for r in resultados if r["resultado"] == "nao_descontado"]
    nao_enc = [r for r in resultados if r["resultado"] == "nao_encontrado"]
    pendencia = [r for r in resultados if r["resultado"] == "pendencia_manual"]
    ciclo_aberto = [r for r in resultados if r["resultado"] == "ciclo_aberto"]
    aptos = [r for r in resultados if r["ficara_apto_renovar"]]

    valor_previsto = sum((_to_decimal(r["valor_descontado"]) for r in resultados), Decimal("0"))
    valor_real = sum((_to_decimal(r["valor_descontado"]) for r in baixa), Decimal("0"))

    v3050 = [r for r in resultados if r["categoria"] == "valores_30_50"]
    v3050_desc = [r for r in v3050 if r["resultado"] == "baixa_efetuada"]
    v3050_ndesc = [r for r in v3050 if r["resultado"] == "nao_descontado"]

    # Mudanças de status de associado
    mudancas_assoc: dict[tuple, int] = defaultdict(int)
    for r in resultados:
        antes = r.get("associado_status_antes")
        depois = r.get("associado_status_depois")
        if antes and depois and antes != depois:
            mudancas_assoc[(antes, depois)] += 1

    # Mudanças de status de ciclo
    mudancas_ciclo: dict[tuple, int] = defaultdict(int)
    for r in resultados:
        antes = r.get("ciclo_status_antes")
        depois = r.get("ciclo_status_depois")
        if antes and depois and antes != depois:
            mudancas_ciclo[(antes, depois)] += 1

    return {
        "total_no_arquivo": total,
        "atualizados": len(baixa) + len(nao_desc) + len(pendencia) + len(nao_enc),
        "baixa_efetuada": len(baixa),
        "nao_descontado": len(nao_desc),
        "nao_encontrado": len(nao_enc),
        "associados_importados": len(nao_enc),
        "pendencia_manual": len(pendencia),
        "ciclo_aberto": len(ciclo_aberto),
        "valor_previsto": str(valor_previsto),
        "valor_real": str(valor_real),
        "aptos_a_renovar": len(aptos),
        "valores_30_50": {
            "descontaram": {
                "count": len(v3050_desc),
                "valor_total": str(sum((_to_decimal(r["valor_descontado"]) for r in v3050_desc), Decimal("0"))),
            },
            "nao_descontaram": {
                "count": len(v3050_ndesc),
                "valor_total": str(sum((_to_decimal(r["valor_descontado"]) for r in v3050_ndesc), Decimal("0"))),
            },
        },
        "mudancas_status_associado": [
            {"antes": antes, "depois": depois, "count": count}
            for (antes, depois), count in sorted(mudancas_assoc.items())
        ],
        "mudancas_status_ciclo": [
            {"antes": antes, "depois": depois, "count": count}
            for (antes, depois), count in sorted(mudancas_ciclo.items())
        ],
    }


def simular_dry_run(competencia: date, parsed_items: list[dict]) -> dict:
    """Ponto de entrada principal.

    Recebe os items já parseados (sem deduplicação — chame _deduplicar antes),
    simula a reconciliação de forma read-only e retorna o dict com kpis + items.
    """
    resultados = [_simular_item(raw, competencia) for raw in parsed_items]
    return {
        "kpis": _build_kpis(resultados),
        "items": resultados,
    }
