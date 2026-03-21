from __future__ import annotations

from collections import Counter
from contextlib import nullcontext
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.legacy_helpers import map_refi_status
from apps.associados.models import Associado, only_digits
from apps.contratos.models import Contrato
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


COMPLEMENT_TABLES = (
    "agente_margens",
    "agente_cadastro_assumptions",
    "agente_doc_issues",
    "agente_doc_reuploads",
    "agente_margem_historicos",
    "agente_margem_snapshots",
    "despesas",
    "pagamentos_mensalidades",
    "tesouraria_confirmacoes",
    "tesouraria_pagamentos",
    "refinanciamentos",
    "refinanciamento_assumptions",
    "refinanciamento_ajustes_valor",
    "refinanciamento_comprovantes",
    "refinanciamento_itens",
    "refinanciamento_solicitacoes",
)

EPOCH_DATE = date(1970, 1, 1)
EPOCH_DATETIME = timezone.make_aware(datetime.combine(EPOCH_DATE, time.min))


class Command(BaseCommand):
    help = (
        "Importa as tabelas complementares do legado para o schema canônico "
        "após a materialização de associados/contratos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            required=True,
            help="Caminho para o dump SQL legado.",
        )
        parser.add_argument(
            "--tables",
            nargs="*",
            choices=COMPLEMENT_TABLES,
            default=COMPLEMENT_TABLES,
            help="Quais tabelas complementares importar.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa em transação revertida ao final.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        dump = LegacyDump.from_file(dump_path)
        self._ensure_runtime_state()
        self._bootstrap_maps(dump)

        summary: dict[str, dict[str, int]] = {}
        context = transaction.atomic() if options["dry_run"] else nullcontext()
        with context:
            for table_name in COMPLEMENT_TABLES:
                if table_name not in options["tables"]:
                    continue
                rows = dump.table_rows(table_name)
                table_summary = {
                    "source_rows": len(rows),
                    "created": 0,
                    "updated": 0,
                    "processed": 0,
                    "skipped": 0,
                }
                getattr(self, f"_import_{table_name}")(rows, table_summary)
                summary[table_name] = table_summary
                self.stdout.write(
                    f"  {table_name}: source={table_summary['source_rows']} "
                    f"processed={table_summary['processed']} created={table_summary['created']} "
                    f"updated={table_summary['updated']} skipped={table_summary['skipped']}"
                )

            if options["dry_run"]:
                transaction.set_rollback(True)

        self.summary = summary

    def _ensure_runtime_state(self):
        self._user_map: dict[int, int] = {}
        self._cad_map: dict[int, int] = {}
        self._associadodois_map: dict[int, int] = {}
        self._associadodois_rows: dict[int, dict[str, str]] = {}
        self._legacy_cad_contract_codes: dict[int, str] = {}
        self._esteira_map: dict[int, int] = {}
        self._doc_issue_map: dict[int, int] = {}
        self._pag_map: dict[int, int] = {}
        self._tes_pag_map: dict[int, int] = {}
        self._refi_map: dict[int, int] = {}
        self._margem_snapshot_occurrences: Counter[tuple[object, ...]] = Counter()

    def _bootstrap_maps(self, dump: LegacyDump):
        self._bootstrap_user_map(dump.table_rows("users"))
        self._bootstrap_associado_map(dump.table_rows("agente_cadastros"))
        self._bootstrap_associadodois_map(dump.table_rows("associadodois_cadastros"))
        self._bootstrap_esteira_map()
        self._bootstrap_doc_issue_map(dump.table_rows("agente_doc_issues"))
        self._bootstrap_pagamento_map(dump.table_rows("pagamentos_mensalidades"))
        self._bootstrap_tesouraria_pagamento_map(dump.table_rows("tesouraria_pagamentos"))
        self._bootstrap_refinanciamento_map(dump.table_rows("refinanciamentos"))

    def _bootstrap_user_map(self, rows: list[dict[str, str]]):
        user_model = get_user_model()
        for row in rows:
            legacy_user_id = parse_int(row.get("id"))
            email = parse_str(row.get("email"))
            if legacy_user_id is None or not email:
                continue
            user = user_model.all_objects.filter(email__iexact=email).only("id").first()
            if user:
                self._user_map[legacy_user_id] = user.pk

    def _bootstrap_associado_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            contract_code = parse_str(row.get("contrato_codigo_contrato"))[:40]
            if legacy_id is None or not cpf_cnpj:
                continue
            associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).only("id").first()
            if associado:
                self._cad_map[legacy_id] = associado.pk
                self._legacy_cad_contract_codes[legacy_id] = contract_code

    def _bootstrap_associadodois_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            if legacy_id is None:
                continue
            self._associadodois_rows[legacy_id] = row
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            if not cpf_cnpj:
                continue
            associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).only("id").first()
            if associado:
                self._associadodois_map[legacy_id] = associado.pk

    def _bootstrap_esteira_map(self):
        for legacy_cad_id, associado_id in self._cad_map.items():
            esteira = (
                EsteiraItem.all_objects.filter(associado_id=associado_id)
                .only("id")
                .first()
            )
            if esteira:
                self._esteira_map[legacy_cad_id] = esteira.pk

    def _bootstrap_doc_issue_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            associado_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            analista_id = self._user_map.get(parse_int(row.get("analista_id")))
            created_at = parse_timestamp(row.get("created_at"))
            if legacy_id is None or not associado_id or not analista_id:
                continue
            queryset = DocIssue.all_objects.filter(
                associado_id=associado_id,
                contrato_codigo=parse_str(row.get("contrato_codigo_contrato")),
                analista_id=analista_id,
                mensagem=parse_str(row.get("mensagem")),
            )
            if created_at:
                queryset = queryset.filter(created_at=created_at)
            issue = queryset.only("id").first()
            if issue:
                self._doc_issue_map[legacy_id] = issue.pk

    def _bootstrap_pagamento_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            referencia_month = parse_date(row.get("referencia_month"))
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            if legacy_id is None or not referencia_month or not cpf_cnpj:
                continue
            pagamento = (
                PagamentoMensalidade.all_objects.filter(
                    cpf_cnpj=cpf_cnpj,
                    referencia_month=referencia_month,
                )
                .only("id")
                .first()
            )
            if pagamento:
                self._pag_map[legacy_id] = pagamento.pk

    def _bootstrap_tesouraria_pagamento_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            if legacy_id is None:
                continue
            pagamento = self._find_tesouraria_pagamento(row)
            if pagamento:
                self._tes_pag_map[legacy_id] = pagamento.pk

    def _bootstrap_refinanciamento_map(self, rows: list[dict[str, str]]):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            if legacy_id is None:
                continue
            refinanciamento = self._find_refinanciamento(row)
            if refinanciamento:
                self._refi_map[legacy_id] = refinanciamento.pk

    def _fallback_user_id(self) -> int | None:
        user_model = get_user_model()
        user = user_model.all_objects.filter(is_active=True).order_by("id").only("id").first()
        return user.pk if user else None

    def _sync_timestamps(self, model_class, obj_id: int, row: dict[str, str]):
        created_at = parse_timestamp(row.get("created_at"))
        updated_at = parse_timestamp(row.get("updated_at"))
        updates: dict[str, object] = {}
        if created_at:
            updates["created_at"] = created_at
        if updated_at:
            updates["updated_at"] = updated_at
        elif created_at:
            updates["updated_at"] = created_at
        if updates:
            model_class.all_objects.filter(pk=obj_id).update(**updates)

    def _fallback_date(self, *values: object) -> date:
        for value in values:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
        return EPOCH_DATE

    def _competencia_from_timestamp(self, *values: object) -> date:
        chosen = self._fallback_date(*values)
        return chosen.replace(day=1)

    def _resolve_associado_id(
        self,
        legacy_cadastro_id: int | None,
        legacy_associadodois_id: int | None = None,
    ) -> int | None:
        associado_id = self._cad_map.get(legacy_cadastro_id)
        if associado_id:
            return associado_id
        associado_id = self._associadodois_map.get(legacy_associadodois_id)
        if associado_id:
            return associado_id
        if legacy_associadodois_id is None:
            return None
        return self._ensure_auxiliary_associado(legacy_associadodois_id)

    def _ensure_auxiliary_associado(self, legacy_associadodois_id: int) -> int | None:
        row = self._associadodois_rows.get(legacy_associadodois_id)
        if not row:
            return None
        cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
        if not cpf_cnpj:
            return None

        associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).first()
        if associado is None:
            associado = Associado.objects.create(
                tipo_documento=(
                    Associado.TipoDocumento.CNPJ
                    if parse_str(row.get("doc_type")).upper() == Associado.TipoDocumento.CNPJ
                    else Associado.TipoDocumento.CPF
                ),
                nome_completo=parse_str(row.get("full_name"))[:255] or cpf_cnpj,
                cpf_cnpj=cpf_cnpj,
                email=parse_str(row.get("email"))[:254],
                telefone=parse_str(row.get("cellphone"))[:30],
                observacao=(
                    "Cadastro auxiliar importado de associadodois_cadastros para "
                    "reconciliar dados complementares do legado."
                ),
            )
            self._sync_timestamps(Associado, associado.pk, row)

        self._associadodois_map[legacy_associadodois_id] = associado.pk
        self._legacy_cad_contract_codes.setdefault(
            legacy_associadodois_id,
            parse_str(row.get("contrato_codigo_contrato"))[:40],
        )
        return associado.pk

    def _ensure_esteira_item(self, associado_id: int, row: dict[str, str]) -> EsteiraItem:
        esteira = EsteiraItem.all_objects.filter(associado_id=associado_id).first()
        if esteira:
            return esteira
        esteira = EsteiraItem.objects.create(
            associado_id=associado_id,
            etapa_atual=EsteiraItem.Etapa.ANALISE,
            status=EsteiraItem.Situacao.AGUARDANDO,
        )
        self._sync_timestamps(EsteiraItem, esteira.pk, row)
        return esteira

    def _synthetic_doc_issue_message(self, row: dict[str, str]) -> str:
        legacy_issue_id = parse_int(row.get("agente_doc_issue_id"))
        prefix = (
            f"[legacy-missing-issue:{legacy_issue_id}]"
            if legacy_issue_id is not None
            else "[legacy-missing-issue]"
        )
        note = "Reupload legado sem issue original."
        return f"{prefix} {note}".strip()

    def _ensure_doc_issue_for_reupload(
        self,
        row: dict[str, str],
        associado_id: int | None,
    ) -> int | None:
        legacy_issue_id = parse_int(row.get("agente_doc_issue_id"))
        if legacy_issue_id is None:
            return None
        mapped_issue_id = self._doc_issue_map.get(legacy_issue_id)
        if mapped_issue_id:
            return mapped_issue_id
        if not associado_id:
            return None

        analista_id = self._user_map.get(parse_int(row.get("uploaded_by_user_id")))
        if not analista_id:
            return None

        created_at = parse_timestamp(row.get("created_at")) or parse_timestamp(row.get("uploaded_at"))
        lookup = {
            "associado_id": associado_id,
            "contrato_codigo": parse_str(row.get("contrato_codigo_contrato"))[:80],
            "analista_id": analista_id,
            "mensagem": self._synthetic_doc_issue_message(row),
        }
        if created_at:
            lookup["created_at"] = created_at

        defaults = {
            "cpf_cnpj": only_digits(parse_str(row.get("cpf_cnpj"))),
            "status": (
                DocIssue.Status.RESOLVIDO
                if parse_str(row.get("status")) == DocReupload.Status.ACEITO
                else DocIssue.Status.INCOMPLETO
            ),
            "documents_snapshot_json": None,
            "agent_uploads_json": parse_json(row.get("extras")),
        }
        obj = DocIssue.all_objects.filter(**lookup).first()
        if obj is None:
            obj = DocIssue.objects.create(**lookup, **defaults)
        else:
            self._apply_updates(obj, defaults)
        self._sync_timestamps(DocIssue, obj.pk, row)
        self._doc_issue_map[legacy_issue_id] = obj.pk
        return obj.pk

    def _resolve_contrato(self, legacy_cadastro_id: int | None):
        associado_id = self._cad_map.get(legacy_cadastro_id)
        if not associado_id:
            return None
        contract_code = self._legacy_cad_contract_codes.get(legacy_cadastro_id) or ""
        if contract_code:
            contrato = Contrato.all_objects.filter(codigo=contract_code).first()
            if contrato:
                return contrato
        return (
            Contrato.all_objects.filter(associado_id=associado_id)
            .order_by("-created_at", "-id")
            .first()
        )

    def _orphan_confirmacao_contract_code(self, legacy_cadastro_id: int) -> str:
        return f"LEGACY-CONF-{legacy_cadastro_id}"[:40]

    def _ensure_orphan_confirmacao_contract(
        self,
        legacy_cadastro_id: int,
        row: dict[str, str],
    ):
        contract_code = self._orphan_confirmacao_contract_code(legacy_cadastro_id)
        contrato = Contrato.all_objects.filter(codigo=contract_code).first()
        if contrato:
            return contrato

        associado_key = f"LEGACYCONF{legacy_cadastro_id:06d}"[:18]
        associado = Associado.all_objects.filter(cpf_cnpj=associado_key).first()
        if associado is None:
            associado = Associado.objects.create(
                tipo_documento=Associado.TipoDocumento.CPF,
                nome_completo=f"Cadastro legado órfão {legacy_cadastro_id}",
                cpf_cnpj=associado_key,
                observacao=(
                    "Cadastro auxiliar sintetizado para reconciliar "
                    "tesouraria_confirmacoes sem agente_cadastro origem."
                ),
            )
            self._sync_timestamps(Associado, associado.pk, row)

        created_at = parse_timestamp(row.get("created_at"))
        contrato = Contrato.objects.create(
            associado=associado,
            codigo=contract_code,
            status=Contrato.Status.EM_ANALISE,
            data_contrato=(created_at.date() if created_at else timezone.localdate()),
            data_aprovacao=(created_at.date() if created_at else None),
        )
        self._sync_timestamps(Contrato, contrato.pk, row)
        return contrato

    def _find_tesouraria_pagamento(self, row: dict[str, str]):
        paid_at = parse_timestamp(row.get("paid_at"))
        return (
            Pagamento.all_objects.filter(
                cpf_cnpj=only_digits(parse_str(row.get("cpf_cnpj"))),
                contrato_codigo=parse_str(row.get("contrato_codigo_contrato"))[:80],
                paid_at=paid_at,
                valor_pago=parse_decimal(row.get("valor_pago")),
            )
            .only("id")
            .first()
        )

    def _refinanciamento_lookup_filters(self, row: dict[str, str]) -> dict[str, object]:
        return {
            "cpf_cnpj_snapshot": only_digits(parse_str(row.get("cpf_cnpj"))),
            "cycle_key": parse_str(row.get("cycle_key")),
            "ref1": parse_date(row.get("ref1")),
            "ref2": parse_date(row.get("ref2")),
            "ref3": parse_date(row.get("ref3")),
            "contrato_codigo_origem": parse_str(row.get("contrato_codigo_origem"))[:80],
        }

    def _find_refinanciamento(self, row: dict[str, str]):
        legacy_id = parse_int(row.get("id"))
        if legacy_id is not None:
            existing = (
                Refinanciamento.all_objects.filter(legacy_refinanciamento_id=legacy_id)
                .order_by("created_at", "id")
                .only("id")
                .first()
            )
            if existing is not None:
                return existing
        filters = self._refinanciamento_lookup_filters(row)
        return (
            Refinanciamento.all_objects.filter(**filters)
            .order_by("created_at", "id")
            .only("id")
            .first()
        )

    def _next_month_start(
        self,
        value: datetime | None,
        *,
        ref1: date | None = None,
        ref2: date | None = None,
        ref3: date | None = None,
        ref4: date | None = None,
    ) -> date:
        origin_refs = sorted(
            reference for reference in [ref1, ref2, ref3, ref4] if reference is not None
        )
        if origin_refs:
            last_reference = origin_refs[-1].replace(day=1)
            month_index = last_reference.month
            year = last_reference.year
            if month_index == 12:
                return date(year + 1, 1, 1)
            return date(year, month_index + 1, 1)
        base = (value.date() if value else timezone.localdate()).replace(day=1)
        return base

    def _legacy_storage_name(self, path: str, *, legacy_id: int | None) -> str:
        normalized = path.strip()
        if len(normalized) <= 100:
            return normalized
        suffix = Path(normalized).name[-60:]
        if legacy_id is None:
            return f"legacy/{suffix}"[:100]
        return f"legacy/{legacy_id}-{suffix}"[:100]

    def _apply_updates(self, obj, defaults: dict[str, object]) -> int:
        update_fields: list[str] = []
        for field_name, value in defaults.items():
            if getattr(obj, field_name) != value:
                setattr(obj, field_name, value)
                update_fields.append(field_name)
        if update_fields:
            obj.save(update_fields=[*update_fields, "updated_at"])
        return len(update_fields)

    def _import_agente_margens(self, rows, summary):
        from apps.accounts.models import AgenteMargemConfig

        for row in rows:
            agente_id = self._user_map.get(parse_int(row.get("agente_user_id")))
            if not agente_id:
                summary["skipped"] += 1
                continue
            vigente_desde = parse_timestamp(row.get("vigente_desde")) or parse_timestamp(
                row.get("created_at")
            ) or EPOCH_DATETIME
            defaults = {
                "vigente_ate": parse_timestamp(row.get("vigente_ate")),
                "updated_by_id": self._user_map.get(parse_int(row.get("updated_by_user_id"))),
                "motivo": parse_str(row.get("motivo"))[:190],
            }
            obj, created = AgenteMargemConfig.all_objects.get_or_create(
                agente_id=agente_id,
                percentual=parse_decimal(row.get("percentual")) or Decimal("10.00"),
                vigente_desde=vigente_desde,
                defaults=defaults,
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(AgenteMargemConfig, obj.pk, row)
            summary["processed"] += 1

    def _import_agente_cadastro_assumptions(self, rows, summary):
        for row in rows:
            legacy_cad_id = parse_int(row.get("agente_cadastro_id"))
            associado_id = self._resolve_associado_id(
                legacy_cad_id,
                parse_int(row.get("associadodois_cadastro_id")),
            )
            if not associado_id:
                summary["skipped"] += 1
                continue
            esteira = self._ensure_esteira_item(associado_id, row)
            defaults = {
                "analista_responsavel_id": self._user_map.get(parse_int(row.get("analista_id"))),
                "assumido_em": parse_timestamp(row.get("assumido_em")),
                "heartbeat_at": parse_timestamp(row.get("heartbeat_at")),
            }
            if esteira.etapa_atual != EsteiraItem.Etapa.CONCLUIDO:
                defaults["etapa_atual"] = EsteiraItem.Etapa.ANALISE
                defaults["status"] = (
                    EsteiraItem.Situacao.EM_ANDAMENTO
                    if parse_str(row.get("status")) == "assumido"
                    else EsteiraItem.Situacao.AGUARDANDO
                )
            summary["updated"] += int(bool(self._apply_updates(esteira, defaults)))
            self._sync_timestamps(EsteiraItem, esteira.pk, row)
            self._esteira_map[legacy_cad_id or 0] = esteira.pk
            summary["processed"] += 1

    def _import_agente_doc_issues(self, rows, summary):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            associado_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            analista_id = self._user_map.get(parse_int(row.get("analista_id")))
            if legacy_id is None or not associado_id or not analista_id:
                summary["skipped"] += 1
                continue
            created_at = parse_timestamp(row.get("created_at"))
            lookup = {
                "associado_id": associado_id,
                "contrato_codigo": parse_str(row.get("contrato_codigo_contrato"))[:80],
                "analista_id": analista_id,
                "mensagem": parse_str(row.get("mensagem")),
            }
            if created_at:
                lookup["created_at"] = created_at
            defaults = {
                "cpf_cnpj": only_digits(parse_str(row.get("cpf_cnpj"))),
                "status": parse_str(row.get("status")) or DocIssue.Status.INCOMPLETO,
                "documents_snapshot_json": parse_json(row.get("documents_snapshot_json")),
                "agent_uploads_json": parse_json(row.get("agent_uploads_json")),
            }
            obj = DocIssue.all_objects.filter(**lookup).first()
            if obj is None:
                payload = {**lookup, **defaults}
                obj = DocIssue.objects.create(**payload)
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(DocIssue, obj.pk, row)
            self._doc_issue_map[legacy_id] = obj.pk
            summary["processed"] += 1

    def _import_agente_doc_reuploads(self, rows, summary):
        for row in rows:
            associado_id = self._resolve_associado_id(parse_int(row.get("agente_cadastro_id")))
            issue_id = self._ensure_doc_issue_for_reupload(row, associado_id)
            uploaded_at = parse_timestamp(row.get("uploaded_at"))
            if not issue_id or not associado_id:
                summary["skipped"] += 1
                continue
            defaults = {
                "uploaded_by_id": self._user_map.get(parse_int(row.get("uploaded_by_user_id"))),
                "cpf_cnpj": only_digits(parse_str(row.get("cpf_cnpj"))),
                "contrato_codigo": parse_str(row.get("contrato_codigo_contrato"))[:80],
                "file_original_name": parse_str(row.get("file_original_name"))[:255],
                "file_stored_name": parse_str(row.get("file_stored_name"))[:255],
                "file_mime": parse_str(row.get("file_mime"))[:100],
                "file_size_bytes": parse_int(row.get("file_size_bytes")),
                "status": parse_str(row.get("status")) or DocReupload.Status.RECEBIDO,
                "notes": parse_str(row.get("notes")),
                "extras": parse_json(row.get("extras")),
            }
            obj, created = DocReupload.all_objects.get_or_create(
                doc_issue_id=issue_id,
                file_relative_path=parse_str(row.get("file_relative_path"))[:500],
                uploaded_at=uploaded_at,
                defaults={
                    **defaults,
                    "associado_id": associado_id,
                },
            )
            if created:
                summary["created"] += 1
            else:
                defaults["associado_id"] = associado_id
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(DocReupload, obj.pk, row)
            summary["processed"] += 1

    def _import_agente_margem_historicos(self, rows, summary):
        from apps.accounts.models import AgenteMargemHistorico

        for row in rows:
            agente_id = self._user_map.get(parse_int(row.get("agente_user_id")))
            if not agente_id:
                summary["skipped"] += 1
                continue
            created_at = parse_timestamp(row.get("created_at"))
            lookup = {
                "agente_id": agente_id,
                "percentual_anterior": parse_decimal(row.get("percentual_anterior")),
                "percentual_novo": parse_decimal(row.get("percentual_novo")),
                "motivo": parse_str(row.get("motivo"))[:190],
            }
            if created_at:
                lookup["created_at"] = created_at
            defaults = {
                "changed_by_id": self._user_map.get(parse_int(row.get("changed_by_user_id"))),
                "meta": parse_json(row.get("meta")),
            }
            obj = AgenteMargemHistorico.all_objects.filter(**lookup).first()
            if obj is None:
                obj = AgenteMargemHistorico.objects.create(**lookup, **defaults)
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(AgenteMargemHistorico, obj.pk, row)
            summary["processed"] += 1

    def _import_agente_margem_snapshots(self, rows, summary):
        from apps.accounts.models import AgenteMargemSnapshot

        for row in rows:
            cadastro_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            agente_id = self._user_map.get(parse_int(row.get("agente_user_id")))
            if not cadastro_id or not agente_id:
                summary["skipped"] += 1
                continue
            created_at = parse_timestamp(row.get("created_at"))
            payload = {
                "cadastro_id": cadastro_id,
                "agente_id": agente_id,
                "percentual_anterior": parse_decimal(row.get("percentual_anterior")),
                "percentual_novo": parse_decimal(row.get("percentual_novo")),
                "mensalidade": parse_decimal(row.get("mensalidade")),
                "margem_disponivel": parse_decimal(row.get("margem_disponivel")),
                "auxilio_valor_anterior": parse_decimal(row.get("auxilio_valor_anterior")),
                "auxilio_valor_novo": parse_decimal(row.get("auxilio_valor_novo")),
                "changed_by_id": self._user_map.get(parse_int(row.get("changed_by_user_id"))),
                "motivo": parse_str(row.get("motivo"))[:190],
            }
            if created_at:
                payload["created_at"] = created_at

            snapshot_key = (
                payload["cadastro_id"],
                payload["agente_id"],
                payload["percentual_anterior"],
                payload["percentual_novo"],
                payload["mensalidade"],
                payload["margem_disponivel"],
                payload["auxilio_valor_anterior"],
                payload["auxilio_valor_novo"],
                payload["changed_by_id"],
                payload["motivo"],
                payload.get("created_at"),
            )
            self._margem_snapshot_occurrences[snapshot_key] += 1
            occurrence = self._margem_snapshot_occurrences[snapshot_key]
            matches = list(
                AgenteMargemSnapshot.all_objects.filter(**payload)
                .order_by("id")[:occurrence]
            )

            if len(matches) >= occurrence:
                obj = matches[occurrence - 1]
                summary["updated"] += 0
            else:
                obj = AgenteMargemSnapshot.objects.create(**payload)
                summary["created"] += 1
            self._sync_timestamps(AgenteMargemSnapshot, obj.pk, row)
            summary["processed"] += 1

    def _import_despesas(self, rows, summary):
        for row in rows:
            created_at = parse_timestamp(row.get("created_at"))
            lookup = {
                "categoria": parse_str(row.get("categoria"))[:100],
                "descricao": parse_str(row.get("descricao"))[:255],
                "valor": parse_decimal(row.get("valor")) or Decimal("0.00"),
                "data_despesa": parse_date(row.get("data_despesa"))
                or self._fallback_date(created_at),
            }
            if created_at:
                lookup["created_at"] = created_at
            defaults = {
                "user_id": self._user_map.get(parse_int(row.get("user_id"))),
                "data_pagamento": parse_date(row.get("data_pagamento")),
                "status": parse_str(row.get("status")) or Despesa.Status.PENDENTE,
                "tipo": parse_str(row.get("tipo")),
                "recorrencia": parse_str(row.get("recorrencia")) or Despesa.Recorrencia.NENHUMA,
                "recorrencia_ativa": parse_bool(row.get("recorrencia_ativa")),
                "observacoes": parse_str(row.get("observacoes")),
                "comprovantes_json": parse_json(row.get("comprovantes_json")),
            }
            obj = Despesa.all_objects.filter(**lookup).first()
            if obj is None:
                obj = Despesa.objects.create(**lookup, **defaults)
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(Despesa, obj.pk, row)
            summary["processed"] += 1

    def _import_pagamentos_mensalidades(self, rows, summary):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            referencia_month = parse_date(row.get("referencia_month"))
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            if legacy_id is None or not referencia_month or not cpf_cnpj:
                summary["skipped"] += 1
                continue
            defaults = {
                "created_by_id": self._user_map.get(parse_int(row.get("created_by_user_id"))),
                "import_uuid": parse_str(row.get("import_uuid")),
                "status_code": parse_str(row.get("status_code"))[:2],
                "matricula": parse_str(row.get("matricula"))[:40],
                "orgao_pagto": parse_str(row.get("orgao_pagto"))[:40],
                "nome_relatorio": parse_str(row.get("nome_relatorio"))[:200],
                "associado_id": self._cad_map.get(parse_int(row.get("agente_cadastro_id"))),
                "valor": parse_decimal(row.get("valor")),
                "esperado_manual": parse_decimal(row.get("esperado_manual")),
                "recebido_manual": parse_decimal(row.get("recebido_manual")),
                "manual_status": parse_str(row.get("manual_status")) or None,
                "agente_refi_solicitado": parse_bool(row.get("agente_refi_solicitado")),
                "manual_paid_at": parse_timestamp(row.get("manual_paid_at")),
                "manual_forma_pagamento": parse_str(row.get("manual_forma_pagamento"))[:40],
                "manual_comprovante_path": parse_str(row.get("manual_comprovante_path"))[:500],
                "manual_by_id": self._user_map.get(parse_int(row.get("manual_by_user_id"))),
                "source_file_path": parse_str(row.get("source_file_path"))[:500],
            }
            obj, created = PagamentoMensalidade.all_objects.update_or_create(
                cpf_cnpj=cpf_cnpj,
                referencia_month=referencia_month,
                defaults=defaults,
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += 1
            self._sync_timestamps(PagamentoMensalidade, obj.pk, row)
            self._pag_map[legacy_id] = obj.pk
            summary["processed"] += 1

    def _import_tesouraria_confirmacoes(self, rows, summary):
        for row in rows:
            legacy_cad_id = parse_int(row.get("cad_id"))
            contrato = self._resolve_contrato(legacy_cad_id)
            if contrato is None and legacy_cad_id is not None:
                contrato = self._ensure_orphan_confirmacao_contract(legacy_cad_id, row)
            if not contrato:
                summary["skipped"] += 1
                continue

            link = parse_str(row.get("link_chamada"))
            ligacao_at = parse_timestamp(row.get("ligacao_recebida_at"))
            averbacao_at = parse_timestamp(row.get("averbacao_confirmada_at"))
            created_at = parse_timestamp(row.get("created_at"))
            if parse_bool(row.get("averbacao_confirmada")):
                tipo = Confirmacao.Tipo.AVERBACAO
                status = Confirmacao.Status.CONFIRMADO
                data_confirmacao = averbacao_at
                competencia = self._competencia_from_timestamp(averbacao_at, created_at)
            elif parse_bool(row.get("ligacao_recebida")):
                tipo = Confirmacao.Tipo.LIGACAO
                status = Confirmacao.Status.CONFIRMADO
                data_confirmacao = ligacao_at
                competencia = self._competencia_from_timestamp(ligacao_at, created_at)
            else:
                tipo = Confirmacao.Tipo.LIGACAO
                status = Confirmacao.Status.PENDENTE
                data_confirmacao = None
                competencia = self._competencia_from_timestamp(created_at)

            obj, created = Confirmacao.all_objects.update_or_create(
                contrato=contrato,
                tipo=tipo,
                competencia=competencia,
                defaults={
                    "status": status,
                    "data_confirmacao": data_confirmacao,
                    "link_chamada": link,
                },
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += 1
            self._sync_timestamps(Confirmacao, obj.pk, row)
            summary["processed"] += 1

    def _import_tesouraria_pagamentos(self, rows, summary):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            cadastro_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            if legacy_id is None or not cadastro_id:
                summary["skipped"] += 1
                continue
            defaults = {
                "cadastro_id": cadastro_id,
                "created_by_id": self._user_map.get(parse_int(row.get("created_by_user_id"))),
                "contrato_valor_antecipacao": parse_decimal(row.get("contrato_valor_antecipacao")),
                "contrato_margem_disponivel": parse_decimal(row.get("contrato_margem_disponivel")),
                "full_name": parse_str(row.get("full_name"))[:200],
                "agente_responsavel": parse_str(row.get("agente_responsavel"))[:160],
                "status": parse_str(row.get("status")) or Pagamento.Status.PAGO,
                "forma_pagamento": parse_str(row.get("forma_pagamento"))[:40],
                "comprovante_path": parse_str(row.get("comprovante_path"))[:500],
                "comprovante_associado_path": parse_str(row.get("comprovante_associado_path"))[:500],
                "comprovante_agente_path": parse_str(row.get("comprovante_agente_path"))[:500],
                "notes": parse_str(row.get("notes")),
            }
            obj, created = Pagamento.all_objects.update_or_create(
                cpf_cnpj=only_digits(parse_str(row.get("cpf_cnpj"))),
                contrato_codigo=parse_str(row.get("contrato_codigo_contrato"))[:80],
                paid_at=parse_timestamp(row.get("paid_at")),
                valor_pago=parse_decimal(row.get("valor_pago")),
                defaults=defaults,
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += 1
            self._sync_timestamps(Pagamento, obj.pk, row)
            self._tes_pag_map[legacy_id] = obj.pk
            summary["processed"] += 1

    def _import_refinanciamentos(self, rows, summary):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            associado_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            if not associado_id and cpf_cnpj:
                associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).first()
                associado_id = associado.pk if associado else None
            if legacy_id is None or not associado_id:
                summary["skipped"] += 1
                continue
            created_at = parse_timestamp(row.get("created_at"))
            activation_at = created_at or parse_timestamp(row.get("executed_at"))
            contrato_origem_id = (
                Contrato.all_objects.filter(
                    codigo=parse_str(row.get("contrato_codigo_origem"))[:80]
                )
                .values_list("id", flat=True)
                .first()
            )
            defaults = {
                "associado_id": associado_id,
                "solicitado_por_id": self._user_map.get(parse_int(row.get("created_by_user_id")))
                or self._fallback_user_id(),
                "competencia_solicitada": self._next_month_start(
                    activation_at,
                    ref1=parse_date(row.get("ref1")),
                    ref2=parse_date(row.get("ref2")),
                    ref3=parse_date(row.get("ref3")),
                    ref4=parse_date(row.get("ref4")),
                ),
                "status": Refinanciamento.Status.EFETIVADO,
                "mode": parse_str(row.get("mode")) or "manual",
                "nome_snapshot": parse_str(row.get("nome_snapshot"))[:200],
                "executado_em": activation_at,
                "data_ativacao_ciclo": activation_at,
                "legacy_refinanciamento_id": legacy_id,
                "origem": Refinanciamento.Origem.LEGADO,
                "agente_snapshot": parse_str(row.get("agente_snapshot"))[:200],
                "filial_snapshot": parse_str(row.get("filial_snapshot"))[:200],
                "contrato_codigo_origem": parse_str(row.get("contrato_codigo_origem"))[:80],
                "contrato_codigo_novo": parse_str(row.get("contrato_codigo_novo"))[:80],
                "observacao": parse_str(row.get("notes")),
                "ref1": parse_date(row.get("ref1")),
                "ref2": parse_date(row.get("ref2")),
                "ref3": parse_date(row.get("ref3")),
                "ref4": parse_date(row.get("ref4")),
                "parcelas_ok": len(
                    [
                        item
                        for item in [
                            parse_date(row.get("ref1")),
                            parse_date(row.get("ref2")),
                            parse_date(row.get("ref3")),
                            parse_date(row.get("ref4")),
                        ]
                        if item is not None
                    ]
                ),
                "contrato_origem_id": contrato_origem_id,
            }
            filters = self._refinanciamento_lookup_filters(row)
            obj = self._find_refinanciamento(row)
            if obj is None:
                create_payload = {**defaults, **filters}
                obj = Refinanciamento.objects.create(**create_payload)
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(Refinanciamento, obj.pk, row)
            self._refi_map[legacy_id] = obj.pk
            summary["processed"] += 1

    def _import_refinanciamento_assumptions(self, rows, summary):
        for row in rows:
            cadastro_id = self._cad_map.get(parse_int(row.get("agente_cadastro_id")))
            request_key = parse_str(row.get("request_key"))[:80]
            if not cadastro_id or not request_key:
                summary["skipped"] += 1
                continue
            defaults = {
                "cpf_cnpj": only_digits(parse_str(row.get("cpf_cnpj"))),
                "refs_json": parse_json(row.get("refs_json")),
                "solicitado_por_id": self._user_map.get(parse_int(row.get("solicitado_por_user_id"))),
                "analista_id": self._user_map.get(parse_int(row.get("analista_id"))),
                "status": parse_str(row.get("status")) or RefinanciamentoAssumption.Status.LIBERADO,
                "solicitado_em": parse_timestamp(row.get("solicitado_em")),
                "liberado_em": parse_timestamp(row.get("liberado_em")),
                "assumido_em": parse_timestamp(row.get("assumido_em")),
                "finalizado_em": parse_timestamp(row.get("finalizado_em")),
                "heartbeat_at": parse_timestamp(row.get("heartbeat_at")),
            }
            obj, created = RefinanciamentoAssumption.all_objects.update_or_create(
                cadastro_id=cadastro_id,
                request_key=request_key,
                defaults=defaults,
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += 1
            self._sync_timestamps(RefinanciamentoAssumption, obj.pk, row)
            summary["processed"] += 1

    def _import_refinanciamento_ajustes_valor(self, rows, summary):
        for row in rows:
            refinanciamento_id = self._refi_map.get(parse_int(row.get("refinanciamento_id")))
            if not refinanciamento_id:
                summary["skipped"] += 1
                continue
            created_at = parse_timestamp(row.get("created_at"))
            lookup = {
                "refinanciamento_id": refinanciamento_id,
                "cpf_cnpj": only_digits(parse_str(row.get("cpf_cnpj"))),
                "valor_novo": parse_decimal(row.get("valor_novo")) or Decimal("0.00"),
                "origem": parse_str(row.get("origem"))[:10],
                "fonte_base": parse_str(row.get("fonte_base"))[:10],
            }
            if created_at:
                lookup["created_at"] = created_at
            defaults = {
                "valor_base": parse_decimal(row.get("valor_base")),
                "valor_antigo": parse_decimal(row.get("valor_antigo")),
                "tp_margem": parse_decimal(row.get("tp_margem")),
                "ac_margem": parse_decimal(row.get("ac_margem")),
                "a2_margem": parse_decimal(row.get("a2_margem")),
                "created_by_id": self._user_map.get(parse_int(row.get("created_by_user_id"))),
                "ip": parse_str(row.get("ip"))[:64],
                "user_agent": parse_str(row.get("user_agent"))[:255],
                "motivo": parse_str(row.get("motivo")),
                "meta": parse_json(row.get("meta")),
            }
            obj = AjusteValor.all_objects.filter(**lookup).first()
            if obj is None:
                obj = AjusteValor.objects.create(**lookup, **defaults)
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(AjusteValor, obj.pk, row)
            summary["processed"] += 1

    def _import_refinanciamento_comprovantes(self, rows, summary):
        for row in rows:
            legacy_id = parse_int(row.get("id"))
            refinanciamento_id = self._refi_map.get(parse_int(row.get("refinanciamento_id")))
            if not refinanciamento_id:
                summary["skipped"] += 1
                continue
            kind = parse_str(row.get("kind")).lower()
            refinanciamento = Refinanciamento.all_objects.filter(pk=refinanciamento_id).first()
            if "agente" in kind:
                tipo = RefinanciamentoComprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE
                papel = RefinanciamentoComprovante.Papel.AGENTE
            elif "associado" in kind:
                tipo = RefinanciamentoComprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO
                papel = RefinanciamentoComprovante.Papel.ASSOCIADO
            elif "pix" in kind:
                tipo = RefinanciamentoComprovante.Tipo.PIX
                papel = RefinanciamentoComprovante.Papel.OPERACIONAL
            elif "contrato" in kind:
                tipo = RefinanciamentoComprovante.Tipo.CONTRATO
                papel = RefinanciamentoComprovante.Papel.OPERACIONAL
            else:
                tipo = RefinanciamentoComprovante.Tipo.OUTRO
                papel = RefinanciamentoComprovante.Papel.OPERACIONAL
            defaults = {
                "contrato_id": getattr(refinanciamento, "contrato_origem_id", None),
                "ciclo_id": getattr(refinanciamento, "ciclo_destino_id", None),
                "tipo": tipo,
                "papel": papel,
                "data_pagamento": (
                    getattr(refinanciamento, "data_ativacao_ciclo", None)
                    or getattr(refinanciamento, "executado_em", None)
                    or getattr(refinanciamento, "created_at", None)
                ),
                "legacy_comprovante_id": legacy_id,
                "origem": RefinanciamentoComprovante.Origem.LEGADO,
                "nome_original": parse_str(row.get("original_name"))[:255],
                "agente_snapshot": parse_str(row.get("agente_snapshot"))[:200],
                "filial_snapshot": parse_str(row.get("filial_snapshot"))[:200],
                "enviado_por_id": self._user_map.get(parse_int(row.get("uploaded_by_user_id")))
                or self._fallback_user_id(),
            }
            arquivo_path = parse_str(row.get("path"))
            storage_name = self._legacy_storage_name(arquivo_path, legacy_id=legacy_id)
            lookup = {"refinanciamento_id": refinanciamento_id, "arquivo": storage_name}
            if legacy_id is not None:
                lookup = {"legacy_comprovante_id": legacy_id}
            obj, created = RefinanciamentoComprovante.all_objects.get_or_create(
                **lookup,
                defaults={
                    **defaults,
                    "refinanciamento_id": refinanciamento_id,
                    "arquivo": storage_name,
                    "arquivo_referencia_path": arquivo_path,
                },
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(RefinanciamentoComprovante, obj.pk, row)
            summary["processed"] += 1

    def _import_refinanciamento_itens(self, rows, summary):
        for row in rows:
            refinanciamento_id = self._refi_map.get(parse_int(row.get("refinanciamento_id")))
            if not refinanciamento_id:
                summary["skipped"] += 1
                continue
            referencia_month = parse_date(row.get("referencia_month"))
            defaults = {
                "status_code": parse_str(row.get("status_code"))[:2],
                "valor": parse_decimal(row.get("valor")),
                "import_uuid": parse_str(row.get("import_uuid"))[:36],
                "source_file_path": parse_str(row.get("source_file_path"))[:500],
            }
            obj, created = RefinanciamentoItem.all_objects.get_or_create(
                refinanciamento_id=refinanciamento_id,
                pagamento_mensalidade_id=self._pag_map.get(
                    parse_int(row.get("pagamento_mensalidade_id"))
                ),
                tesouraria_pagamento_id=self._tes_pag_map.get(
                    parse_int(row.get("tesouraria_pagamento_id"))
                ),
                referencia_month=referencia_month or EPOCH_DATE,
                defaults=defaults,
            )
            if created:
                summary["created"] += 1
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            self._sync_timestamps(RefinanciamentoItem, obj.pk, row)
            summary["processed"] += 1

    def _import_refinanciamento_solicitacoes(self, rows, summary):
        for row in rows:
            refinanciamento_id = self._refi_map.get(parse_int(row.get("refinanciamento_id")))
            cadastro_id = self._cad_map.get(parse_int(row.get("cadastro_id")))
            cpf_cnpj = only_digits(parse_str(row.get("cpf_cnpj")))
            if not cadastro_id and cpf_cnpj:
                associado = Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).first()
                cadastro_id = associado.pk if associado else None
            if not cadastro_id:
                summary["skipped"] += 1
                continue
            defaults = {
                "associado_id": cadastro_id,
                "solicitado_por_id": self._user_map.get(parse_int(row.get("created_by_user_id")))
                or self._fallback_user_id(),
                "competencia_solicitada": parse_date(row.get("ref1"))
                or self._fallback_date(parse_timestamp(row.get("created_at"))),
                "status": Refinanciamento.Status.EFETIVADO,
                "origem": Refinanciamento.Origem.LEGADO,
                "cycle_key": parse_str(row.get("cycle_key"))[:32],
                "ref1": parse_date(row.get("ref1")),
                "ref2": parse_date(row.get("ref2")),
                "ref3": parse_date(row.get("ref3")),
                "ref4": parse_date(row.get("ref4")),
                "cpf_cnpj_snapshot": cpf_cnpj,
                "nome_snapshot": parse_str(row.get("nome_snapshot"))[:200],
                "agente_snapshot": parse_str(row.get("agente_snapshot"))[:200],
                "filial_snapshot": parse_str(row.get("filial_snapshot"))[:200],
                "parcelas_ok": parse_int(row.get("parcelas_ok"))
                or len(
                    [
                        item
                        for item in [
                            parse_date(row.get("ref1")),
                            parse_date(row.get("ref2")),
                            parse_date(row.get("ref3")),
                            parse_date(row.get("ref4")),
                        ]
                        if item is not None
                    ]
                ),
                "parcelas_json": parse_json(row.get("parcelas_json")),
                "analista_note": parse_str(row.get("analista_note")),
                "coordenador_note": parse_str(row.get("coordenador_note")),
                "reviewed_by_id": self._user_map.get(parse_int(row.get("reviewed_by_user_id"))),
                "reviewed_at": parse_timestamp(row.get("reviewed_at")),
                "termo_antecipacao_path": parse_str(row.get("termo_antecipacao_path"))[:255],
                "termo_antecipacao_original_name": parse_str(
                    row.get("termo_antecipacao_original_name")
                )[:255],
                "termo_antecipacao_mime": parse_str(row.get("termo_antecipacao_mime"))[:120],
                "termo_antecipacao_size_bytes": parse_int(
                    row.get("termo_antecipacao_size_bytes")
                ),
                "termo_antecipacao_uploaded_at": parse_timestamp(
                    row.get("termo_antecipacao_uploaded_at")
                ),
                "data_ativacao_ciclo": parse_timestamp(row.get("created_at")),
                "executado_em": parse_timestamp(row.get("created_at")),
            }

            obj = None
            if refinanciamento_id:
                obj = Refinanciamento.all_objects.filter(pk=refinanciamento_id).first()

            if obj is None:
                lookup = {
                    "cpf_cnpj_snapshot": cpf_cnpj,
                    "cycle_key": parse_str(row.get("cycle_key"))[:32],
                    "ref1": parse_date(row.get("ref1")),
                    "ref2": parse_date(row.get("ref2")),
                    "ref3": parse_date(row.get("ref3")),
                    "contrato_codigo_origem": parse_str(row.get("contrato_codigo_origem"))[:80],
                }
                obj = (
                    Refinanciamento.all_objects.filter(**lookup)
                    .order_by("created_at", "id")
                    .first()
                )
                if obj is None:
                    create_payload = {**defaults, **lookup}
                    obj = Refinanciamento.objects.create(**create_payload)
                    summary["created"] += 1
                else:
                    summary["updated"] += int(bool(self._apply_updates(obj, defaults)))
            else:
                summary["updated"] += int(bool(self._apply_updates(obj, defaults)))

            self._sync_timestamps(Refinanciamento, obj.pk, row)
            summary["processed"] += 1
