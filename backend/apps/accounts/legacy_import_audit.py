from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from django.apps import apps as django_apps
from django.conf import settings
from django.utils import timezone

from apps.accounts.legacy_helpers import (
    build_legacy_document_path,
    map_legacy_document_type,
    map_legacy_role_code,
)
from apps.accounts.models import (
    AgenteMargemConfig,
    AgenteMargemHistorico,
    AgenteMargemSnapshot,
    Role,
    User,
)
from apps.associados.models import Associado, Documento, only_digits
from apps.associados.services import add_months, calculate_contract_dates
from apps.contratos.models import Ciclo, Contrato, Parcela
from apps.esteira.models import DocIssue, DocReupload, EsteiraItem
from apps.financeiro.models import Despesa
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import (
    AjusteValor,
    Assumption as RefinanciamentoAssumption,
    Comprovante as RefinanciamentoComprovante,
    Item as RefinanciamentoItem,
    Refinanciamento,
)
from apps.tesouraria.models import Confirmacao, Pagamento
from core.business_reference import backfill_business_references
from core.legacy_dump import (
    LegacyDump,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_int,
    parse_json,
    parse_str,
    parse_timestamp,
)
from core.models import BaseModel


SUCCESS_STATUS = "100% concluído"
OPERATIONAL_ROLE_NAMES = {"admin", "agente", "analista", "coordenador", "tesoureiro"}
EXPECTED_COUNTS = {
    "roles": 8,
    "users_operacionais": 36,
    "agente_cadastros": 648,
    "associados": 647,
    "associado_users": 647,
    "contratos": 648,
    "ciclos": 648,
    "parcelas": 1944,
    "documentos": 4405,
    "agente_cadastro_assumptions": 111,
    "agente_doc_issues": 437,
    "agente_doc_reuploads": 616,
    "agente_margens": 11,
    "agente_margem_historicos": 11,
    "agente_margem_snapshots": 671,
    "despesas": 82,
    "pagamentos_mensalidades": 2081,
    "tesouraria_confirmacoes": 198,
    "tesouraria_pagamentos": 648,
    "refinanciamentos": 347,
    "refinanciamento_assumptions": 251,
    "refinanciamento_ajustes_valor": 0,
    "refinanciamento_comprovantes": 690,
    "refinanciamento_itens": 51,
    "refinanciamento_solicitacoes": 330,
}


def default_legacy_report_path(prefix: str = "legacy_import_report") -> Path:
    timestamp = timezone.localtime().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


def save_legacy_report(report: dict[str, Any], report_path: Path) -> Path:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return report_path


def managed_base_model_classes() -> list[type[BaseModel]]:
    model_classes: list[type[BaseModel]] = []
    for model_class in django_apps.get_models():
        if not issubclass(model_class, BaseModel):
            continue
        if not model_class._meta.managed or model_class._meta.abstract:
            continue
        model_classes.append(model_class)
    return sorted(model_classes, key=lambda item: item._meta.label_lower)


def backfill_all_business_references() -> dict[str, Any]:
    updated_by_model = backfill_business_references(managed_base_model_classes())
    return {
        "updated_by_model": updated_by_model,
        "total_updated": sum(updated_by_model.values()),
    }


def _key_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        localized = timezone.localtime(value) if timezone.is_aware(value) else value
        return localized.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, str):
        return value.strip()
    return value


def _serialize_key(*parts: Any) -> str:
    return json.dumps([_key_value(part) for part in parts], ensure_ascii=True, separators=(",", ":"))


def _role_key(email: str, role_codes: Iterable[str]) -> str:
    return _serialize_key(email.lower(), sorted(role_codes))


def _lower_email(value: str | None) -> str:
    return (value or "").strip().lower()


def _doc_issue_key(
    cpf_cnpj: str,
    contract_code: str,
    analyst_email: str,
    message: str,
    created_at: datetime | None,
) -> str:
    return _serialize_key(
        cpf_cnpj,
        contract_code[:80],
        _lower_email(analyst_email),
        message,
        created_at,
    )


def _synthetic_doc_issue_message(
    legacy_issue_id: int | None,
    notes: str,
) -> str:
    prefix = (
        f"[legacy-missing-issue:{legacy_issue_id}]"
        if legacy_issue_id is not None
        else "[legacy-missing-issue]"
    )
    note = "Reupload legado sem issue original."
    return f"{prefix} {note}".strip()


def _orphan_confirmacao_contract_code(legacy_cadastro_id: int) -> str:
    return f"LEGACY-CONF-{legacy_cadastro_id}"[:40]


def _refinanciamento_key_parts(
    *,
    cpf_cnpj: str,
    cycle_key: str,
    ref1: date | None,
    ref2: date | None,
    ref3: date | None,
    contrato_codigo_origem: str,
) -> tuple[Any, ...]:
    return (
        cpf_cnpj,
        cycle_key[:32],
        ref1,
        ref2,
        ref3,
        contrato_codigo_origem[:80],
    )


def _refinanciamento_key(**kwargs: Any) -> str:
    return _serialize_key(*_refinanciamento_key_parts(**kwargs))


def _competencia_from_timestamps(*values: datetime | None) -> date | None:
    for value in values:
        if value is None:
            continue
        return value.date().replace(day=1)
    return None


def _schedule_references_from_row(row: dict[str, str]) -> list[date]:
    data_aprovacao = parse_date(row.get("contrato_data_aprovacao"))
    _approval, calc_primeira, _mes_averbacao = calculate_contract_dates(data_aprovacao)
    data_primeira = parse_date(row.get("contrato_data_envio_primeira")) or calc_primeira
    primeira_referencia = data_primeira.replace(day=1)
    prazo_meses = parse_int(row.get("contrato_prazo_meses")) or 3
    return [add_months(primeira_referencia, index) for index in range(prazo_meses)]


