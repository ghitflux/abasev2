from __future__ import annotations

import json
import mimetypes
import os
import secrets
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Prefetch, Q
from django.utils import timezone

from apps.accounts.mobile_legacy_auth import ensure_self_service_roles, resolve_associado_for_user
from apps.contratos.cycle_projection import get_associado_visual_status_payload
from apps.contratos.models import Contrato, Parcela
from apps.esteira.models import DocIssue, DocReupload
from apps.importacao.models import PagamentoMensalidade
from core.file_references import build_storage_reference

from .models import Associado, Auxilio2Filiacao, Documento

WHATSAPP_GERAL = os.getenv("ABASE_HOME_WHATSAPP_GERAL", "").strip() or None
WHATSAPP_JURIDICO = os.getenv("ABASE_HOME_WHATSAPP_JURIDICO", "").strip() or None
STATIC_AUXILIO2_PIX = os.getenv("ABASE_MOBILE_AUXILIO2_PIX_COPIA_COLA", "").strip()
STATIC_AUXILIO2_QR = os.getenv("ABASE_MOBILE_AUXILIO2_QR_IMAGE", "").strip()

ISSUE_STATUS_MAP = {
    DocIssue.Status.INCOMPLETO: "waiting_user",
    DocIssue.Status.RESOLVIDO: "closed",
}
DOC_FIELD_MAP = {
    "cpf": "doc_front",
    "cpf_frente": "doc_front",
    "documento_frente": "doc_front",
    "rg": "doc_front",
    "rg_frente": "doc_front",
    "cpf_verso": "doc_back",
    "documento_verso": "doc_back",
    "rg_verso": "doc_back",
    "comp_endereco": "comprovante_endereco",
    "comprovante_endereco": "comprovante_endereco",
    "comprovante_residencia": "comprovante_endereco",
    "contracheque": "contracheque_atual",
    "contracheque_atual": "contracheque_atual",
    "simulacao": "simulacao",
    "termo_adesao": "termo_adesao",
    "termo_antecipacao": "termo_antecipacao",
}
PARCELA_STATUS_CODE_MAP = {
    Parcela.Status.DESCONTADO: "1",
    Parcela.Status.NAO_DESCONTADO: "2",
    Parcela.Status.EM_ABERTO: "0",
    Parcela.Status.EM_PREVISAO: "0",
    Parcela.Status.FUTURO: "0",
}


def parse_jsonish(value):
    current = value
    for _ in range(3):
        if isinstance(current, str):
            stripped = current.strip()
            if not stripped:
                return None
            try:
                current = json.loads(stripped)
                continue
            except json.JSONDecodeError:
                return current
        break
    return current


