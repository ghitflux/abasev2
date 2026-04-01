from __future__ import annotations

import hashlib
import json
import re
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

from apps.associados.models import Associado
from apps.contratos.models import Contrato
from apps.esteira.models import EsteiraItem
from apps.refinanciamento.models import Comprovante
from apps.tesouraria.initial_payment import get_initial_payment_for_contract
from apps.tesouraria.legacy_initial_payments import (
    LegacyInitialPaymentRecord,
    load_initial_payment_overrides,
    load_legacy_initial_payments,
    merge_initial_payment_overrides,
)
from apps.tesouraria.models import Pagamento
from core.legacy_dump import LegacyDump, default_legacy_dump_path


def _default_report_path(prefix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return (
        Path(settings.BASE_DIR)
        / "media"
        / "relatorios"
        / "legacy_import"
        / f"{prefix}_{timestamp}.json"
    )


class Command(BaseCommand):
    help = "Sincroniza pagamentos iniciais legados da tesouraria e seus anexos de efetivação."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(default_legacy_dump_path()),
            help="Dump SQL legado.",
        )
        parser.add_argument(
            "--legacy-media-root",
            default="anexos_legado",
            help="Diretório raiz do acervo legado.",
        )
        parser.add_argument(
            "--overrides",
            help="Arquivo JSON/CSV com pagamentos mais novos que o dump.",
        )
        parser.add_argument("--cpf", help="Filtra um associado específico por CPF.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica alterações no banco. Sem esta flag, executa em dry-run.",
        )
        parser.add_argument(
            "--report-json",
            dest="report_json",
            help="Caminho opcional para o relatório JSON.",
        )

    def handle(self, *args, **options):
        execute = bool(options["execute"])
        dump_path = Path(options["file"]).expanduser()
        if not dump_path.exists():
            raise CommandError(f"Arquivo SQL não encontrado: {dump_path}")

        dump = LegacyDump.from_file(dump_path)
        records = load_legacy_initial_payments(dump, cpf_filter=options.get("cpf"))
        overrides = load_initial_payment_overrides(options.get("overrides"))
        if overrides:
            records = merge_initial_payment_overrides(records, overrides)
        if not records:
            raise CommandError("Nenhum pagamento inicial legado encontrado para sincronização.")

        self._legacy_roots = self._resolve_legacy_roots(options.get("legacy_media_root"))
        self._fallback_user_id = self._resolve_fallback_user_id()
        report_rows: list[dict[str, object]] = []

        context = transaction.atomic() if not execute else nullcontext()
        with context:
            for record in records:
                report_rows.append(self._sync_record(record, execute=execute))
            if not execute:
                transaction.set_rollback(True)

        summary = {
            "mode": "execute" if execute else "dry-run",
            "records": len(report_rows),
            "synced": sum(1 for row in report_rows if row["status"] == "synced"),
            "created_pagamentos": sum(int(bool(row["created_pagamento"])) for row in report_rows),
            "copied_files": sum(int(row["copied_files"]) for row in report_rows),
            "updated_comprovantes": sum(int(row["updated_comprovantes"]) for row in report_rows),
            "placeholders": sum(1 for row in report_rows if row["evidencia_status"] == "placeholder_recebido"),
        }
        payload = {
            "generated_at": datetime.now().isoformat(),
            "legacy_file": str(dump_path),
            "legacy_media_roots": [str(path) for path in self._legacy_roots],
            "summary": summary,
            "payments": report_rows,
        }
        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("sync_legacy_initial_payments")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronizados {summary['synced']} pagamento(s) em modo {summary['mode']}."
            )
        )
        self.stdout.write(f"Relatório: {target}")

    def _resolve_fallback_user_id(self) -> int:
        user_model = get_user_model()
        manager = getattr(user_model, "all_objects", user_model.objects)
        user = manager.filter(is_active=True).order_by("id").only("id").first()
        if user is None:
            raise CommandError("Nenhum usuário ativo disponível para vincular comprovantes legados.")
        return int(user.pk)

    def _resolve_legacy_roots(self, raw_root: str | None) -> list[Path]:
        if not raw_root:
            return []
        root = Path(raw_root).expanduser()
        candidates = [
            root,
            root / "storage" / "storage" / "app" / "public",
            root / "public" / "public" / "storage",
        ]
        roots: list[Path] = []
        for candidate in candidates:
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
        return roots

    def _resolve_associado(self, record: LegacyInitialPaymentRecord) -> Associado | None:
        return (
            Associado.all_objects.filter(cpf_cnpj=record.cpf_cnpj)
            .select_related("agente_responsavel")
            .first()
        )

    def _resolve_contrato(
        self,
        record: LegacyInitialPaymentRecord,
        associado: Associado | None,
    ) -> Contrato | None:
        contrato = (
            Contrato.all_objects.filter(codigo=record.contrato_codigo)
            .select_related("associado", "agente")
            .first()
        )
        if contrato is not None:
            return contrato
        if associado is None:
            return None
        return (
            Contrato.all_objects.filter(associado=associado)
            .exclude(status=Contrato.Status.CANCELADO)
            .order_by("created_at", "id")
            .first()
        )

    def _find_pagamento(
        self,
        record: LegacyInitialPaymentRecord,
        associado: Associado | None,
    ) -> Pagamento | None:
        base = Pagamento.all_objects.filter(
            cpf_cnpj=record.cpf_cnpj,
            contrato_codigo=record.contrato_codigo,
        )
        if record.legacy_id is not None:
            legacy_lookup = Pagamento.all_objects.filter(
                legacy_tesouraria_pagamento_id=record.legacy_id,
            )
            if associado is not None:
                legacy_lookup = legacy_lookup.filter(cadastro=associado)
            found = legacy_lookup.order_by("id").first()
            if found is not None:
                return found
            found = base.filter(legacy_tesouraria_pagamento_id=record.legacy_id).first()
            if found is not None:
                return found
        if record.created_at is not None:
            found = base.filter(created_at=record.created_at).order_by("id").first()
            if found is not None:
                return found
        if record.paid_at is not None or record.valor_pago is not None:
            found = base.filter(
                paid_at=record.paid_at,
                valor_pago=record.valor_pago,
            ).order_by("id").first()
            if found is not None:
                return found
        if associado is not None:
            found = (
                Pagamento.all_objects.filter(
                    cadastro=associado,
                    contrato_codigo=record.contrato_codigo,
                )
                .order_by("created_at", "id")
                .first()
            )
            if found is not None:
                return found
            found = (
                Pagamento.all_objects.filter(
                    cadastro=associado,
                    contrato_codigo="",
                )
                .filter(
                    paid_at=record.paid_at,
                    valor_pago=record.valor_pago,
                )
                .order_by("created_at", "id")
                .first()
            )
            if found is not None:
                return found
        if base.count() == 1:
            return base.first()
        return None

    def _resolve_value(self, pagamento: Pagamento | None, record: LegacyInitialPaymentRecord):
        if record.valor_pago is not None:
            return record.valor_pago
        if pagamento and pagamento.valor_pago is not None:
            return pagamento.valor_pago
        if record.contrato_margem_disponivel is not None:
            return record.contrato_margem_disponivel
        if pagamento and pagamento.contrato_margem_disponivel is not None:
            return pagamento.contrato_margem_disponivel
        return None

    def _payment_origin(self, record: LegacyInitialPaymentRecord) -> str:
        return (
            Pagamento.Origem.OVERRIDE_MANUAL
            if record.source == "override"
            else Pagamento.Origem.LEGADO
        )

    def _reference_payload(self, record: LegacyInitialPaymentRecord) -> dict[str, object]:
        payload: dict[str, object] = {
            "payment_kind": "contrato_inicial",
        }
        if record.assoc_legacy_url:
            payload["assoc_legacy_url"] = record.assoc_legacy_url
        if record.agente_legacy_url:
            payload["agente_legacy_url"] = record.agente_legacy_url
        if record.comprovante_associado_path:
            payload["assoc_legacy_path"] = record.comprovante_associado_path
        if record.comprovante_agente_path:
            payload["agente_legacy_path"] = record.comprovante_agente_path
        if record.observacao:
            payload["observacao"] = record.observacao
        return payload

    def _resolve_relative_file(self, relative_path: str) -> tuple[str, Path | None]:
        normalized = relative_path.strip().lstrip("/")
        if not normalized:
            return "", None
        prefixes = (
            "storage/app/public/",
            "public/storage/",
            "storage/",
        )
        candidates = [normalized]
        for prefix in prefixes:
            if normalized.startswith(prefix):
                candidates.append(normalized.removeprefix(prefix))
        for root in self._legacy_roots:
            for candidate in candidates:
                resolved = root / candidate
                if resolved.exists() and resolved.is_file():
                    return candidate, resolved
        return normalized, None

    def _file_sort_key(self, path: Path):
        match = re.match(r"^(\d{8}_\d{6})", path.name)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
            except ValueError:
                pass
        return datetime.fromtimestamp(path.stat().st_mtime)

    def _classify_papel(self, path: Path) -> str | None:
        name = path.name.lower()
        if any(token in name for token in ("_assoc_", "associado", "_0_")):
            return Comprovante.Papel.ASSOCIADO
        if any(token in name for token in ("_agente_", "_agent_", "agente", "_1_")):
            return Comprovante.Papel.AGENTE
        return None

    def _discover_relative_file(
        self,
        *,
        legacy_cadastro_id: int | None,
        papel: str,
        paid_at,
    ) -> tuple[str, Path | None]:
        if legacy_cadastro_id is None:
            return "", None
        candidates: list[tuple[Path, Path]] = []
        for root in self._legacy_roots:
            folder = root / "tesouraria" / "comprovantes" / str(legacy_cadastro_id)
            if not folder.exists() or not folder.is_dir():
                continue
            for path in folder.iterdir():
                if not path.is_file():
                    continue
                classified = self._classify_papel(path)
                if classified != papel:
                    continue
                candidates.append((folder, path))
        if not candidates:
            return "", None

        cutoff = timezone.localtime(paid_at).replace(tzinfo=None) if paid_at else None
        ordered = sorted(
            candidates,
            key=lambda item: self._file_sort_key(item[1]),
            reverse=True,
        )
        if cutoff:
            before_cutoff = [
                item
                for item in ordered
                if self._file_sort_key(item[1]) <= cutoff
            ]
            if before_cutoff:
                ordered = before_cutoff
        folder, picked = ordered[0]
        relative = str(
            Path("tesouraria") / "comprovantes" / folder.name / picked.name
        )
        return relative, picked

    def _resolve_evidence_file(
        self,
        *,
        explicit_relative: str,
        legacy_cadastro_id: int | None,
        papel: str,
        paid_at,
    ) -> tuple[str, Path | None]:
        if explicit_relative:
            relative, resolved = self._resolve_relative_file(explicit_relative)
            if relative:
                return relative, resolved
        return self._discover_relative_file(
            legacy_cadastro_id=legacy_cadastro_id,
            papel=papel,
            paid_at=paid_at,
        )

    def _copy_to_storage(
        self,
        *,
        contrato_codigo: str,
        papel: str,
        source_path: Path,
    ) -> str:
        prefix = "associado" if papel == Comprovante.Papel.ASSOCIADO else "agente"
        destination = self._planned_storage_name(
            contrato_codigo=contrato_codigo,
            papel=papel,
            source_name=source_path.name,
        )
        if default_storage.exists(destination):
            return destination
        with source_path.open("rb") as handle:
            return default_storage.save(destination, File(handle, name=source_path.name))

    def _planned_storage_name(
        self,
        *,
        contrato_codigo: str,
        papel: str,
        source_name: str,
    ) -> str:
        prefix = "associado" if papel == Comprovante.Papel.ASSOCIADO else "agente"
        candidate = (
            f"refinanciamentos/efetivacao_contrato/{contrato_codigo}/"
            f"{prefix}_{get_valid_filename(source_name)}"
        )
        if len(candidate) <= 100:
            return candidate
        safe_name = get_valid_filename(source_name)
        suffix = Path(safe_name).suffix.lower()
        stem = Path(safe_name).stem[-18:]
        contract_tail = contrato_codigo[-12:]
        digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
        shortened = (
            f"refinanciamentos/efet/{contract_tail}/"
            f"{prefix}_{digest}_{stem}{suffix}"
        )
        return shortened[:100]

    def _payment_reference_at(
        self,
        *,
        record: LegacyInitialPaymentRecord,
        pagamento: Pagamento,
    ):
        return pagamento.paid_at or record.paid_at or record.created_at or pagamento.created_at

    def _stamp_timestamps(self, model, pk: int, reference_at) -> None:
        if reference_at is None:
            return
        model.all_objects.filter(pk=pk).update(
            created_at=reference_at,
            updated_at=reference_at,
        )

    def _sync_pending_contract_state(
        self,
        *,
        associado: Associado,
        contrato: Contrato,
        execute: bool,
    ) -> None:
        if contrato.status in {Contrato.Status.CANCELADO, Contrato.Status.ENCERRADO}:
            return

        contract_changed_fields: list[str] = []
        if contrato.status != Contrato.Status.EM_ANALISE:
            contrato.status = Contrato.Status.EM_ANALISE
            contract_changed_fields.append("status")
        if contrato.auxilio_liberado_em is not None:
            contrato.auxilio_liberado_em = None
            contract_changed_fields.append("auxilio_liberado_em")

        if execute and contract_changed_fields:
            contract_changed_fields.append("updated_at")
            contrato.save(update_fields=contract_changed_fields)

        associado_changed_fields: list[str] = []
        if associado.status != Associado.Status.EM_ANALISE:
            associado.status = Associado.Status.EM_ANALISE
            associado_changed_fields.append("status")

        if execute and associado_changed_fields:
            associado_changed_fields.append("updated_at")
            associado.save(update_fields=associado_changed_fields)

        esteira = associado.esteira
        if esteira is None:
            if not execute:
                return
            EsteiraItem.objects.create(
                associado=associado,
                etapa_atual=EsteiraItem.Etapa.TESOURARIA,
                status=EsteiraItem.Situacao.AGUARDANDO,
            )
            return

        esteira_changed_fields: list[str] = []
        if esteira.etapa_atual != EsteiraItem.Etapa.TESOURARIA:
            esteira.etapa_atual = EsteiraItem.Etapa.TESOURARIA
            esteira_changed_fields.append("etapa_atual")
        if esteira.status != EsteiraItem.Situacao.AGUARDANDO:
            esteira.status = EsteiraItem.Situacao.AGUARDANDO
            esteira_changed_fields.append("status")
        if esteira.concluido_em is not None:
            esteira.concluido_em = None
            esteira_changed_fields.append("concluido_em")

        if execute and esteira_changed_fields:
            esteira_changed_fields.append("updated_at")
            esteira.save(update_fields=esteira_changed_fields)

    def _upsert_contract_comprovante(
        self,
        *,
        contrato: Contrato,
        pagamento: Pagamento,
        record: LegacyInitialPaymentRecord,
        papel: str,
        legacy_reference_path: str,
        stored_path: str,
    ) -> int:
        tipo = (
            Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO
            if papel == Comprovante.Papel.ASSOCIADO
            else Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE
        )
        defaults = {
            "ciclo": contrato.ciclos.order_by("numero", "id").first(),
            "arquivo": stored_path,
            "arquivo_referencia_path": legacy_reference_path or stored_path,
            "nome_original": Path(legacy_reference_path or stored_path).name,
            "data_pagamento": pagamento.paid_at,
            "enviado_por_id": self._fallback_user_id,
            "agente_snapshot": contrato.agente.full_name if contrato.agente else "",
        }
        lookup = {
            "contrato": contrato,
            "refinanciamento": None,
            "papel": papel,
            "tipo": tipo,
            "origem": Comprovante.Origem.EFETIVACAO_CONTRATO,
        }
        obj = Comprovante.all_objects.filter(**lookup).first()
        if obj is None:
            obj = Comprovante.objects.create(**lookup, **defaults)
            self._stamp_timestamps(
                Comprovante,
                obj.pk,
                self._payment_reference_at(record=record, pagamento=pagamento),
            )
            return 1
        changed = False
        for field_name, value in defaults.items():
            if getattr(obj, field_name) != value:
                setattr(obj, field_name, value)
                changed = True
        if changed:
            obj.save()
        self._stamp_timestamps(
            Comprovante,
            obj.pk,
            self._payment_reference_at(record=record, pagamento=pagamento),
        )
        return 1 if changed else 0

    def _sync_record(self, record: LegacyInitialPaymentRecord, *, execute: bool) -> dict[str, object]:
        associado = self._resolve_associado(record)
        contrato = self._resolve_contrato(record, associado)
        if associado is None or contrato is None:
            return {
                "legacy_payment_id": record.legacy_id,
                "cpf_cnpj": record.cpf_cnpj,
                "contrato_codigo": record.contrato_codigo,
                "status": "skipped_not_found",
                "created_pagamento": False,
                "copied_files": 0,
                "updated_comprovantes": 0,
                "evidencia_status": "",
            }

        pagamento = self._find_pagamento(record, associado)
        created_pagamento = False
        if pagamento is None:
            pagamento = Pagamento.objects.create(
                cadastro=associado,
                created_by_id=self._fallback_user_id,
                contrato_codigo=contrato.codigo,
                contrato_valor_antecipacao=contrato.valor_liquido or contrato.valor_total_antecipacao,
                contrato_margem_disponivel=record.contrato_margem_disponivel or contrato.margem_disponivel,
                cpf_cnpj=record.cpf_cnpj,
                full_name=associado.nome_completo,
                agente_responsavel=contrato.agente.full_name if contrato.agente else "",
                status=record.status or Pagamento.Status.PENDENTE,
                valor_pago=self._resolve_value(None, record),
                paid_at=record.paid_at,
                forma_pagamento=record.forma_pagamento,
                notes=record.notes,
                legacy_tesouraria_pagamento_id=record.legacy_id,
                origem=self._payment_origin(record),
                referencias_externas={
                    **self._reference_payload(record),
                    "contrato_id": contrato.id,
                },
            )
            created_pagamento = True

        pagamento.status = record.status or pagamento.status
        pagamento.cadastro = associado
        pagamento.contrato_codigo = contrato.codigo
        pagamento.contrato_valor_antecipacao = (
            contrato.valor_liquido or contrato.valor_total_antecipacao
        )
        pagamento.legacy_tesouraria_pagamento_id = record.legacy_id
        pagamento.origem = self._payment_origin(record)
        pagamento.full_name = associado.nome_completo
        pagamento.agente_responsavel = contrato.agente.full_name if contrato.agente else ""
        pagamento.forma_pagamento = record.forma_pagamento or pagamento.forma_pagamento
        pagamento.notes = record.notes or pagamento.notes
        pagamento.valor_pago = self._resolve_value(pagamento, record)
        if record.status == Pagamento.Status.PENDENTE:
            pagamento.paid_at = None
        elif record.paid_at is not None:
            pagamento.paid_at = record.paid_at
        if record.contrato_margem_disponivel is not None:
            pagamento.contrato_margem_disponivel = record.contrato_margem_disponivel
        pagamento.referencias_externas = {
            **(pagamento.referencias_externas or {}),
            "payment_kind": "contrato_inicial",
            "contrato_id": contrato.id,
            **self._reference_payload(record),
        }

        copied_files = 0
        updated_comprovantes = 0
        for papel, field_name in [
            (Comprovante.Papel.ASSOCIADO, "comprovante_associado_path"),
            (Comprovante.Papel.AGENTE, "comprovante_agente_path"),
        ]:
            explicit_relative = (
                record.comprovante_associado_path
                if papel == Comprovante.Papel.ASSOCIADO
                else record.comprovante_agente_path
            )
            legacy_reference, source_path = self._resolve_evidence_file(
                explicit_relative=explicit_relative,
                legacy_cadastro_id=record.legacy_cadastro_id,
                papel=papel,
                paid_at=pagamento.paid_at,
            )
            if source_path is not None:
                stored_path = (
                    self._copy_to_storage(
                        contrato_codigo=contrato.codigo,
                        papel=papel,
                        source_path=source_path,
                    )
                    if execute
                    else self._planned_storage_name(
                        contrato_codigo=contrato.codigo,
                        papel=papel,
                        source_name=source_path.name,
                    )
                )
                setattr(pagamento, field_name, stored_path)
                copied_files += 1
                updated_comprovantes += self._upsert_contract_comprovante(
                    contrato=contrato,
                    pagamento=pagamento,
                    record=record,
                    papel=papel,
                    legacy_reference_path=legacy_reference,
                    stored_path=stored_path,
                )
            elif legacy_reference:
                setattr(pagamento, field_name, legacy_reference)

        if execute:
            update_fields = [
                "status",
                "cadastro",
                "contrato_codigo",
                "contrato_valor_antecipacao",
                "legacy_tesouraria_pagamento_id",
                "origem",
                "full_name",
                "agente_responsavel",
                "forma_pagamento",
                "notes",
                "valor_pago",
                "paid_at",
                "contrato_margem_disponivel",
                "referencias_externas",
                "comprovante_associado_path",
                "comprovante_agente_path",
                "updated_at",
            ]
            pagamento.save(update_fields=update_fields)
            self._stamp_timestamps(
                Pagamento,
                pagamento.pk,
                record.created_at or pagamento.paid_at,
            )
            pagamento.refresh_from_db()
            if pagamento.status == Pagamento.Status.PENDENTE:
                self._sync_pending_contract_state(
                    associado=associado,
                    contrato=contrato,
                    execute=execute,
                )

        initial_payment = get_initial_payment_for_contract(contrato) or pagamento
        evidencia_status = "arquivo_local" if copied_files else ""
        if evidencia_status == "" and initial_payment.status == Pagamento.Status.PAGO:
            if getattr(initial_payment, "comprovante_associado_path", "") or getattr(
                initial_payment, "comprovante_agente_path", ""
            ):
                evidencia_status = "referencia_legado"
            else:
                evidencia_status = "placeholder_recebido"

        return {
            "legacy_payment_id": record.legacy_id,
            "cpf_cnpj": record.cpf_cnpj,
            "contrato_codigo": contrato.codigo,
            "pagamento_id": pagamento.id,
            "status": "synced",
            "created_pagamento": created_pagamento,
            "copied_files": copied_files,
            "updated_comprovantes": updated_comprovantes,
            "payment_status": pagamento.status,
            "paid_at": pagamento.paid_at,
            "valor_pago": pagamento.valor_pago,
            "evidencia_status": evidencia_status,
            "origem": pagamento.origem,
        }