def _legacy_dump_context(dump: LegacyDump) -> dict[str, Any]:
    roles_rows = dump.table_rows("roles")
    users_rows = dump.table_rows("users")
    role_user_rows = dump.table_rows("role_user")
    cadastro_rows = dump.table_rows("agente_cadastros")

    legacy_role_name_by_id: dict[int, str] = {}
    for row in roles_rows:
        role_id = parse_int(row.get("id"))
        if role_id is None:
            continue
        legacy_role_name_by_id[role_id] = parse_str(row.get("name")).strip().lower()

    legacy_user_email_by_id: dict[int, str] = {}
    for row in users_rows:
        user_id = parse_int(row.get("id"))
        email = parse_str(row.get("email")).strip().lower()
        if user_id is None or not email:
            continue
        legacy_user_email_by_id[user_id] = email

    operational_role_codes_by_user: dict[int, set[str]] = defaultdict(set)
    for row in role_user_rows:
        user_id = parse_int(row.get("user_id"))
        role_id = parse_int(row.get("role_id"))
        if user_id is None or role_id is None:
            continue
        role_name = legacy_role_name_by_id.get(role_id, "")
        if role_name not in OPERATIONAL_ROLE_NAMES:
            continue
        role_code = map_legacy_role_code(role_name)
        if role_code:
            operational_role_codes_by_user[user_id].add(role_code)

    cpf_by_cad_id: dict[int, str] = {}
    contract_code_by_cad_id: dict[int, str] = {}
    for row in cadastro_rows:
        cadastro_id = parse_int(row.get("id"))
        if cadastro_id is None:
            continue
        cpf_by_cad_id[cadastro_id] = only_digits(parse_str(row.get("cpf_cnpj")))
        contract_code_by_cad_id[cadastro_id] = parse_str(row.get("contrato_codigo_contrato"))[:40]

    associadodois_cpf_by_id: dict[int, str] = {}
    for row in dump.table_rows("associadodois_cadastros"):
        cadastro_id = parse_int(row.get("id"))
        if cadastro_id is None:
            continue
        associadodois_cpf_by_id[cadastro_id] = only_digits(parse_str(row.get("cpf_cnpj")))

    return {
        "cadastro_rows": cadastro_rows,
        "cpf_by_cad_id": cpf_by_cad_id,
        "contract_code_by_cad_id": contract_code_by_cad_id,
        "associadodois_cpf_by_id": associadodois_cpf_by_id,
        "legacy_user_email_by_id": legacy_user_email_by_id,
        "operational_role_codes_by_user": operational_role_codes_by_user,
    }


def _build_section_report(
    *,
    name: str,
    source_rows: list[str],
    actual_rows: list[str],
    expected_source_rows: int,
    expected_db_rows: int,
    note: str = "",
    allowed_missing_rows: list[str] | None = None,
) -> dict[str, Any]:
    source_counter = Counter(source_rows)
    actual_counter = Counter(actual_rows)
    source_keys = set(source_counter)
    actual_keys = set(actual_counter)
    missing_counter = source_counter - actual_counter
    allowed_missing_counter = Counter(allowed_missing_rows or [])
    missing_counter = missing_counter - allowed_missing_counter
    unexpected_counter = actual_counter - source_counter
    missing = sorted(missing_counter.elements())
    unexpected = sorted(unexpected_counter.elements())
    return {
        "name": name,
        "expected_source_rows": expected_source_rows,
        "source_rows": len(source_rows),
        "expected_db_rows": expected_db_rows,
        "actual_rows": len(actual_rows),
        "source_key_count": len(source_keys),
        "actual_key_count": len(actual_keys),
        "source_duplicate_rows": len(source_rows) - len(source_keys),
        "actual_duplicate_rows": len(actual_rows) - len(actual_keys),
        "missing_keys_count": len(missing),
        "unexpected_keys_count": len(unexpected),
        "missing_keys_sample": missing[:10],
        "unexpected_keys_sample": unexpected[:10],
        "note": note,
        "ok": (
            not missing_counter
            and not unexpected_counter
        ),
    }


