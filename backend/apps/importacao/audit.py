from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from apps.contratos.models import Parcela
from apps.importacao.models import ArquivoRetornoItem, PagamentoMensalidade
from apps.importacao.services import classify_manual_paid_at_difference
from apps.tesouraria.models import BaixaManual
from core.legacy_dump import LegacyDump, parse_date, parse_decimal, parse_str


def _normalize_cpf(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _serialize_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def build_return_consistency_report(
    *,
    dump_path: str | Path,
    competencia: date | None = None,
    cpf: str | None = None,
) -> dict[str, object]:
    dump = LegacyDump.from_file(dump_path)
    cpf_filter = _normalize_cpf(cpf)

    legacy_rows: dict[tuple[str, date], dict[str, object]] = {}
    per_competencia = defaultdict(
        lambda: {
            "legacy_total": 0,
            "legacy_manual_pago": 0,
            "legacy_with_manual_path": 0,
            "current_total": 0,
            "current_manual_pago": 0,
            "current_with_manual_path": 0,
            "current_baixas_manuais": 0,
            "manual_rows_with_baixa_manual": 0,
            "timezone_only_paid_at": 0,
            "real_mismatches": 0,
        }
    )

    for row in dump.table_rows("pagamentos_mensalidades"):
        referencia = parse_date(row.get("referencia_month"))
        if referencia is None:
            continue
        if competencia and referencia != competencia:
            continue
        normalized_cpf = _normalize_cpf(parse_str(row.get("cpf_cnpj")))
        if cpf_filter and normalized_cpf != cpf_filter:
            continue
        if not normalized_cpf:
            continue

        payload = {
            "manual_status": parse_str(row.get("manual_status")),
            "manual_paid_at": parse_str(row.get("manual_paid_at")) or None,
            "manual_comprovante_path": parse_str(row.get("manual_comprovante_path")),
            "recebido_manual": (
                str(parse_decimal(row.get("recebido_manual")))
                if parse_decimal(row.get("recebido_manual")) is not None
                else None
            ),
            "status_code": parse_str(row.get("status_code")),
        }
        legacy_rows[(normalized_cpf, referencia)] = payload
        competencia_key = referencia.isoformat()
        per_competencia[competencia_key]["legacy_total"] += 1
        if payload["manual_status"] == "pago":
            per_competencia[competencia_key]["legacy_manual_pago"] += 1
        if payload["manual_comprovante_path"]:
            per_competencia[competencia_key]["legacy_with_manual_path"] += 1

    current_rows: dict[tuple[str, date], dict[str, object]] = {}
    baixas_lookup: set[tuple[str, date]] = set()
    pagamentos = PagamentoMensalidade.objects.all().order_by("referencia_month", "cpf_cnpj", "id")
    if competencia:
        pagamentos = pagamentos.filter(referencia_month=competencia)
    if cpf_filter:
        pagamentos = pagamentos.filter(cpf_cnpj=cpf_filter)

    for pagamento in pagamentos.iterator():
        normalized_cpf = _normalize_cpf(pagamento.cpf_cnpj)
        if not normalized_cpf:
            continue
        key = (normalized_cpf, pagamento.referencia_month)
        payload = {
            "id": pagamento.id,
            "manual_status": pagamento.manual_status or "",
            "manual_paid_at": _serialize_datetime(pagamento.manual_paid_at),
            "manual_comprovante_path": pagamento.manual_comprovante_path or "",
            "recebido_manual": (
                str(pagamento.recebido_manual)
                if pagamento.recebido_manual is not None
                else None
            ),
            "status_code": (pagamento.status_code or "").strip(),
        }
        current_rows[key] = payload
        competencia_key = pagamento.referencia_month.isoformat()
        per_competencia[competencia_key]["current_total"] += 1
        if payload["manual_status"] == "pago":
            per_competencia[competencia_key]["current_manual_pago"] += 1
        if payload["manual_comprovante_path"]:
            per_competencia[competencia_key]["current_with_manual_path"] += 1

    baixas_manuais = BaixaManual.objects.select_related("parcela", "parcela__associado")
    if competencia:
        baixas_manuais = baixas_manuais.filter(parcela__referencia_mes=competencia)
    if cpf_filter:
        baixas_manuais = baixas_manuais.filter(parcela__associado__cpf_cnpj=cpf_filter)

    for baixa in baixas_manuais.iterator():
        referencia = baixa.parcela.referencia_mes
        normalized_cpf = _normalize_cpf(baixa.parcela.associado.cpf_cnpj)
        if not normalized_cpf:
            continue
        baixas_lookup.add((normalized_cpf, referencia))
        per_competencia[referencia.isoformat()]["current_baixas_manuais"] += 1

    mismatches: list[dict[str, object]] = []
    timezone_only_total = 0
    missing_current = 0
    missing_legacy = 0
    manual_rows_with_baixa_manual = 0

    all_keys = sorted(set(legacy_rows) | set(current_rows), key=lambda item: (item[1], item[0]))
    for key in all_keys:
        normalized_cpf, referencia = key
        legacy_payload = legacy_rows.get(key)
        current_payload = current_rows.get(key)
        competencia_key = referencia.isoformat()

        if legacy_payload is None:
            missing_legacy += 1
            per_competencia[competencia_key]["real_mismatches"] += 1
            mismatches.append(
                {
                    "cpf_cnpj": normalized_cpf,
                    "referencia_month": competencia_key,
                    "tipo": "missing_legacy",
                    "legacy": None,
                    "current": current_payload,
                }
            )
            continue

        if current_payload is None:
            missing_current += 1
            per_competencia[competencia_key]["real_mismatches"] += 1
            mismatches.append(
                {
                    "cpf_cnpj": normalized_cpf,
                    "referencia_month": competencia_key,
                    "tipo": "missing_current",
                    "legacy": legacy_payload,
                    "current": None,
                }
            )
            continue

        paid_at_comparison = classify_manual_paid_at_difference(
            datetime.fromisoformat(current_payload["manual_paid_at"].replace("Z", "+00:00"))
            if current_payload["manual_paid_at"]
            else None,
            datetime.strptime(legacy_payload["manual_paid_at"], "%Y-%m-%d %H:%M:%S")
            if legacy_payload["manual_paid_at"]
            else None,
        )
        other_equal = (
            legacy_payload["manual_status"] == current_payload["manual_status"]
            and (legacy_payload["manual_comprovante_path"] or "")
            == (current_payload["manual_comprovante_path"] or "")
            and (legacy_payload["recebido_manual"] or None)
            == (current_payload["recebido_manual"] or None)
            and (legacy_payload["status_code"] or "")
            == (current_payload["status_code"] or "")
        )
        has_baixa_manual = key in baixas_lookup
        if (legacy_payload["manual_status"] == "pago" or current_payload["manual_status"] == "pago") and has_baixa_manual:
            manual_rows_with_baixa_manual += 1
            per_competencia[competencia_key]["manual_rows_with_baixa_manual"] += 1

        if other_equal and paid_at_comparison == "timezone_only":
            timezone_only_total += 1
            per_competencia[competencia_key]["timezone_only_paid_at"] += 1
            continue

        if other_equal and paid_at_comparison in {"exact", "missing"}:
            continue

        per_competencia[competencia_key]["real_mismatches"] += 1
        mismatches.append(
            {
                "cpf_cnpj": normalized_cpf,
                "referencia_month": competencia_key,
                "tipo": "field_mismatch",
                "manual_paid_at_comparison": paid_at_comparison,
                "legacy": legacy_payload,
                "current": current_payload,
            }
        )

    itens_retorno = ArquivoRetornoItem.objects.all()
    if competencia:
        itens_retorno = itens_retorno.filter(arquivo_retorno__competencia=competencia)
    if cpf_filter:
        itens_retorno = itens_retorno.filter(cpf_cnpj=cpf_filter)
    itens_retorno_orfaos = itens_retorno.filter(parcela__isnull=True).count()

    parcelas = Parcela.all_objects.exclude(status=Parcela.Status.CANCELADO)
    if competencia:
        parcelas = parcelas.filter(referencia_mes=competencia)
    if cpf_filter:
        parcelas = parcelas.filter(associado__cpf_cnpj=cpf_filter)
    parcelas_sem_retorno_ou_baixa = parcelas.filter(
        itens_retorno__isnull=True,
        baixa_manual__isnull=True,
    ).count()

    return {
        "generated_at": datetime.now().isoformat(),
        "dump_path": str(Path(dump_path).resolve()),
        "filters": {
            "competencia": _serialize_date(competencia),
            "cpf_cnpj": cpf_filter or None,
        },
        "summary": {
            "competencias": dict(sorted(per_competencia.items())),
            "timezone_only_paid_at_total": timezone_only_total,
            "real_mismatch_total": len(mismatches),
            "missing_current_total": missing_current,
            "missing_legacy_total": missing_legacy,
            "itens_retorno_orfaos": itens_retorno_orfaos,
            "parcelas_sem_retorno_ou_baixa": parcelas_sem_retorno_ou_baixa,
            "baixas_manuais_total": len(baixas_lookup),
            "manual_rows_with_baixa_manual_total": manual_rows_with_baixa_manual,
            "status": "ok" if not mismatches else "divergente",
        },
        "mismatches": mismatches,
    }


def write_report_json(report_path: str | Path, payload: dict[str, object]) -> Path:
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target
