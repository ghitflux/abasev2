from __future__ import annotations

import re
import unicodedata

from apps.accounts.backends import LEGACY_ROLE_CODE_MAP
from apps.associados.models import Documento


LEGACY_DOCUMENT_TYPE_MAP = {
    "cpf": Documento.Tipo.CPF,
    "cpf_frente": Documento.Tipo.DOCUMENTO_FRENTE,
    "cpf_verso": Documento.Tipo.DOCUMENTO_VERSO,
    "rg": Documento.Tipo.RG,
    "rg_frente": Documento.Tipo.DOCUMENTO_FRENTE,
    "rg_verso": Documento.Tipo.DOCUMENTO_VERSO,
    "comp_endereco": Documento.Tipo.COMPROVANTE_RESIDENCIA,
    "comp_renda": Documento.Tipo.OUTRO,
    "contracheque": Documento.Tipo.CONTRACHEQUE,
    "contracheque_atual": Documento.Tipo.CONTRACHEQUE,
    "termo_adesao": Documento.Tipo.TERMO_ADESAO,
    "termo_antecipacao": Documento.Tipo.TERMO_ANTECIPACAO,
}


def normalize_lookup_value(raw: str) -> str:
    normalized = unicodedata.normalize("NFKD", raw or "")
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    collapsed = re.sub(r"\s+", " ", ascii_only).strip().casefold()
    return collapsed


def lookup_aliases(raw: str) -> list[str]:
    normalized = normalize_lookup_value(raw)
    if not normalized:
        return []

    aliases = [normalized]
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    if compact and compact != normalized:
        aliases.append(compact)

    if "@" in normalized:
        local_part = normalized.split("@", 1)[0].strip()
        if local_part and local_part not in aliases:
            aliases.append(local_part)
        compact_local = re.sub(r"[^a-z0-9]+", "", local_part)
        if compact_local and compact_local not in aliases:
            aliases.append(compact_local)

    return aliases


def first_lookup_token(raw: str) -> str:
    normalized = normalize_lookup_value(raw)
    if not normalized:
        return ""
    return normalized.split(" ", 1)[0]


def map_legacy_role_code(raw: str) -> str | None:
    normalized = normalize_lookup_value(raw)
    return LEGACY_ROLE_CODE_MAP.get(normalized)


def map_estado_civil(raw: str) -> str:
    mapping = {
        "casado": "casado",
        "casado(a)": "casado",
        "solteiro": "solteiro",
        "solteiro(a)": "solteiro",
        "divorciado": "divorciado",
        "divorciado(a)": "divorciado",
        "viúvo": "viuvo",
        "viuvo": "viuvo",
        "viúvo(a)": "viuvo",
        "viuvo(a)": "viuvo",
        "união estável": "uniao_estavel",
    }
    return mapping.get(raw.lower(), "")


def map_contrato_status(raw: str) -> str:
    mapping = {
        "concluído": "ativo",
        "concluido": "ativo",
        "ativo": "ativo",
        "pendente": "em_analise",
        "cancelado": "cancelado",
        "encerrado": "encerrado",
    }
    return mapping.get(raw.lower(), "em_analise")


def map_refi_status(raw: str) -> str:
    mapping = {
        "done": "concluido",
        "enabled": "pendente_apto",
        "pending": "pendente_apto",
        "in_progress": "em_analise",
        "suspended": "bloqueado",
        "approved": "aprovado",
        "rejected": "rejeitado",
        "cancelled": "revertido",
    }
    return mapping.get(raw.lower(), "pendente_apto")


def map_legacy_document_type(raw: str) -> str:
    return LEGACY_DOCUMENT_TYPE_MAP.get(
        normalize_lookup_value(raw),
        Documento.Tipo.OUTRO,
    )


def build_legacy_document_path(item: dict[str, object]) -> str:
    relative_path = str(item.get("relative_path") or "").strip()
    if relative_path:
        return relative_path[:100]
    stored_name = str(item.get("stored_name") or "").strip()
    if not stored_name:
        return ""
    return f"documentos/legacy/{stored_name}"[:100]