def build_legacy_verification_report(
    dump_path: str | Path,
    *,
    dry_run: bool = False,
    phases: dict[str, Any] | None = None,
    business_reference_backfill: dict[str, Any] | None = None,
) -> dict[str, Any]:
    dump_path = Path(dump_path).expanduser()
    dump = LegacyDump.from_file(dump_path)
    context = _legacy_dump_context(dump)

    legacy_user_email_by_id = context["legacy_user_email_by_id"]
    operational_role_codes_by_user = context["operational_role_codes_by_user"]
    cadastro_rows = context["cadastro_rows"]
    cpf_by_cad_id = context["cpf_by_cad_id"]
    contract_code_by_cad_id = context["contract_code_by_cad_id"]
    associadodois_cpf_by_id = context["associadodois_cpf_by_id"]

    sections: dict[str, dict[str, Any]] = {}

    role_source_rows = [
        _serialize_key(map_legacy_role_code(parse_str(row.get("name")).strip().lower()))
        for row in dump.table_rows("roles")
        if map_legacy_role_code(parse_str(row.get("name")).strip().lower())
    ]
    role_codes = {
        json.loads(item)[0]
        for item in role_source_rows
    }
    role_actual_rows = [
        _serialize_key(codigo)
        for codigo in Role.objects.filter(codigo__in=role_codes)
        .order_by("codigo")
        .values_list("codigo", flat=True)
    ]
    sections["roles"] = _build_section_report(
        name="roles",
        source_rows=role_source_rows,
        actual_rows=role_actual_rows,
        expected_source_rows=EXPECTED_COUNTS["roles"],
        expected_db_rows=EXPECTED_COUNTS["roles"],
    )

    operational_source_rows = [
        _role_key(legacy_user_email_by_id[user_id], role_codes)
        for user_id, role_codes in sorted(operational_role_codes_by_user.items())
        if legacy_user_email_by_id.get(user_id)
    ]
    operational_emails = {
        legacy_user_email_by_id[user_id]
        for user_id in operational_role_codes_by_user
        if legacy_user_email_by_id.get(user_id)
    }
    operational_actual_rows = []
    for user in (
        User.objects.filter(email__in=operational_emails)
        .prefetch_related("roles")
        .order_by("email")
    ):
        actual_role_codes = sorted(
            role.codigo
            for role in user.roles.all()
            if role.codigo in role_codes
        )
        operational_actual_rows.append(_role_key(user.email, actual_role_codes))
    sections["users_operacionais"] = _build_section_report(
        name="users_operacionais",
        source_rows=operational_source_rows,
        actual_rows=operational_actual_rows,
        expected_source_rows=EXPECTED_COUNTS["users_operacionais"],
        expected_db_rows=EXPECTED_COUNTS["users_operacionais"],
    )

    associado_source_rows = []
    contract_source_rows = []
    cycle_source_rows = []
    parcela_source_rows = []
    documento_source_rows = []
    competencia_counter: Counter[tuple[str, str]] = Counter()
    for row in cadastro_rows:
        cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
        if cpf_cnpj:
            associado_source_rows.append(_serialize_key(cpf_cnpj))
        contract_code = parse_str(row.get("contrato_codigo_contrato"))[:40]
        if contract_code:
            contract_source_rows.append(_serialize_key(contract_code))
            cycle_source_rows.append(_serialize_key(contract_code, 1))
            for index, referencia in enumerate(_schedule_references_from_row(row), start=1):
                parcela_source_rows.append(_serialize_key(contract_code, index, referencia))
                if cpf_cnpj:
                    competencia_counter[(cpf_cnpj, referencia.isoformat())] += 1
        raw_documents = parse_json(row.get("documents_json"))
        if not isinstance(raw_documents, list) or not cpf_cnpj:
            continue
        for item in raw_documents:
            if not isinstance(item, dict):
                continue
            relative_path = build_legacy_document_path(item)
            if not relative_path:
                continue
            documento_source_rows.append(
                _serialize_key(
                    cpf_cnpj,
                    map_legacy_document_type(str(item.get("field") or "")),
                    relative_path,
                )
            )
    documento_source_rows = sorted(set(documento_source_rows))

    associado_cpfs = {json.loads(item)[0] for item in associado_source_rows}
    contract_codes = {json.loads(item)[0] for item in contract_source_rows}
    associado_allowed_missing_rows = []
    for key, count in Counter(associado_source_rows).items():
        if count > 1:
            associado_allowed_missing_rows.extend([key] * (count - 1))
    sections["associados"] = _build_section_report(
        name="associados",
        source_rows=associado_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj)
            for cpf_cnpj in Associado.objects.filter(cpf_cnpj__in=associado_cpfs)
            .order_by("cpf_cnpj")
            .values_list("cpf_cnpj", flat=True)
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_cadastros"],
        expected_db_rows=EXPECTED_COUNTS["associados"],
        note="1 CPF duplicado consolidado é esperado.",
        allowed_missing_rows=associado_allowed_missing_rows,
    )
    sections["associado_users"] = _build_section_report(
        name="associado_users",
        source_rows=[_serialize_key(cpf, f"{cpf}@app.abase.local") for cpf in sorted(associado_cpfs)],
        actual_rows=[
            _serialize_key(cpf_cnpj, user_email)
            for cpf_cnpj, user_email in Associado.objects.filter(cpf_cnpj__in=associado_cpfs, user__isnull=False)
            .order_by("cpf_cnpj")
            .values_list("cpf_cnpj", "user__email")
        ],
        expected_source_rows=EXPECTED_COUNTS["associados"],
        expected_db_rows=EXPECTED_COUNTS["associado_users"],
    )
    sections["contratos"] = _build_section_report(
        name="contratos",
        source_rows=contract_source_rows,
        actual_rows=[
            _serialize_key(codigo)
            for codigo in Contrato.objects.filter(codigo__in=contract_codes)
            .order_by("codigo")
            .values_list("codigo", flat=True)
        ],
        expected_source_rows=EXPECTED_COUNTS["contratos"],
        expected_db_rows=EXPECTED_COUNTS["contratos"],
    )
    sections["ciclos"] = _build_section_report(
        name="ciclos",
        source_rows=cycle_source_rows,
        actual_rows=[
            _serialize_key(contrato_codigo, numero)
            for contrato_codigo, numero in Ciclo.objects.filter(contrato__codigo__in=contract_codes)
            .order_by("contrato__codigo", "numero")
            .values_list("contrato__codigo", "numero")
        ],
        expected_source_rows=EXPECTED_COUNTS["ciclos"],
        expected_db_rows=EXPECTED_COUNTS["ciclos"],
    )
    sections["parcelas"] = _build_section_report(
        name="parcelas",
        source_rows=parcela_source_rows,
        actual_rows=[
            _serialize_key(contrato_codigo, numero, referencia_mes)
            for contrato_codigo, numero, referencia_mes in Parcela.objects.filter(
                ciclo__contrato__codigo__in=contract_codes
            )
            .order_by("ciclo__contrato__codigo", "numero")
            .values_list("ciclo__contrato__codigo", "numero", "referencia_mes")
        ],
        expected_source_rows=EXPECTED_COUNTS["parcelas"],
        expected_db_rows=EXPECTED_COUNTS["parcelas"],
    )
    sections["documentos"] = _build_section_report(
        name="documentos",
        source_rows=documento_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj, tipo, arquivo)
            for cpf_cnpj, tipo, arquivo in Documento.objects.filter(associado__cpf_cnpj__in=associado_cpfs)
            .order_by("associado__cpf_cnpj", "tipo", "arquivo")
            .values_list("associado__cpf_cnpj", "tipo", "arquivo")
        ],
        expected_source_rows=EXPECTED_COUNTS["documentos"],
        expected_db_rows=EXPECTED_COUNTS["documentos"],
    )

    assumption_source_rows = []
    assumption_cpfs: set[str] = set()
    for row in dump.table_rows("agente_cadastro_assumptions"):
        cpf_cnpj = (
            cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, "")
            or associadodois_cpf_by_id.get(parse_int(row.get("associadodois_cadastro_id")) or -1, "")
        )
        if not cpf_cnpj:
            continue
        assumption_cpfs.add(cpf_cnpj)
        assumption_source_rows.append(_serialize_key(cpf_cnpj))
    assumption_allowed_missing_rows = []
    for key, count in Counter(assumption_source_rows).items():
        if count > 1:
            assumption_allowed_missing_rows.extend([key] * (count - 1))
    sections["agente_cadastro_assumptions"] = _build_section_report(
        name="agente_cadastro_assumptions",
        source_rows=assumption_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj)
            for cpf_cnpj in EsteiraItem.objects.filter(
                associado__cpf_cnpj__in=assumption_cpfs
            )
            .order_by("associado__cpf_cnpj")
            .values_list("associado__cpf_cnpj", flat=True)
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_cadastro_assumptions"],
        expected_db_rows=len(set(assumption_source_rows)),
        allowed_missing_rows=assumption_allowed_missing_rows,
    )

    doc_issue_source_rows = []
    doc_issue_cpfs: set[str] = set()
    issue_rows_by_id = {
        parse_int(row.get("id")): row
        for row in dump.table_rows("agente_doc_issues")
        if parse_int(row.get("id")) is not None
    }
    for row in dump.table_rows("agente_doc_issues"):
        cpf_cnpj = cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, "")
        analista_email = _lower_email(
            legacy_user_email_by_id.get(parse_int(row.get("analista_id")) or -1, "")
        )
        if not cpf_cnpj or not analista_email:
            continue
        doc_issue_cpfs.add(cpf_cnpj)
        doc_issue_source_rows.append(
            _doc_issue_key(
                cpf_cnpj,
                parse_str(row.get("contrato_codigo_contrato"))[:80],
                analista_email,
                parse_str(row.get("mensagem")),
                parse_timestamp(row.get("created_at")),
            )
        )
    sections["agente_doc_issues"] = _build_section_report(
        name="agente_doc_issues",
        source_rows=doc_issue_source_rows,
        actual_rows=[
            _doc_issue_key(cpf_cnpj, contrato_codigo, analista_email, mensagem, created_at)
            for cpf_cnpj, contrato_codigo, analista_email, mensagem, created_at in DocIssue.objects.filter(
                associado__cpf_cnpj__in=doc_issue_cpfs
            )
            .order_by("associado__cpf_cnpj", "created_at", "id")
            .values_list(
                "associado__cpf_cnpj",
                "contrato_codigo",
                "analista__email",
                "mensagem",
                "created_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_doc_issues"],
        expected_db_rows=EXPECTED_COUNTS["agente_doc_issues"],
    )

    doc_reupload_source_rows = []
    doc_reupload_cpfs: set[str] = set()
    for row in dump.table_rows("agente_doc_reuploads"):
        cpf_cnpj = cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, "")
        issue_row = issue_rows_by_id.get(parse_int(row.get("agente_doc_issue_id")))
        if not cpf_cnpj:
            continue
        doc_reupload_cpfs.add(cpf_cnpj)
        if issue_row is not None:
            issue_key = _doc_issue_key(
                cpf_by_cad_id.get(parse_int(issue_row.get("agente_cadastro_id")) or -1, ""),
                parse_str(issue_row.get("contrato_codigo_contrato"))[:80],
                _lower_email(
                    legacy_user_email_by_id.get(parse_int(issue_row.get("analista_id")) or -1, "")
                ),
                parse_str(issue_row.get("mensagem")),
                parse_timestamp(issue_row.get("created_at")),
            )
        else:
            issue_key = _doc_issue_key(
                cpf_cnpj,
                parse_str(row.get("contrato_codigo_contrato"))[:80],
                _lower_email(
                    legacy_user_email_by_id.get(parse_int(row.get("uploaded_by_user_id")) or -1, "")
                ),
                _synthetic_doc_issue_message(
                    parse_int(row.get("agente_doc_issue_id")),
                    parse_str(row.get("notes")),
                ),
                parse_timestamp(row.get("created_at")) or parse_timestamp(row.get("uploaded_at")),
            )
        doc_reupload_source_rows.append(
            _serialize_key(
                issue_key,
                parse_str(row.get("file_relative_path"))[:500],
                parse_timestamp(row.get("uploaded_at")),
            )
        )
    sections["agente_doc_reuploads"] = _build_section_report(
        name="agente_doc_reuploads",
        source_rows=doc_reupload_source_rows,
        actual_rows=[
            _serialize_key(
                _doc_issue_key(
                    cpf_cnpj,
                    contrato_codigo,
                    analista_email,
                    mensagem,
                    issue_created_at,
                ),
                file_relative_path,
                uploaded_at,
            )
            for cpf_cnpj, contrato_codigo, analista_email, mensagem, issue_created_at, file_relative_path, uploaded_at in DocReupload.objects.filter(
                associado__cpf_cnpj__in=doc_reupload_cpfs
            )
            .order_by("doc_issue__associado__cpf_cnpj", "uploaded_at", "id")
            .values_list(
                "doc_issue__associado__cpf_cnpj",
                "doc_issue__contrato_codigo",
                "doc_issue__analista__email",
                "doc_issue__mensagem",
                "doc_issue__created_at",
                "file_relative_path",
                "uploaded_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_doc_reuploads"],
        expected_db_rows=EXPECTED_COUNTS["agente_doc_reuploads"],
    )

    margem_source_rows = [
        _serialize_key(
            legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, ""),
            parse_decimal(row.get("percentual")) or Decimal("10.00"),
            parse_timestamp(row.get("vigente_desde")) or parse_timestamp(row.get("created_at")),
        )
        for row in dump.table_rows("agente_margens")
        if legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, "")
    ]
    margem_emails = {
        json.loads(item)[0] for item in margem_source_rows if json.loads(item)[0]
    }
    sections["agente_margens"] = _build_section_report(
        name="agente_margens",
        source_rows=margem_source_rows,
        actual_rows=[
            _serialize_key(_lower_email(email), percentual, vigente_desde)
            for email, percentual, vigente_desde in AgenteMargemConfig.objects.filter(agente__email__in=margem_emails)
            .order_by("agente__email", "vigente_desde")
            .values_list("agente__email", "percentual", "vigente_desde")
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_margens"],
        expected_db_rows=EXPECTED_COUNTS["agente_margens"],
    )

    margem_historico_source_rows = [
        _serialize_key(
            legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, ""),
            parse_decimal(row.get("percentual_anterior")),
            parse_decimal(row.get("percentual_novo")),
            parse_str(row.get("motivo"))[:190],
            parse_timestamp(row.get("created_at")),
        )
        for row in dump.table_rows("agente_margem_historicos")
        if legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, "")
    ]
    sections["agente_margem_historicos"] = _build_section_report(
        name="agente_margem_historicos",
        source_rows=margem_historico_source_rows,
        actual_rows=[
            _serialize_key(_lower_email(email), percentual_anterior, percentual_novo, motivo, created_at)
            for email, percentual_anterior, percentual_novo, motivo, created_at in AgenteMargemHistorico.objects.filter(
                agente__email__in=margem_emails
            )
            .order_by("agente__email", "created_at", "id")
            .values_list(
                "agente__email",
                "percentual_anterior",
                "percentual_novo",
                "motivo",
                "created_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_margem_historicos"],
        expected_db_rows=EXPECTED_COUNTS["agente_margem_historicos"],
    )

    margem_snapshot_source_rows = [
        _serialize_key(
            cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, ""),
            legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, ""),
            parse_decimal(row.get("percentual_anterior")),
            parse_decimal(row.get("percentual_novo")),
            parse_decimal(row.get("mensalidade")),
            parse_decimal(row.get("margem_disponivel")),
            parse_timestamp(row.get("created_at")),
        )
        for row in dump.table_rows("agente_margem_snapshots")
        if cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, "")
        and legacy_user_email_by_id.get(parse_int(row.get("agente_user_id")) or -1, "")
    ]
    sections["agente_margem_snapshots"] = _build_section_report(
        name="agente_margem_snapshots",
        source_rows=margem_snapshot_source_rows,
        actual_rows=[
            _serialize_key(
                cpf_cnpj,
                _lower_email(email),
                percentual_anterior,
                percentual_novo,
                mensalidade,
                margem_disponivel,
                created_at,
            )
            for cpf_cnpj, email, percentual_anterior, percentual_novo, mensalidade, margem_disponivel, created_at in AgenteMargemSnapshot.objects.filter(
                cadastro__cpf_cnpj__in=associado_cpfs,
                agente__email__in=margem_emails,
            )
            .order_by("cadastro__cpf_cnpj", "created_at", "id")
            .values_list(
                "cadastro__cpf_cnpj",
                "agente__email",
                "percentual_anterior",
                "percentual_novo",
                "mensalidade",
                "margem_disponivel",
                "created_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["agente_margem_snapshots"],
        expected_db_rows=EXPECTED_COUNTS["agente_margem_snapshots"],
    )

    despesa_source_rows = [
        _serialize_key(
            parse_str(row.get("categoria"))[:100],
            parse_str(row.get("descricao"))[:255],
            parse_decimal(row.get("valor")) or Decimal("0.00"),
            parse_date(row.get("data_despesa")),
            parse_timestamp(row.get("created_at")),
        )
        for row in dump.table_rows("despesas")
    ]
    sections["despesas"] = _build_section_report(
        name="despesas",
        source_rows=despesa_source_rows,
        actual_rows=[
            _serialize_key(categoria, descricao, valor, data_despesa, created_at)
            for categoria, descricao, valor, data_despesa, created_at in Despesa.objects.order_by("created_at", "id").values_list(
                "categoria",
                "descricao",
                "valor",
                "data_despesa",
                "created_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["despesas"],
        expected_db_rows=EXPECTED_COUNTS["despesas"],
    )

    pagamento_mensalidade_source_rows = [
        _serialize_key(
            only_digits(parse_str(row.get("cpf_cnpj"))),
            parse_date(row.get("referencia_month")),
        )
        for row in dump.table_rows("pagamentos_mensalidades")
        if only_digits(parse_str(row.get("cpf_cnpj"))) and parse_date(row.get("referencia_month"))
    ]
    pagamento_cpfs = {json.loads(item)[0] for item in pagamento_mensalidade_source_rows}
    sections["pagamentos_mensalidades"] = _build_section_report(
        name="pagamentos_mensalidades",
        source_rows=pagamento_mensalidade_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj, referencia_month)
            for cpf_cnpj, referencia_month in PagamentoMensalidade.objects.filter(cpf_cnpj__in=pagamento_cpfs)
            .order_by("cpf_cnpj", "referencia_month", "id")
            .values_list("cpf_cnpj", "referencia_month")
        ],
        expected_source_rows=EXPECTED_COUNTS["pagamentos_mensalidades"],
        expected_db_rows=EXPECTED_COUNTS["pagamentos_mensalidades"],
    )

    confirmacao_source_rows = []
    for row in dump.table_rows("tesouraria_confirmacoes"):
        legacy_cad_id = parse_int(row.get("cad_id"))
        contract_code = contract_code_by_cad_id.get(legacy_cad_id or -1, "")
        if not contract_code and legacy_cad_id is not None:
            contract_code = _orphan_confirmacao_contract_code(legacy_cad_id)
        if not contract_code:
            continue
        created_at = parse_timestamp(row.get("created_at"))
        ligacao_at = parse_timestamp(row.get("ligacao_recebida_at"))
        averbacao_at = parse_timestamp(row.get("averbacao_confirmada_at"))
        if parse_bool(row.get("averbacao_confirmada")):
            tipo = Confirmacao.Tipo.AVERBACAO
            competencia = _competencia_from_timestamps(averbacao_at, created_at)
        else:
            tipo = Confirmacao.Tipo.LIGACAO
            competencia = _competencia_from_timestamps(ligacao_at, created_at)
        confirmacao_source_rows.append(_serialize_key(contract_code, tipo, competencia))
    confirmacao_contract_codes = {json.loads(item)[0] for item in confirmacao_source_rows}
    sections["tesouraria_confirmacoes"] = _build_section_report(
        name="tesouraria_confirmacoes",
        source_rows=confirmacao_source_rows,
        actual_rows=[
            _serialize_key(codigo, tipo, competencia)
            for codigo, tipo, competencia in Confirmacao.objects.filter(contrato__codigo__in=confirmacao_contract_codes)
            .order_by("contrato__codigo", "tipo", "competencia", "id")
            .values_list("contrato__codigo", "tipo", "competencia")
        ],
        expected_source_rows=EXPECTED_COUNTS["tesouraria_confirmacoes"],
        expected_db_rows=EXPECTED_COUNTS["tesouraria_confirmacoes"],
    )

    tesouraria_pagamento_source_rows = [
        _serialize_key(
            only_digits(parse_str(row.get("cpf_cnpj"))),
            parse_str(row.get("contrato_codigo_contrato"))[:80],
            parse_timestamp(row.get("paid_at")),
            parse_decimal(row.get("valor_pago")),
        )
        for row in dump.table_rows("tesouraria_pagamentos")
        if only_digits(parse_str(row.get("cpf_cnpj")))
    ]
    tesouraria_cpfs = {json.loads(item)[0] for item in tesouraria_pagamento_source_rows}
    sections["tesouraria_pagamentos"] = _build_section_report(
        name="tesouraria_pagamentos",
        source_rows=tesouraria_pagamento_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj, contrato_codigo, paid_at, valor_pago)
            for cpf_cnpj, contrato_codigo, paid_at, valor_pago in Pagamento.objects.filter(cpf_cnpj__in=tesouraria_cpfs)
            .order_by("cpf_cnpj", "paid_at", "id")
            .values_list("cpf_cnpj", "contrato_codigo", "paid_at", "valor_pago")
        ],
        expected_source_rows=EXPECTED_COUNTS["tesouraria_pagamentos"],
        expected_db_rows=EXPECTED_COUNTS["tesouraria_pagamentos"],
    )

    refinanciamento_source_rows = [
        _refinanciamento_key(
            cpf_cnpj=only_digits(parse_str(row.get("cpf_cnpj"))),
            cycle_key=parse_str(row.get("cycle_key")),
            ref1=parse_date(row.get("ref1")),
            ref2=parse_date(row.get("ref2")),
            ref3=parse_date(row.get("ref3")),
            contrato_codigo_origem=parse_str(row.get("contrato_codigo_origem")),
        )
        for row in dump.table_rows("refinanciamentos")
        if only_digits(parse_str(row.get("cpf_cnpj")))
    ]
    refinanciamento_cpfs = {json.loads(item)[0] for item in refinanciamento_source_rows}
    sections["refinanciamentos"] = _build_section_report(
        name="refinanciamentos",
        source_rows=refinanciamento_source_rows,
        actual_rows=[
            _refinanciamento_key(
                cpf_cnpj=cpf_cnpj_snapshot or associado_cpf,
                cycle_key=cycle_key,
                ref1=ref1,
                ref2=ref2,
                ref3=ref3,
                contrato_codigo_origem=contrato_codigo_origem,
            )
            for associado_cpf, cpf_cnpj_snapshot, cycle_key, ref1, ref2, ref3, contrato_codigo_origem in Refinanciamento.objects.filter(
                associado__cpf_cnpj__in=refinanciamento_cpfs
            )
            .order_by("associado__cpf_cnpj", "id")
            .values_list(
                "associado__cpf_cnpj",
                "cpf_cnpj_snapshot",
                "cycle_key",
                "ref1",
                "ref2",
                "ref3",
                "contrato_codigo_origem",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamentos"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamentos"],
    )

    refi_assumption_source_rows = [
        _serialize_key(
            cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, ""),
            parse_str(row.get("request_key"))[:80],
        )
        for row in dump.table_rows("refinanciamento_assumptions")
        if cpf_by_cad_id.get(parse_int(row.get("agente_cadastro_id")) or -1, "")
        and parse_str(row.get("request_key"))
    ]
    refi_assumption_cpfs = {json.loads(item)[0] for item in refi_assumption_source_rows}
    sections["refinanciamento_assumptions"] = _build_section_report(
        name="refinanciamento_assumptions",
        source_rows=refi_assumption_source_rows,
        actual_rows=[
            _serialize_key(cpf_cnpj, request_key)
            for cpf_cnpj, request_key in RefinanciamentoAssumption.objects.filter(cadastro__cpf_cnpj__in=refi_assumption_cpfs)
            .order_by("cadastro__cpf_cnpj", "request_key", "id")
            .values_list("cadastro__cpf_cnpj", "request_key")
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamento_assumptions"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamento_assumptions"],
    )

    ajuste_valor_source_rows = [
        _serialize_key(
            _refinanciamento_key(
                cpf_cnpj=only_digits(parse_str(ref_row.get("cpf_cnpj"))),
                cycle_key=parse_str(ref_row.get("cycle_key")),
                ref1=parse_date(ref_row.get("ref1")),
                ref2=parse_date(ref_row.get("ref2")),
                ref3=parse_date(ref_row.get("ref3")),
                contrato_codigo_origem=parse_str(ref_row.get("contrato_codigo_origem")),
            ),
            parse_decimal(row.get("valor_novo")) or Decimal("0.00"),
            parse_timestamp(row.get("created_at")),
        )
        for row in dump.table_rows("refinanciamento_ajustes_valor")
        for ref_row in dump.table_rows("refinanciamentos")
        if parse_int(ref_row.get("id")) == parse_int(row.get("refinanciamento_id"))
    ]
    sections["refinanciamento_ajustes_valor"] = _build_section_report(
        name="refinanciamento_ajustes_valor",
        source_rows=ajuste_valor_source_rows,
        actual_rows=[
            _serialize_key(
                _refinanciamento_key(
                    cpf_cnpj=cpf_cnpj_snapshot or associado_cpf,
                    cycle_key=cycle_key,
                    ref1=ref1,
                    ref2=ref2,
                    ref3=ref3,
                    contrato_codigo_origem=contrato_codigo_origem,
                ),
                valor_novo,
                created_at,
            )
            for associado_cpf, cpf_cnpj_snapshot, cycle_key, ref1, ref2, ref3, contrato_codigo_origem, valor_novo, created_at in AjusteValor.objects.filter(
                refinanciamento__associado__cpf_cnpj__in=refinanciamento_cpfs
            )
            .order_by("created_at", "id")
            .values_list(
                "refinanciamento__associado__cpf_cnpj",
                "refinanciamento__cpf_cnpj_snapshot",
                "refinanciamento__cycle_key",
                "refinanciamento__ref1",
                "refinanciamento__ref2",
                "refinanciamento__ref3",
                "refinanciamento__contrato_codigo_origem",
                "valor_novo",
                "created_at",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamento_ajustes_valor"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamento_ajustes_valor"],
    )

    comprovante_source_rows = []
    ref_rows_by_id = {
        parse_int(row.get("id")): row
        for row in dump.table_rows("refinanciamentos")
        if parse_int(row.get("id")) is not None
    }
    for row in dump.table_rows("refinanciamento_comprovantes"):
        ref_row = ref_rows_by_id.get(parse_int(row.get("refinanciamento_id")))
        if ref_row is None:
            continue
        ref_key = _refinanciamento_key(
            cpf_cnpj=only_digits(parse_str(ref_row.get("cpf_cnpj"))),
            cycle_key=parse_str(ref_row.get("cycle_key")),
            ref1=parse_date(ref_row.get("ref1")),
            ref2=parse_date(ref_row.get("ref2")),
            ref3=parse_date(ref_row.get("ref3")),
            contrato_codigo_origem=parse_str(ref_row.get("contrato_codigo_origem")),
        )
        comprovante_source_rows.append(
            _serialize_key(ref_key, parse_str(row.get("path")))
        )
    sections["refinanciamento_comprovantes"] = _build_section_report(
        name="refinanciamento_comprovantes",
        source_rows=comprovante_source_rows,
        actual_rows=[
            _serialize_key(
                _refinanciamento_key(
                    cpf_cnpj=cpf_cnpj_snapshot or associado_cpf,
                    cycle_key=cycle_key,
                    ref1=ref1,
                    ref2=ref2,
                    ref3=ref3,
                    contrato_codigo_origem=contrato_codigo_origem,
                ),
                arquivo,
            )
            for associado_cpf, cpf_cnpj_snapshot, cycle_key, ref1, ref2, ref3, contrato_codigo_origem, arquivo in RefinanciamentoComprovante.objects.filter(
                refinanciamento__associado__cpf_cnpj__in=refinanciamento_cpfs
            )
            .order_by("id")
            .values_list(
                "refinanciamento__associado__cpf_cnpj",
                "refinanciamento__cpf_cnpj_snapshot",
                "refinanciamento__cycle_key",
                "refinanciamento__ref1",
                "refinanciamento__ref2",
                "refinanciamento__ref3",
                "refinanciamento__contrato_codigo_origem",
                "arquivo",
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamento_comprovantes"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamento_comprovantes"],
    )

    pagamento_rows_by_id = {
        parse_int(row.get("id")): row
        for row in dump.table_rows("pagamentos_mensalidades")
        if parse_int(row.get("id")) is not None
    }
    tes_pag_rows_by_id = {
        parse_int(row.get("id")): row
        for row in dump.table_rows("tesouraria_pagamentos")
        if parse_int(row.get("id")) is not None
    }
    refi_item_source_rows = []
    for row in dump.table_rows("refinanciamento_itens"):
        ref_row = ref_rows_by_id.get(parse_int(row.get("refinanciamento_id")))
        if ref_row is None:
            continue
        ref_key = _refinanciamento_key(
            cpf_cnpj=only_digits(parse_str(ref_row.get("cpf_cnpj"))),
            cycle_key=parse_str(ref_row.get("cycle_key")),
            ref1=parse_date(ref_row.get("ref1")),
            ref2=parse_date(ref_row.get("ref2")),
            ref3=parse_date(ref_row.get("ref3")),
            contrato_codigo_origem=parse_str(ref_row.get("contrato_codigo_origem")),
        )
        pagamento_row = pagamento_rows_by_id.get(parse_int(row.get("pagamento_mensalidade_id")))
        tes_pagamento_row = tes_pag_rows_by_id.get(parse_int(row.get("tesouraria_pagamento_id")))
        pagamento_key = (
            _serialize_key(
                only_digits(parse_str(pagamento_row.get("cpf_cnpj"))),
                parse_date(pagamento_row.get("referencia_month")),
            )
            if pagamento_row
            else None
        )
        tes_pagamento_key = (
            _serialize_key(
                only_digits(parse_str(tes_pagamento_row.get("cpf_cnpj"))),
                parse_str(tes_pagamento_row.get("contrato_codigo_contrato"))[:80],
                parse_timestamp(tes_pagamento_row.get("paid_at")),
                parse_decimal(tes_pagamento_row.get("valor_pago")),
            )
            if tes_pagamento_row
            else None
        )
        refi_item_source_rows.append(
            _serialize_key(
                ref_key,
                pagamento_key,
                tes_pagamento_key,
                parse_date(row.get("referencia_month")),
            )
        )
    sections["refinanciamento_itens"] = _build_section_report(
        name="refinanciamento_itens",
        source_rows=refi_item_source_rows,
        actual_rows=[
            _serialize_key(
                _refinanciamento_key(
                    cpf_cnpj=cpf_cnpj_snapshot or associado_cpf,
                    cycle_key=cycle_key,
                    ref1=ref1,
                    ref2=ref2,
                    ref3=ref3,
                    contrato_codigo_origem=contrato_codigo_origem,
                ),
                pagamento_key,
                tes_pagamento_key,
                referencia_month,
            )
            for associado_cpf, cpf_cnpj_snapshot, cycle_key, ref1, ref2, ref3, contrato_codigo_origem, pagamento_key, tes_pagamento_key, referencia_month in (
                (
                    item.refinanciamento.associado.cpf_cnpj,
                    item.refinanciamento.cpf_cnpj_snapshot,
                    item.refinanciamento.cycle_key,
                    item.refinanciamento.ref1,
                    item.refinanciamento.ref2,
                    item.refinanciamento.ref3,
                    item.refinanciamento.contrato_codigo_origem,
                    (
                        _serialize_key(
                            item.pagamento_mensalidade.cpf_cnpj,
                            item.pagamento_mensalidade.referencia_month,
                        )
                        if item.pagamento_mensalidade_id
                        else None
                    ),
                    (
                        _serialize_key(
                            item.tesouraria_pagamento.cpf_cnpj,
                            item.tesouraria_pagamento.contrato_codigo,
                            item.tesouraria_pagamento.paid_at,
                            item.tesouraria_pagamento.valor_pago,
                        )
                        if item.tesouraria_pagamento_id
                        else None
                    ),
                    item.referencia_month,
                )
                for item in RefinanciamentoItem.objects.filter(refinanciamento__associado__cpf_cnpj__in=refinanciamento_cpfs)
                .select_related("refinanciamento", "pagamento_mensalidade", "tesouraria_pagamento", "refinanciamento__associado")
                .order_by("id")
            )
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamento_itens"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamento_itens"],
    )

    solicitacao_source_rows = [
        _refinanciamento_key(
            cpf_cnpj=only_digits(parse_str(row.get("cpf_cnpj"))),
            cycle_key=parse_str(row.get("cycle_key")),
            ref1=parse_date(row.get("ref1")),
            ref2=parse_date(row.get("ref2")),
            ref3=parse_date(row.get("ref3")),
            contrato_codigo_origem=parse_str(row.get("contrato_codigo_origem")),
        )
        for row in dump.table_rows("refinanciamento_solicitacoes")
        if only_digits(parse_str(row.get("cpf_cnpj")))
    ]
    solicitacao_source_keyset = set(solicitacao_source_rows)
    sections["refinanciamento_solicitacoes"] = _build_section_report(
        name="refinanciamento_solicitacoes",
        source_rows=solicitacao_source_rows,
        actual_rows=[
            key
            for key in (
                _refinanciamento_key(
                    cpf_cnpj=cpf_cnpj_snapshot or associado_cpf,
                    cycle_key=cycle_key,
                    ref1=ref1,
                    ref2=ref2,
                    ref3=ref3,
                    contrato_codigo_origem=contrato_codigo_origem,
                )
                for associado_cpf, cpf_cnpj_snapshot, cycle_key, ref1, ref2, ref3, contrato_codigo_origem in Refinanciamento.objects.filter(
                    associado__cpf_cnpj__in=refinanciamento_cpfs
                )
                .order_by("id")
                .values_list(
                    "associado__cpf_cnpj",
                    "cpf_cnpj_snapshot",
                    "cycle_key",
                    "ref1",
                    "ref2",
                    "ref3",
                    "contrato_codigo_origem",
                )
            )
            if key in solicitacao_source_keyset
        ],
        expected_source_rows=EXPECTED_COUNTS["refinanciamento_solicitacoes"],
        expected_db_rows=EXPECTED_COUNTS["refinanciamento_solicitacoes"],
    )

    competencia_conflicts = sum(1 for count in competencia_counter.values() if count > 1)

    summary = {
        "roles": sections["roles"]["source_rows"],
        "users_operacionais": sections["users_operacionais"]["source_rows"],
        "agente_cadastros": sections["associados"]["source_rows"],
        "associados": sections["associados"]["actual_rows"],
        "cpf_duplicado_consolidado": sections["associados"]["source_duplicate_rows"],
        "associado_users": sections["associado_users"]["actual_rows"],
        "contratos": sections["contratos"]["actual_rows"],
        "ciclos": sections["ciclos"]["actual_rows"],
        "parcelas": sections["parcelas"]["actual_rows"],
        "documentos": sections["documentos"]["actual_rows"],
        "agente_cadastro_assumptions": sections["agente_cadastro_assumptions"]["source_rows"],
        "agente_doc_issues": sections["agente_doc_issues"]["source_rows"],
        "agente_doc_reuploads": sections["agente_doc_reuploads"]["source_rows"],
        "agente_margens": sections["agente_margens"]["source_rows"],
        "agente_margem_historicos": sections["agente_margem_historicos"]["source_rows"],
        "agente_margem_snapshots": sections["agente_margem_snapshots"]["source_rows"],
        "despesas": sections["despesas"]["source_rows"],
        "pagamentos_mensalidades": sections["pagamentos_mensalidades"]["source_rows"],
        "tesouraria_confirmacoes": sections["tesouraria_confirmacoes"]["source_rows"],
        "tesouraria_pagamentos": sections["tesouraria_pagamentos"]["source_rows"],
        "refinanciamentos": sections["refinanciamentos"]["source_rows"],
        "refinanciamento_assumptions": sections["refinanciamento_assumptions"]["source_rows"],
        "refinanciamento_ajustes_valor": sections["refinanciamento_ajustes_valor"]["source_rows"],
        "refinanciamento_comprovantes": sections["refinanciamento_comprovantes"]["source_rows"],
        "refinanciamento_itens": sections["refinanciamento_itens"]["source_rows"],
        "refinanciamento_solicitacoes": sections["refinanciamento_solicitacoes"]["source_rows"],
        "competencia_conflicts": competencia_conflicts,
    }

    mismatches: list[str] = []
    for name, section in sections.items():
        if section["ok"]:
            continue
        mismatches.append(
            (
                f"{name}: source_rows={section['source_rows']}/{section['expected_source_rows']} "
                f"actual_rows={section['actual_rows']}/{section['expected_db_rows']} "
                f"missing={section['missing_keys_count']} unexpected={section['unexpected_keys_count']}"
            )
        )
    if competencia_conflicts != 0:
        mismatches.append(
            f"competencia_conflicts: actual={competencia_conflicts}/0"
        )

    status = SUCCESS_STATUS if not mismatches else "divergências"
    return {
        "status": status,
        "generated_at": timezone.localtime().replace(microsecond=0).isoformat(),
        "dry_run": dry_run,
        "source_file": str(dump_path),
        "summary": summary,
        "sections": sections,
        "business_reference_backfill": business_reference_backfill or {},
        "phases": phases or {},
        "mismatches": mismatches,
    }