def decimal_to_number(value):
    if value in (None, ""):
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def format_date_iso(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def only_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def normalize_status(value: str | None) -> str:
    return (value or "").strip().lower()


def absolute_media_url(request, relative_path: str | None) -> str | None:
    reference = build_storage_reference(relative_path, request=request)
    return reference.url or None


def resolve_mobile_associado(user) -> Associado | None:
    associado = resolve_associado_for_user(user)
    if associado is None:
        return None
    ensure_self_service_roles(user)
    if not associado.user_id:
        associado.user = user
        associado.save(update_fields=["user", "updated_at"])
    return associado


def _active_contratos_qs(associado: Associado):
    return (
        associado.contratos.exclude(status=Contrato.Status.CANCELADO)
        .prefetch_related(
            Prefetch(
                "ciclos__parcelas",
                queryset=Parcela.objects.exclude(status=Parcela.Status.CANCELADO).order_by("referencia_mes"),
            )
        )
        .order_by("-data_aprovacao", "-created_at")
    )


def get_latest_contrato(associado: Associado) -> Contrato | None:
    return _active_contratos_qs(associado).first()


def get_contrato_status_label(associado: Associado, contrato: Contrato | None) -> str:
    if associado.status == Associado.Status.INADIMPLENTE:
        return "Inadimplente"
    if contrato is None:
        return "Sem contrato"
    mapping = {
        Contrato.Status.ATIVO: "Concluído",
        Contrato.Status.EM_ANALISE: "Em análise",
        Contrato.Status.RASCUNHO: "Pendente",
        Contrato.Status.ENCERRADO: "Encerrado",
        Contrato.Status.CANCELADO: "Cancelado",
    }
    return mapping.get(contrato.status, "Pendente")


def build_pessoa_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {
            "nome_razao_social": "",
            "documento": "",
            "email": "",
            "celular": "",
            "orgao_publico": "",
            "cidade": "",
            "uf": "",
        }
    return {
        "nome_razao_social": associado.nome_completo or "",
        "documento": associado.cpf_cnpj or "",
        "email": associado.email or "",
        "celular": associado.telefone or "",
        "orgao_publico": associado.orgao_publico or "",
        "cidade": associado.cidade or "",
        "uf": associado.uf or "",
    }


def build_vinculo_publico_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {
            "orgao_publico": "",
            "situacao_servidor": "",
            "matricula": "",
        }
    return {
        "orgao_publico": associado.orgao_publico or "",
        "situacao_servidor": associado.situacao_servidor or "",
        "matricula": associado.matricula_display or "",
    }


def build_dados_bancarios_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {
            "banco": "",
            "agencia": "",
            "conta": "",
            "tipo_conta": "",
            "chave_pix": "",
        }
    payload = associado.build_dados_bancarios_payload() or {}
    return {
        "banco": payload.get("banco") or "",
        "agencia": payload.get("agencia") or "",
        "conta": payload.get("conta") or "",
        "tipo_conta": payload.get("tipo_conta") or "",
        "chave_pix": payload.get("chave_pix") or "",
    }


def get_document_snapshot_items(associado: Associado) -> list[dict[str, object]]:
    raw = parse_jsonish(associado.documents_json)
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        return [
            {
                "field": key,
                "relative_path": value,
                "stored_name": os.path.basename(str(value or "")),
            }
            for key, value in raw.items()
        ]
    return []


def _guess_file_size(path: str | None) -> int:
    if not path:
        return 0
    normalized = str(path).lstrip("/")
    try:
        return int(default_storage.size(normalized))
    except Exception:
        return 0


def _term_document_payload(associado: Associado, *, tipo: str, request) -> dict[str, object] | None:
    documento = (
        associado.documentos.filter(tipo=tipo)
        .order_by("-created_at")
        .first()
    )
    if documento is not None:
        reference = build_storage_reference(documento.arquivo_referencia, request=request)
        fallback_url = ""
        if not reference.url:
            try:
                fallback_url = documento.arquivo.url
                if request and fallback_url and not fallback_url.startswith(("http://", "https://")):
                    fallback_url = request.build_absolute_uri(fallback_url)
            except Exception:
                fallback_url = ""
        mime, _ = mimetypes.guess_type(documento.arquivo_referencia or "")
        return {
            "name": documento.nome_original or os.path.basename(documento.arquivo_referencia or "") or f"{tipo}.pdf",
            "mime": mime or "application/pdf",
            "size_bytes": _guess_file_size(documento.arquivo_referencia),
            "uploaded_at": format_date_iso(documento.created_at),
            "relative_path": documento.arquivo_referencia or "",
            "url": reference.url or fallback_url or None,
            "origin": "inicial" if documento.origem == Documento.Origem.OPERACIONAL else "reupload",
        }

    path_field = (
        associado.termo_adesao_admin_path
        if tipo == Documento.Tipo.TERMO_ADESAO
        else associado.termo_antecipacao_admin_path
    )
    if path_field:
        mime, _ = mimetypes.guess_type(path_field)
        return {
            "name": os.path.basename(path_field) or f"{tipo}.pdf",
            "mime": mime or "application/pdf",
            "size_bytes": _guess_file_size(path_field),
            "uploaded_at": format_date_iso(associado.updated_at),
            "relative_path": path_field,
            "url": absolute_media_url(request, path_field),
            "origin": "inicial",
        }

    for item in get_document_snapshot_items(associado):
        field = str(item.get("field") or item.get("tipo") or "").strip().lower()
        if field != tipo:
            continue
        relative_path = str(item.get("relative_path") or item.get("arquivo") or "")
        mime, _ = mimetypes.guess_type(relative_path)
        return {
            "name": str(item.get("original_name") or item.get("stored_name") or os.path.basename(relative_path) or f"{tipo}.pdf"),
            "mime": mime or str(item.get("mime") or "application/pdf"),
            "size_bytes": int(item.get("size_bytes") or 0),
            "uploaded_at": format_date_iso(item.get("uploaded_at")),
            "relative_path": relative_path or None,
            "url": absolute_media_url(request, relative_path),
            "origin": "inicial",
        }

    return None


def build_termo_adesao_payload(associado: Associado | None, *, request) -> dict[str, object] | None:
    if associado is None:
        return None
    return _term_document_payload(associado, tipo=Documento.Tipo.TERMO_ADESAO, request=request)


def build_termo_antecipacao_payload(associado: Associado | None, *, request) -> dict[str, object] | None:
    if associado is None:
        return None
    return _term_document_payload(associado, tipo=Documento.Tipo.TERMO_ANTECIPACAO, request=request)


def _collect_parcelas(contrato: Contrato) -> list[Parcela]:
    parcelas: list[Parcela] = []
    ciclos_cache = getattr(contrato, "_prefetched_objects_cache", {}).get("ciclos")
    ciclos = ciclos_cache or contrato.ciclos.all()
    for ciclo in ciclos:
        parcelas_cache = getattr(ciclo, "_prefetched_objects_cache", {}).get("parcelas")
        parcelas.extend(parcelas_cache or ciclo.parcelas.exclude(status=Parcela.Status.CANCELADO).all())
    return sorted(parcelas, key=lambda item: (item.referencia_mes, item.numero))


def build_contratos_payload(associado: Associado | None) -> list[dict[str, object]]:
    if associado is None:
        return []
    contratos = list(_active_contratos_qs(associado))
    if not contratos and associado.contrato_codigo_contrato:
        return [
            {
                "codigo": associado.contrato_codigo_contrato or None,
                "status_contrato": associado.contrato_status_contrato or "Pendente",
                "prazo": int(associado.contrato_prazo_meses or 0),
                "parcela_valor": decimal_to_number(associado.contrato_mensalidade),
                "mensalidade": decimal_to_number(associado.contrato_mensalidade),
                "total_financiado": decimal_to_number(associado.contrato_valor_antecipacao),
                "data_aprovacao": format_date_iso(associado.contrato_data_aprovacao),
            }
        ]

    return [
        {
            "codigo": contrato.codigo or None,
            "status_contrato": get_contrato_status_label(associado, contrato),
            "prazo": int(contrato.prazo_meses or 0),
            "parcela_valor": decimal_to_number(contrato.valor_mensalidade),
            "mensalidade": decimal_to_number(contrato.valor_mensalidade),
            "total_financiado": decimal_to_number(contrato.valor_total_antecipacao),
            "data_aprovacao": format_date_iso(contrato.data_aprovacao),
        }
        for contrato in contratos
    ]


def build_resumo_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {
            "prazo": 0,
            "parcela_valor": 0,
            "total_financiado": 0,
            "status_contrato": "Sem contrato",
            "parcelas_pagas": 0,
            "parcelas_restantes": 0,
            "atraso": 0,
            "abertas_total": 0,
            "total_pago": 0,
            "restante": 0,
            "percentual_pago": 0,
            "elegivel_antecipacao": False,
            "mensalidade": 0,
        }

    contrato = get_latest_contrato(associado)
    if contrato is None:
        prazo = int(associado.contrato_prazo_meses or 0)
        pagas = 0
        parcela_valor = decimal_to_number(associado.contrato_mensalidade)
        total_financiado = decimal_to_number(associado.contrato_valor_antecipacao)
        percentual = round((pagas / prazo) * 100, 2) if prazo else 0
        total_pago = round(parcela_valor * pagas, 2) if isinstance(parcela_valor, (int, float)) else 0
        return {
            "prazo": prazo,
            "parcela_valor": parcela_valor,
            "total_financiado": total_financiado,
            "status_contrato": associado.contrato_status_contrato or "Sem contrato",
            "parcelas_pagas": pagas,
            "parcelas_restantes": max(prazo - pagas, 0),
            "atraso": 0,
            "abertas_total": max(prazo - pagas, 0),
            "total_pago": total_pago,
            "restante": max((total_financiado or 0) - total_pago, 0),
            "percentual_pago": percentual,
            "elegivel_antecipacao": pagas >= 1,
            "mensalidade": parcela_valor,
        }

    parcelas = _collect_parcelas(contrato)
    paid_count = sum(1 for parcela in parcelas if parcela.status == Parcela.Status.DESCONTADO)
    overdue_count = sum(
        1
        for parcela in parcelas
        if parcela.status in {Parcela.Status.EM_ABERTO, Parcela.Status.NAO_DESCONTADO}
        and parcela.data_vencimento < timezone.localdate()
    )
    prazo = int(contrato.prazo_meses or len(parcelas) or 0)
    parcelas_total = len(parcelas) or prazo
    parcelas_restantes = max(parcelas_total - paid_count, 0)
    parcela_valor = float(contrato.valor_mensalidade or 0)
    total_financiado = float(contrato.valor_total_antecipacao or 0)
    total_pago = round(parcela_valor * paid_count, 2)
    percentual = round((paid_count / parcelas_total) * 100, 2) if parcelas_total else 0

    return {
        "prazo": prazo,
        "parcela_valor": parcela_valor,
        "total_financiado": total_financiado,
        "status_contrato": get_contrato_status_label(associado, contrato),
        "parcelas_pagas": paid_count,
        "parcelas_restantes": parcelas_restantes,
        "atraso": overdue_count,
        "abertas_total": parcelas_restantes,
        "total_pago": total_pago,
        "restante": max(total_financiado - total_pago, 0),
        "percentual_pago": percentual,
        "elegivel_antecipacao": paid_count >= 1,
        "mensalidade": parcela_valor,
    }


def build_cadastro_payload(associado: Associado | None, *, request) -> dict[str, object] | None:
    if associado is None:
        return None

    termo_adesao = build_termo_adesao_payload(associado, request=request)
    termo_antecipacao = build_termo_antecipacao_payload(associado, request=request)

    return {
        "id": associado.id,
        "user_id": associado.user_id,
        "doc_type": associado.tipo_documento,
        "cpf_cnpj": associado.cpf_cnpj,
        "rg": associado.rg,
        "orgao_expedidor": associado.orgao_expedidor,
        "full_name": associado.nome_completo,
        "birth_date": format_date_iso(associado.data_nascimento),
        "profession": associado.profissao,
        "profissao": associado.profissao,
        "cargo": associado.cargo,
        "marital_status": associado.estado_civil.upper() if associado.estado_civil else "",
        "estado_civil": associado.estado_civil.upper() if associado.estado_civil else "",
        "cep": associado.cep,
        "address": associado.logradouro,
        "logradouro": associado.logradouro,
        "address_number": associado.numero,
        "numero": associado.numero,
        "complement": associado.complemento,
        "complemento": associado.complemento,
        "neighborhood": associado.bairro,
        "bairro": associado.bairro,
        "city": associado.cidade,
        "cidade": associado.cidade,
        "uf": associado.uf,
        "cellphone": associado.telefone,
        "orgao_publico": associado.orgao_publico,
        "situacao_servidor": associado.situacao_servidor,
        "matricula_servidor_publico": associado.matricula_orgao,
        "matricula_orgao": associado.matricula_orgao,
        "email": associado.email,
        "bank_name": associado.banco,
        "banco": associado.banco,
        "bank_agency": associado.agencia,
        "agencia": associado.agencia,
        "bank_account": associado.conta,
        "conta": associado.conta,
        "account_type": associado.tipo_conta,
        "tipo_conta": associado.tipo_conta,
        "pix_key": associado.chave_pix,
        "chave_pix": associado.chave_pix,
        "contrato_mensalidade": decimal_to_number(associado.contrato_mensalidade),
        "contrato_prazo_meses": int(associado.contrato_prazo_meses or 0),
        "contrato_taxa_antecipacao": decimal_to_number(associado.contrato_taxa_antecipacao),
        "contrato_margem_disponivel": decimal_to_number(associado.contrato_margem_disponivel),
        "contrato_data_aprovacao": format_date_iso(associado.contrato_data_aprovacao),
        "contrato_data_envio_primeira": format_date_iso(associado.contrato_data_envio_primeira),
        "contrato_valor_antecipacao": decimal_to_number(associado.contrato_valor_antecipacao),
        "contrato_status_contrato": associado.contrato_status_contrato,
        "contrato_mes_averbacao": format_date_iso(associado.contrato_mes_averbacao),
        "contrato_codigo_contrato": associado.contrato_codigo_contrato,
        "contrato_doacao_associado": decimal_to_number(associado.contrato_doacao_associado),
        "aceite_termos": bool(associado.aceite_termos),
        "termo_adesao_admin_path": (
            termo_adesao.get("relative_path") if termo_adesao else associado.termo_adesao_admin_path
        ),
        "termo_antecipacao_admin_path": (
            termo_antecipacao.get("relative_path") if termo_antecipacao else associado.termo_antecipacao_admin_path
        ),
        "termo_adesao_admin_url": termo_adesao.get("url") if termo_adesao else None,
        "termo_antecipacao_admin_url": termo_antecipacao.get("url") if termo_antecipacao else None,
        "contato_status": associado.contato_status,
        "contato_updated_at": format_date_iso(associado.contato_updated_at),
        "auxilio1_status": associado.auxilio1_status or associado.auxilio_status,
        "auxilio1_updated_at": format_date_iso(associado.auxilio1_updated_at or associado.updated_at),
        "auxilio2_status": associado.auxilio2_status,
        "auxilio2_updated_at": format_date_iso(associado.auxilio2_updated_at),
        "calc_valor_bruto": decimal_to_number(associado.calc_valor_bruto),
        "calc_liquido_cc": decimal_to_number(associado.calc_liquido_cc),
        "calc_prazo_antecipacao": int(associado.calc_prazo_antecipacao or 0),
        "calc_mensalidade_associativa": decimal_to_number(associado.calc_mensalidade_associativa),
        "anticipations_json": parse_jsonish(associado.anticipations_json),
        "documents_json": parse_jsonish(associado.documents_json),
        "agente_responsavel": associado.agente_responsavel.full_name if associado.agente_responsavel else "",
        "agente_filial": associado.agente_filial,
        "observacoes": associado.observacao,
        "created_at": format_date_iso(associado.created_at),
        "updated_at": format_date_iso(associado.updated_at),
    }


def is_basic_complete(associado: Associado | None) -> bool:
    if associado is None:
        return False
    required_values = [
        associado.cpf_cnpj,
        associado.nome_completo,
        associado.data_nascimento,
        associado.cep,
        associado.logradouro,
        associado.cidade,
        associado.uf,
        associado.telefone,
        associado.orgao_publico,
        associado.email,
    ]
    return all(value not in (None, "") for value in required_values)


def _allowed_by_status(value: str | None) -> bool:
    normalized = normalize_status(value)
    return normalized in {
        "liberado",
        "aceito",
        "aceita",
        "autorizado",
        "autorizada",
        "pendente",
        "pago",
    }


def get_status_label(associado: Associado | None) -> str:
    if associado is None:
        return "Sem contrato"
    visual = get_associado_visual_status_payload(associado)
    visual_label = str(visual.get("status_visual_label") or "").strip()
    if associado.status == Associado.Status.ATIVO:
        return "Aprovado"
    if associado.status == Associado.Status.INATIVO:
        return "Reprovado"
    if visual_label:
        return visual_label
    mapping = {
        Associado.Status.CADASTRADO: "Pendente",
        Associado.Status.IMPORTADO: "Importado",
        Associado.Status.EM_ANALISE: "Em análise",
        Associado.Status.PENDENTE: "Pendente",
        Associado.Status.INADIMPLENTE: "Em atraso",
    }
    return mapping.get(associado.status, "Pendente")


def build_status_payload(associado: Associado | None, *, request) -> dict[str, object]:
    cadastro = build_cadastro_payload(associado, request=request)
    basic_complete = is_basic_complete(associado)
    aux1_status = (cadastro or {}).get("auxilio1_status") if cadastro else "bloqueado"
    aux2_status = (cadastro or {}).get("auxilio2_status") if cadastro else "bloqueado"
    termo_adesao = build_termo_adesao_payload(associado, request=request)
    termo_antecipacao = build_termo_antecipacao_payload(associado, request=request)
    latest_charge = get_latest_auxilio2_charge(associado.user if associado and associado.user_id else None, associado=associado)

    return {
        "exists": associado is not None,
        "status": get_status_label(associado),
        "basic_complete": basic_complete,
        "complete": basic_complete,
        "cadastro": cadastro,
        "permissions": {
            "auxilio1": _allowed_by_status(aux1_status),
            "auxilio2": _allowed_by_status(aux2_status) or latest_charge is not None,
        },
        "auxilios": {
            "auxilio1": {
                "allowed": _allowed_by_status(aux1_status),
                "status": aux1_status or "bloqueado",
            },
            "auxilio2": {
                "allowed": _allowed_by_status(aux2_status) or latest_charge is not None,
                "status": (
                    latest_charge.status if latest_charge is not None else (aux2_status or "bloqueado")
                ),
            },
        },
        "aceite_termos": bool(associado and associado.aceite_termos),
        "termo_adesao": termo_adesao,
        "auxilio1_status": aux1_status,
        "auxilio1_updated_at": (cadastro or {}).get("auxilio1_updated_at") if cadastro else None,
        "auxilio2_status": aux2_status,
        "auxilio2_updated_at": (cadastro or {}).get("auxilio2_updated_at") if cadastro else None,
        "termos": {
            "adesao_admin_url": termo_adesao.get("url") if termo_adesao else None,
            "antecipacao_admin_url": termo_antecipacao.get("url") if termo_antecipacao else None,
            "adesao_user_uploaded": bool(termo_adesao),
            "antecipacao_user_uploaded": bool(termo_antecipacao),
        },
    }


def build_bootstrap_payload(associado: Associado | None, *, request) -> dict[str, object]:
    cadastro = build_cadastro_payload(associado, request=request)
    resumo = build_resumo_payload(associado)
    return {
        "pessoa": build_pessoa_payload(associado),
        "vinculo_publico": build_vinculo_publico_payload(associado),
        "dados_bancarios": build_dados_bancarios_payload(associado),
        "contratos": build_contratos_payload(associado),
        "resumo": resumo,
        "termo_adesao": build_termo_adesao_payload(associado, request=request),
        "aceite_termos": bool(associado and associado.aceite_termos),
        "contrato_mensalidade": (cadastro or {}).get("contrato_mensalidade"),
        "cadastro": None
        if cadastro is None
        else {
            "contrato_mensalidade": cadastro.get("contrato_mensalidade"),
            "auxilio1_status": cadastro.get("auxilio1_status"),
            "auxilio1_updated_at": cadastro.get("auxilio1_updated_at"),
            "auxilio2_status": cadastro.get("auxilio2_status"),
            "auxilio2_updated_at": cadastro.get("auxilio2_updated_at"),
        },
        "auxilio1_status": (cadastro or {}).get("auxilio1_status"),
        "auxilio1_updated_at": (cadastro or {}).get("auxilio1_updated_at"),
        "auxilio2_status": (cadastro or {}).get("auxilio2_status"),
        "auxilio2_updated_at": (cadastro or {}).get("auxilio2_updated_at"),
        "whatsapps": {
            "geral": WHATSAPP_GERAL,
            "juridico": WHATSAPP_JURIDICO,
        },
    }


def build_me_payload(user, associado: Associado | None, *, request) -> dict[str, object]:
    roles = ensure_self_service_roles(user, include_legacy_alias=associado is not None)
    return {
        "ok": True,
        "user": {
            "id": user.id,
            "name": user.full_name or user.email,
            "email": user.email,
        },
        "roles": roles,
        "agente": (
            {
                "id": associado.agente_responsavel_id,
                "name": associado.agente_responsavel.full_name,
            }
            if associado and associado.agente_responsavel_id
            else None
        ),
        "pessoa": build_pessoa_payload(associado),
        "vinculo_publico": build_vinculo_publico_payload(associado),
        "dados_bancarios": build_dados_bancarios_payload(associado),
        "termo_adesao": build_termo_adesao_payload(associado, request=request),
    }


def _required_docs_from_issue(issue: DocIssue) -> list[str]:
    raw = parse_jsonish(issue.documents_snapshot_json)
    if isinstance(raw, list):
        values = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            doc_key = DOC_FIELD_MAP.get(str(item.get("field") or item.get("tipo") or "").strip().lower())
            if doc_key and doc_key not in values:
                values.append(doc_key)
        return values
    if isinstance(raw, dict):
        values = []
        for key in raw.keys():
            doc_key = DOC_FIELD_MAP.get(str(key).strip().lower())
            if doc_key and doc_key not in values:
                values.append(doc_key)
        return values
    return []


def _legacy_issue_status(issue: DocIssue) -> str:
    latest_reupload = issue.reuploads.order_by("-created_at").first()
    if issue.status == DocIssue.Status.RESOLVIDO:
        if latest_reupload and latest_reupload.status == DocReupload.Status.ACEITO:
            return "accepted"
        return "closed"

    if latest_reupload is None:
        return ISSUE_STATUS_MAP.get(issue.status, "open")
    if latest_reupload.status == DocReupload.Status.RECEBIDO:
        return "received"
    if latest_reupload.status == DocReupload.Status.REJEITADO:
        return "rejected"
    if latest_reupload.status == DocReupload.Status.ACEITO:
        return "accepted"
    return "waiting_user"


def build_issues_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {"ok": True, "issues": [], "cadastro": None}

    issues = []
    queryset = (
        associado.doc_issues.prefetch_related("reuploads")
        .order_by("-created_at")
    )
    for issue in queryset:
        issues.append(
            {
                "id": issue.id,
                "associadodois_cadastro_id": associado.id,
                "cpf_cnpj": issue.cpf_cnpj or associado.cpf_cnpj,
                "contrato_codigo_contrato": issue.contrato_codigo or associado.contrato_codigo_contrato or None,
                "title": "Documentação pendente",
                "message": issue.mensagem,
                "required_docs": _required_docs_from_issue(issue),
                "status": _legacy_issue_status(issue),
                "opened_at": format_date_iso(issue.created_at),
                "closed_at": format_date_iso(issue.updated_at if issue.status == DocIssue.Status.RESOLVIDO else None),
                "extras": {
                    "documents_snapshot": parse_jsonish(issue.documents_snapshot_json),
                    "agent_uploads": parse_jsonish(issue.agent_uploads_json),
                },
                "created_at": format_date_iso(issue.created_at),
                "updated_at": format_date_iso(issue.updated_at),
            }
        )

    if not issues and associado.esteira is not None:
        for pendencia in associado.esteira.pendencias.all().order_by("-created_at"):
            issues.append(
                {
                    "id": pendencia.id,
                    "associadodois_cadastro_id": associado.id,
                    "cpf_cnpj": associado.cpf_cnpj,
                    "contrato_codigo_contrato": associado.contrato_codigo_contrato or None,
                    "title": "Pendência de análise",
                    "message": pendencia.descricao,
                    "required_docs": [],
                    "status": "open" if pendencia.status == "aberta" else "closed",
                    "opened_at": format_date_iso(pendencia.created_at),
                    "closed_at": format_date_iso(pendencia.resolvida_em),
                    "extras": {
                        "tipo": pendencia.tipo,
                    },
                    "created_at": format_date_iso(pendencia.created_at),
                    "updated_at": format_date_iso(pendencia.updated_at),
                }
            )

    return {
        "ok": True,
        "issues": issues,
        "cadastro": {
            "id": associado.id,
            "cpf_cnpj": associado.cpf_cnpj,
            "contrato_codigo_contrato": associado.contrato_codigo_contrato or None,
        },
    }


def _parse_ref_month(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        year_str, month_str = str(value).split("-", 1)
        return int(year_str), int(month_str)
    except Exception:
        return None


def build_mensalidades_payload(associado: Associado | None, *, ref_from: str | None = None, ref_to: str | None = None) -> dict[str, object]:
    if associado is None:
        return {"parcelas": [], "resumo": build_resumo_payload(None), "proximo_ciclo": None}

    ref_from_parts = _parse_ref_month(ref_from)
    ref_to_parts = _parse_ref_month(ref_to)

    parcelas_qs = (
        Parcela.objects.filter(associado=associado)
        .exclude(status=Parcela.Status.CANCELADO)
        .order_by("referencia_mes", "numero")
    )
    if ref_from_parts:
        parcelas_qs = parcelas_qs.filter(
            Q(referencia_mes__year__gt=ref_from_parts[0])
            | Q(referencia_mes__year=ref_from_parts[0], referencia_mes__month__gte=ref_from_parts[1])
        )
    if ref_to_parts:
        parcelas_qs = parcelas_qs.filter(
            Q(referencia_mes__year__lt=ref_to_parts[0])
            | Q(referencia_mes__year=ref_to_parts[0], referencia_mes__month__lte=ref_to_parts[1])
        )

    parcelas = [
        {
            "id": parcela.id,
            "numero": parcela.numero,
            "ref_ano": parcela.referencia_mes.year,
            "ref_mes": parcela.referencia_mes.month,
            "valor": decimal_to_number(parcela.valor),
            "previsao_data": format_date_iso(parcela.data_vencimento),
            "pago_em": format_date_iso(parcela.data_pagamento),
            "status": parcela.status,
            "status_code": PARCELA_STATUS_CODE_MAP.get(parcela.status, "0"),
            "parcela_valor": decimal_to_number(parcela.valor),
        }
        for parcela in parcelas_qs
    ]

    resumo = build_resumo_payload(associado)
    return {
        "parcelas": parcelas,
        "resumo": resumo,
        "proximo_ciclo": None,
        "refinanciamento": None,
    }


def build_antecipacao_payload(associado: Associado | None) -> dict[str, object]:
    if associado is None:
        return {"historico": []}

    raw = parse_jsonish(associado.anticipations_json)
    if isinstance(raw, list):
        historico = [
            {
                "valor": decimal_to_number(item.get("valorAuxilio") or item.get("valor") or 0),
                "data_pagamento": item.get("dataEnvio") or item.get("paid_at"),
                "status": item.get("status") or "pendente",
                "status_label": item.get("status") or "Pendente",
                "observacao": item.get("observacao"),
            }
            for item in raw
            if isinstance(item, dict)
        ]
        if historico:
            return {"historico": historico}

    pagamentos = (
        associado.tesouraria_pagamentos.filter(status__in=["pago", "pendente"])
        .order_by("-paid_at", "-created_at")
    )
    if pagamentos.exists():
        return {
            "historico": [
                {
                    "valor": decimal_to_number(pagamento.valor_pago),
                    "data_pagamento": format_date_iso(pagamento.paid_at or pagamento.created_at),
                    "status": pagamento.status,
                    "status_label": pagamento.get_status_display(),
                }
                for pagamento in pagamentos
            ]
        }

    return {"historico": []}


def get_latest_auxilio2_charge(user, *, associado: Associado | None = None) -> Auxilio2Filiacao | None:
    if user is None:
        return None
    queryset = Auxilio2Filiacao.objects.filter(user=user)
    if associado is not None:
        queryset = queryset.filter(Q(associado=associado) | Q(associado__isnull=True))
    return queryset.order_by("-created_at").first()


def build_auxilio2_payload(user, *, associado: Associado | None = None) -> dict[str, object]:
    charge = get_latest_auxilio2_charge(user, associado=associado)
    if charge is not None:
        return {
            "status": charge.status,
            "complete": charge.status == Auxilio2Filiacao.Status.PAGO,
            "txid": charge.txid,
            "valor": decimal_to_number(charge.valor),
            "chargeId": charge.charge_id or None,
            "locId": charge.loc_id,
            "filiacaoId": charge.id,
            "paidAt": format_date_iso(charge.paid_at),
            "pixCopiaECola": charge.pix_copia_cola or None,
            "imagemQrcode": charge.imagem_qrcode or None,
        }

    status = normalize_status(associado.auxilio2_status if associado else "")
    return {
        "status": status or "bloqueado",
        "complete": status == "pago",
        "txid": None,
        "valor": 30.0,
        "chargeId": None,
        "locId": None,
        "filiacaoId": None,
        "paidAt": None,
        "pixCopiaECola": None,
        "imagemQrcode": None,
    }


def create_auxilio2_charge(user, *, associado: Associado | None = None) -> Auxilio2Filiacao:
    existing = get_latest_auxilio2_charge(user, associado=associado)
    if existing is not None and existing.status == Auxilio2Filiacao.Status.PENDENTE:
        return existing

    now = timezone.now()
    txid = secrets.token_hex(10).upper()
    charge = Auxilio2Filiacao.objects.create(
        user=user,
        associado=associado,
        txid=txid,
        charge_id=f"AUX2-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3).upper()}",
        loc_id=int(now.timestamp()),
        valor=Decimal("30.00"),
        status=Auxilio2Filiacao.Status.PENDENTE,
        pix_copia_cola=STATIC_AUXILIO2_PIX,
        imagem_qrcode=STATIC_AUXILIO2_QR,
        raw={
            "mode": "static_fallback",
            "generated_at": now.isoformat(),
        },
    )

    if associado is not None:
        associado.auxilio2_status = Auxilio2Filiacao.Status.PENDENTE
        associado.auxilio2_updated_at = now
        associado.save(update_fields=["auxilio2_status", "auxilio2_updated_at", "updated_at"])

    return charge


def get_latest_paid_reference(associado: Associado) -> date | None:
    parcela = (
        Parcela.objects.filter(associado=associado, status=Parcela.Status.DESCONTADO)
        .order_by("-referencia_mes")
        .first()
    )
    if parcela is not None:
        return parcela.referencia_mes

    pagamento = (
        PagamentoMensalidade.objects.filter(
            associado=associado,
            status_code__in=["1", "4"],
        )
        .order_by("-referencia_month")
        .first()
    )
    if pagamento is not None:
        return pagamento.referencia_month
    return None
