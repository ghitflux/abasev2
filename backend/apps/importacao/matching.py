from __future__ import annotations

import re

from django.db.models import F, Q, Value
from django.db.models.functions import Replace, Upper

from apps.associados.models import Associado, only_digits


def normalize_matricula(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (value or "")).upper()


def _normalized_field(field_name: str):
    expression = F(field_name)
    for old in (".", "-", "/", " "):
        expression = Replace(expression, Value(old), Value(""))
    return Upper(expression)


def _build_orgao_candidates(orgao: str = "", *extras: str) -> list[str]:
    candidatos: list[str] = []
    for raw in (orgao, *extras):
        value = (raw or "").strip()
        if value and value not in candidatos:
            candidatos.append(value)
    return candidatos


def find_associado(
    *,
    cpf: str = "",
    matricula: str = "",
    nome: str = "",
    orgao: str = "",
    orgao_alternativo: str = "",
    orgao_codigo: str = "",
) -> Associado | None:
    """Replica a ordem de casamento do legado: CPF -> matrícula -> nome+órgão."""

    cpf_digits = only_digits(cpf)
    if cpf_digits:
        associado = Associado.objects.filter(cpf_cnpj=cpf_digits).first()
        if associado:
            return associado

    matricula_norm = normalize_matricula(matricula)
    if matricula_norm:
        associados = (
            Associado.objects.annotate(
                matricula_orgao_norm=_normalized_field("matricula_orgao"),
                matricula_norm=_normalized_field("matricula"),
            )
            .filter(
                Q(matricula_orgao_norm=matricula_norm)
                | Q(matricula_norm=matricula_norm)
            )
            .order_by("id")
        )
        associado = associados.first()
        if associado:
            return associado

        matricula_digits = only_digits(matricula)
        if matricula_digits:
            candidatos = list(
                Associado.objects.filter(
                    Q(matricula_orgao__icontains=matricula_digits)
                    | Q(matricula__icontains=matricula_digits)
                )[:2]
            )
            if len(candidatos) == 1:
                return candidatos[0]

    nome = (nome or "").strip()
    if nome:
        candidatos_orgao = _build_orgao_candidates(orgao, orgao_alternativo, orgao_codigo)
        for candidato_orgao in candidatos_orgao:
            candidatos = list(
                Associado.objects.filter(nome_completo__icontains=nome).filter(
                    orgao_publico__icontains=candidato_orgao
                )[:2]
            )
            if len(candidatos) == 1:
                return candidatos[0]

        candidatos = list(Associado.objects.filter(nome_completo__icontains=nome)[:2])
        if len(candidatos) == 1:
            return candidatos[0]

    return None
