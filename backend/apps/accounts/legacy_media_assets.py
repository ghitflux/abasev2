from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db.models import Q
from django.utils.text import get_valid_filename

from apps.associados.models import Documento, only_digits
from apps.importacao.models import PagamentoMensalidade
from apps.refinanciamento.models import Comprovante
from apps.esteira.models import DocIssue, DocReupload


ALL_FAMILIES = ("cadastro", "renovacao", "tesouraria", "manual", "esteira")


@dataclass(frozen=True)
class SourceFile:
    kind: str
    display_path: str
    open_path: str | Path
    name: str


class LegacyMediaAssetsService:
    def __init__(self, *, legacy_root: str | Path):
        self.legacy_root = Path(legacy_root).expanduser().resolve()
        self.public_root = self.legacy_root / "public" / "public"
        self.public_storage_root = self.public_root / "storage"
        self.app_root = self.legacy_root / "storage" / "storage" / "app"
        self.app_public_root = self.app_root / "public"

    def run(
        self,
        *,
        families: Iterable[str] | None = None,
        cpf: str | None = None,
        execute: bool,
    ) -> dict[str, object]:
        selected = tuple(family for family in (families or ALL_FAMILIES) if family in ALL_FAMILIES)
        results: list[dict[str, object]] = []
        for family in selected:
            if family == "cadastro":
                results.extend(self._sync_documentos(cpf=cpf, execute=execute))
            elif family == "renovacao":
                results.extend(self._sync_comprovantes(origem="renovacao", cpf=cpf, execute=execute))
            elif family == "tesouraria":
                results.extend(self._sync_comprovantes(origem="tesouraria", cpf=cpf, execute=execute))
            elif family == "manual":
                results.extend(self._sync_manual_comprovantes(cpf=cpf, execute=execute))
            elif family == "esteira":
                results.extend(self._sync_esteira(cpf=cpf, execute=execute))

        summary: dict[str, object] = {
            "families": list(selected),
            "records": len(results),
            "updated": sum(1 for row in results if row["status"] == "updated"),
            "already_canonical": sum(1 for row in results if row["status"] == "already_canonical"),
            "reference_only": sum(1 for row in results if row["status"] == "reference_only"),
            "no_path": sum(1 for row in results if row["status"] == "no_path"),
            "family_breakdown": {},
        }
        for family in selected:
            family_rows = [row for row in results if row["family"] == family]
            summary["family_breakdown"][family] = {
                "records": len(family_rows),
                "updated": sum(1 for row in family_rows if row["status"] == "updated"),
                "already_canonical": sum(
                    1 for row in family_rows if row["status"] == "already_canonical"
                ),
                "reference_only": sum(
                    1 for row in family_rows if row["status"] == "reference_only"
                ),
                "no_path": sum(1 for row in family_rows if row["status"] == "no_path"),
            }
        return {"summary": summary, "results": results}

    def _sync_documentos(self, *, cpf: str | None, execute: bool) -> list[dict[str, object]]:
        queryset = Documento.all_objects.select_related("associado").order_by("associado_id", "id")
        if cpf:
            queryset = queryset.filter(associado__cpf_cnpj=only_digits(cpf))
        results: list[dict[str, object]] = []
        for documento in queryset.iterator():
            current_path = str(getattr(documento.arquivo, "name", "") or "")
            reference_path = documento.arquivo_referencia_path or current_path
            outcome = self._default_outcome(
                family="cadastro",
                model="Documento",
                object_id=documento.pk,
                cpf_cnpj=documento.associado.cpf_cnpj,
                legacy_path=reference_path,
                current_path=current_path,
            )
            if not reference_path:
                outcome["status"] = "no_path"
                results.append(outcome)
                continue

            planned_path = self._planned_document_path(documento, source_name=reference_path)
            outcome["planned_path"] = planned_path
            if self._is_local_canonical(current_path, planned_path):
                outcome["status"] = "already_canonical"
                results.append(outcome)
                continue

            source = self._resolve_source(
                reference_path=reference_path,
                current_path=current_path,
                family="cadastro",
            )
            if source is None:
                outcome["status"] = "reference_only"
                results.append(outcome)
                continue

            outcome["source_kind"] = source.kind
            outcome["source_path"] = source.display_path
            if execute:
                stored_path = self._copy_source_to_storage(source=source, destination=planned_path)
                documento.arquivo = stored_path
                documento.arquivo_referencia_path = reference_path
                documento.nome_original = documento.nome_original or source.name
                documento.origem = Documento.Origem.LEGADO_CADASTRO
                documento.save(
                    update_fields=[
                        "arquivo",
                        "arquivo_referencia_path",
                        "nome_original",
                        "origem",
                        "updated_at",
                    ]
                )
            outcome["status"] = "updated"
            results.append(outcome)
        return results

    def _sync_comprovantes(
        self,
        *,
        origem: str,
        cpf: str | None,
        execute: bool,
    ) -> list[dict[str, object]]:
        queryset = (
            Comprovante.all_objects.select_related(
                "contrato__associado",
                "refinanciamento__associado",
            )
            .order_by("contrato_id", "refinanciamento_id", "id")
        )
        if origem == "tesouraria":
            queryset = queryset.filter(origem=Comprovante.Origem.EFETIVACAO_CONTRATO)
        else:
            queryset = queryset.exclude(origem=Comprovante.Origem.EFETIVACAO_CONTRATO)
        if cpf:
            digits = only_digits(cpf)
            queryset = queryset.filter(
                Q(contrato__associado__cpf_cnpj=digits)
                | Q(refinanciamento__associado__cpf_cnpj=digits)
            )

        results: list[dict[str, object]] = []
        for comprovante in queryset.iterator():
            current_path = str(getattr(comprovante.arquivo, "name", "") or "")
            reference_path = comprovante.arquivo_referencia_path or current_path
            cpf_cnpj = (
                getattr(getattr(comprovante.contrato, "associado", None), "cpf_cnpj", "")
                or getattr(getattr(comprovante.refinanciamento, "associado", None), "cpf_cnpj", "")
            )
            outcome = self._default_outcome(
                family=origem,
                model="Comprovante",
                object_id=comprovante.pk,
                cpf_cnpj=cpf_cnpj,
                legacy_path=reference_path,
                current_path=current_path,
            )
            if not reference_path and not current_path:
                outcome["status"] = "no_path"
                results.append(outcome)
                continue

            planned_path = self._planned_comprovante_path(comprovante, source_name=reference_path or current_path)
            outcome["planned_path"] = planned_path
            if self._is_local_canonical(current_path, planned_path):
                outcome["status"] = "already_canonical"
                results.append(outcome)
                continue

            source = self._resolve_source(
                reference_path=reference_path or current_path,
                current_path=current_path,
                family="renovacao" if origem == "renovacao" else "tesouraria",
            )
            if source is None:
                outcome["status"] = "reference_only"
                results.append(outcome)
                continue

            outcome["source_kind"] = source.kind
            outcome["source_path"] = source.display_path
            if execute:
                stored_path = self._copy_source_to_storage(source=source, destination=planned_path)
                comprovante.arquivo = stored_path
                comprovante.arquivo_referencia_path = reference_path or current_path
                comprovante.nome_original = comprovante.nome_original or source.name
                comprovante.save(
                    update_fields=[
                        "arquivo",
                        "arquivo_referencia_path",
                        "nome_original",
                        "updated_at",
                    ]
                )
            outcome["status"] = "updated"
            results.append(outcome)
        return results

    def _sync_manual_comprovantes(
        self,
        *,
        cpf: str | None,
        execute: bool,
    ) -> list[dict[str, object]]:
        queryset = PagamentoMensalidade.objects.exclude(manual_comprovante_path="").order_by(
            "referencia_month",
            "cpf_cnpj",
            "id",
        )
        if cpf:
            queryset = queryset.filter(cpf_cnpj=only_digits(cpf))
        results: list[dict[str, object]] = []
        for pagamento in queryset.iterator():
            current_path = pagamento.manual_comprovante_path or ""
            outcome = self._default_outcome(
                family="manual",
                model="PagamentoMensalidade",
                object_id=pagamento.pk,
                cpf_cnpj=pagamento.cpf_cnpj,
                legacy_path=current_path,
                current_path=current_path,
            )
            if not current_path:
                outcome["status"] = "no_path"
                results.append(outcome)
                continue

            planned_path = self._planned_manual_path(pagamento, source_name=current_path)
            outcome["planned_path"] = planned_path
            if current_path == planned_path and default_storage.exists(current_path):
                outcome["status"] = "already_canonical"
                results.append(outcome)
                continue

            source = self._resolve_source(
                reference_path=current_path,
                current_path=current_path,
                family="manual",
            )
            if source is None:
                outcome["status"] = "reference_only"
                results.append(outcome)
                continue

            outcome["source_kind"] = source.kind
            outcome["source_path"] = source.display_path
            if execute:
                stored_path = self._copy_source_to_storage(source=source, destination=planned_path)
                pagamento.manual_comprovante_path = stored_path
                pagamento.save(update_fields=["manual_comprovante_path", "updated_at"])
            outcome["status"] = "updated"
            results.append(outcome)
        return results

    def _sync_esteira(self, *, cpf: str | None, execute: bool) -> list[dict[str, object]]:
        results = self._sync_doc_reuploads(cpf=cpf, execute=execute)
        results.extend(self._sync_doc_issue_snapshots(cpf=cpf, execute=execute))
        return results

    def _sync_doc_reuploads(self, *, cpf: str | None, execute: bool) -> list[dict[str, object]]:
        queryset = DocReupload.all_objects.select_related("associado").order_by("doc_issue_id", "id")
        if cpf:
            queryset = queryset.filter(cpf_cnpj=only_digits(cpf))

        results: list[dict[str, object]] = []
        for item in queryset.iterator():
            current_path = item.file_relative_path or ""
            extras = self._coerce_dict(item.extras)
            legacy_path = str(extras.get("legacy_path") or current_path)
            outcome = self._default_outcome(
                family="esteira",
                model="DocReupload",
                object_id=item.pk,
                cpf_cnpj=item.cpf_cnpj,
                legacy_path=legacy_path,
                current_path=current_path,
            )
            if not legacy_path:
                outcome["status"] = "no_path"
                results.append(outcome)
                continue

            planned_path = self._planned_reupload_path(item, source_name=legacy_path)
            outcome["planned_path"] = planned_path
            if current_path == planned_path and default_storage.exists(current_path):
                outcome["status"] = "already_canonical"
                results.append(outcome)
                continue

            source = self._resolve_source(
                reference_path=legacy_path,
                current_path=current_path,
                family="esteira",
            )
            if source is None:
                outcome["status"] = "reference_only"
                results.append(outcome)
                continue

            outcome["source_kind"] = source.kind
            outcome["source_path"] = source.display_path
            if execute:
                stored_path = self._copy_source_to_storage(source=source, destination=planned_path)
                extras["legacy_path"] = legacy_path
                extras["storage_path"] = stored_path
                extras["arquivo_disponivel_localmente"] = True
                item.file_relative_path = stored_path
                item.extras = extras
                item.save(update_fields=["file_relative_path", "extras", "updated_at"])
            outcome["status"] = "updated"
            results.append(outcome)
        return results

    def _sync_doc_issue_snapshots(
        self,
        *,
        cpf: str | None,
        execute: bool,
    ) -> list[dict[str, object]]:
        queryset = DocIssue.all_objects.exclude(agent_uploads_json=None).order_by("associado_id", "id")
        if cpf:
            queryset = queryset.filter(cpf_cnpj=only_digits(cpf))
        results: list[dict[str, object]] = []
        for issue in queryset.iterator():
            payload = issue.agent_uploads_json
            normalized, changed, copied, reference_only = self._normalize_agent_uploads_payload(
                issue=issue,
                payload=payload,
                execute=execute,
            )
            outcome = self._default_outcome(
                family="esteira",
                model="DocIssue.agent_uploads_json",
                object_id=issue.pk,
                cpf_cnpj=issue.cpf_cnpj,
                legacy_path="",
                current_path="",
            )
            if copied:
                outcome["status"] = "updated"
            elif reference_only:
                outcome["status"] = "reference_only"
            elif changed:
                outcome["status"] = "already_canonical"
            else:
                outcome["status"] = "no_path"
            outcome["copied_entries"] = copied
            if execute and changed:
                issue.agent_uploads_json = normalized
                issue.save(update_fields=["agent_uploads_json", "updated_at"])
            results.append(outcome)
        return results

    def _normalize_agent_uploads_payload(
        self,
        *,
        issue: DocIssue,
        payload,
        execute: bool,
    ) -> tuple[object, bool, int, bool]:
        if isinstance(payload, str):
            return payload, False, 0, False
        if isinstance(payload, dict):
            normalized, changed, copied, reference_only = self._normalize_agent_upload_entry(
                issue=issue,
                entry=payload,
                execute=execute,
            )
            return normalized, changed, copied, reference_only
        if not isinstance(payload, list):
            return payload, False, 0, False
        changed = False
        copied = 0
        reference_only = False
        normalized_items = []
        for entry in payload:
            if not isinstance(entry, dict):
                normalized_items.append(entry)
                continue
            normalized, entry_changed, entry_copied, entry_reference_only = self._normalize_agent_upload_entry(
                issue=issue,
                entry=entry,
                execute=execute,
            )
            normalized_items.append(normalized)
            changed = changed or entry_changed
            copied += entry_copied
            reference_only = reference_only or entry_reference_only
        return normalized_items, changed, copied, reference_only

    def _normalize_agent_upload_entry(
        self,
        *,
        issue: DocIssue,
        entry: dict[str, object],
        execute: bool,
    ) -> tuple[dict[str, object], bool, int, bool]:
        normalized = dict(entry)
        legacy_path = self._extract_agent_upload_path(entry)
        if not legacy_path:
            return normalized, False, 0, False
        current_path = str(entry.get("storage_path") or legacy_path)
        planned_path = self._planned_agent_upload_path(issue, source_name=legacy_path)
        normalized["legacy_path"] = legacy_path
        normalized["storage_path"] = current_path
        if current_path == planned_path and default_storage.exists(current_path):
            normalized["arquivo_disponivel_localmente"] = True
            return normalized, True, 0, False

        source = self._resolve_source(
            reference_path=legacy_path,
            current_path=current_path,
            family="esteira",
        )
        if source is None:
            normalized["arquivo_disponivel_localmente"] = False
            return normalized, True, 0, True

        normalized["arquivo_disponivel_localmente"] = True
        if execute:
            stored_path = self._copy_source_to_storage(source=source, destination=planned_path)
            normalized["storage_path"] = stored_path
        else:
            normalized["storage_path"] = planned_path
        return normalized, True, 1, False

    def _resolve_source(
        self,
        *,
        reference_path: str,
        current_path: str,
        family: str,
    ) -> SourceFile | None:
        normalized_current = current_path.strip().lstrip("/")
        if normalized_current and default_storage.exists(normalized_current):
            return SourceFile(
                kind="storage",
                display_path=normalized_current,
                open_path=normalized_current,
                name=Path(normalized_current).name,
            )

        normalized_reference = reference_path.strip().lstrip("/")
        if not normalized_reference:
            return None

        for candidate in self._candidate_paths(normalized_reference, family=family):
            if candidate.exists() and candidate.is_file():
                return SourceFile(
                    kind="legacy_fs",
                    display_path=str(candidate),
                    open_path=candidate,
                    name=candidate.name,
                )
        return None

    def _candidate_paths(self, relative_path: str, *, family: str) -> list[Path]:
        normalized = relative_path.strip().lstrip("/")
        storage_trimmed = normalized.removeprefix("storage/")
        families = {
            "cadastro": [
                self.public_root / normalized,
                self.public_storage_root / storage_trimmed,
            ],
            "esteira": [
                self.public_root / normalized,
                self.public_storage_root / storage_trimmed,
                self.app_public_root / normalized,
            ],
            "tesouraria": [
                self.public_storage_root / normalized,
                self.public_root / normalized,
                self.app_root / normalized,
                self.app_public_root / normalized,
            ],
            "renovacao": [
                self.app_public_root / normalized,
                self.app_root / normalized,
                self.public_storage_root / normalized,
                self.public_root / normalized,
            ],
            "manual": [
                self.app_public_root / normalized,
                self.public_storage_root / normalized,
                self.public_root / normalized,
                self.app_root / normalized,
            ],
        }
        seen: set[Path] = set()
        ordered: list[Path] = []
        for candidate in families.get(family, families["manual"]):
            if candidate not in seen:
                seen.add(candidate)
                ordered.append(candidate)
        return ordered

    def _copy_source_to_storage(self, *, source: SourceFile, destination: str) -> str:
        if default_storage.exists(destination):
            return destination
        if source.kind == "storage":
            with default_storage.open(str(source.open_path), "rb") as handle:
                return default_storage.save(destination, File(handle, name=source.name))
        with Path(source.open_path).open("rb") as handle:
            return default_storage.save(destination, File(handle, name=source.name))

    def _default_outcome(
        self,
        *,
        family: str,
        model: str,
        object_id: int,
        cpf_cnpj: str,
        legacy_path: str,
        current_path: str,
    ) -> dict[str, object]:
        return {
            "family": family,
            "model": model,
            "object_id": object_id,
            "cpf_cnpj": cpf_cnpj,
            "status": "",
            "legacy_path": legacy_path,
            "current_path": current_path,
            "planned_path": "",
            "source_kind": "",
            "source_path": "",
        }

    def _is_local_canonical(self, current_path: str, planned_path: str) -> bool:
        return current_path == planned_path and bool(current_path) and default_storage.exists(current_path)

    def _planned_document_path(self, documento: Documento, *, source_name: str) -> str:
        cpf_cnpj = only_digits(documento.associado.cpf_cnpj) or str(documento.associado_id)
        safe_name = get_valid_filename(Path(source_name).name or f"documento-{documento.pk}")
        candidate = f"documentos/associados/{cpf_cnpj}/{documento.tipo}/{safe_name}"
        if len(candidate) <= 100:
            return candidate
        digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
        suffix = Path(safe_name).suffix.lower()
        stem = Path(safe_name).stem[-18:]
        shortened = f"documentos/assoc/{cpf_cnpj[-8:]}/{documento.tipo}/{digest}_{stem}{suffix}"
        return shortened[:100]

    def _planned_comprovante_path(self, comprovante: Comprovante, *, source_name: str) -> str:
        safe_name = get_valid_filename(Path(source_name).name or f"comprovante-{comprovante.pk}")
        contrato_codigo = getattr(comprovante.contrato, "codigo", "") or getattr(
            getattr(comprovante.refinanciamento, "contrato_origem", None),
            "codigo",
            "",
        )
        if not contrato_codigo:
            contrato_codigo = f"ref-{comprovante.refinanciamento_id or comprovante.id}"
        if comprovante.origem == Comprovante.Origem.EFETIVACAO_CONTRATO:
            prefix = "associado" if comprovante.papel == Comprovante.Papel.ASSOCIADO else "agente"
            candidate = f"refinanciamentos/efetivacao_contrato/{contrato_codigo}/{prefix}_{safe_name}"
            if len(candidate) <= 100:
                return candidate
            digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
            suffix = Path(safe_name).suffix.lower()
            stem = Path(safe_name).stem[-18:]
            return f"refinanciamentos/efet/{contrato_codigo[-12:]}/{prefix}_{digest}_{stem}{suffix}"[:100]

        folder = "operacional"
        if comprovante.tipo == Comprovante.Tipo.TERMO_ANTECIPACAO:
            folder = "termo"
        elif comprovante.papel == Comprovante.Papel.ASSOCIADO:
            folder = "associado"
        elif comprovante.papel == Comprovante.Papel.AGENTE:
            folder = "agente"
        candidate = f"refinanciamentos/renovacoes/{contrato_codigo}/{folder}/{safe_name}"
        if len(candidate) <= 100:
            return candidate
        digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:10]
        suffix = Path(safe_name).suffix.lower()
        stem = Path(safe_name).stem[-18:]
        return f"refinanciamentos/ren/{contrato_codigo[-12:]}/{folder}/{digest}_{stem}{suffix}"[:100]

    def _planned_manual_path(self, pagamento: PagamentoMensalidade, *, source_name: str) -> str:
        safe_name = get_valid_filename(Path(source_name).name or f"manual-{pagamento.pk}")
        cpf = only_digits(pagamento.cpf_cnpj)
        if safe_name.startswith(f"{cpf}_"):
            final_name = safe_name
        else:
            final_name = f"{cpf}_{safe_name}"
        return (
            "pagamentos_mensalidades/comprovantes/"
            f"{pagamento.referencia_month:%Y/%m}/{final_name}"
        )[:500]

    def _planned_reupload_path(self, item: DocReupload, *, source_name: str) -> str:
        safe_name = get_valid_filename(Path(source_name).name or item.file_original_name or f"reupload-{item.pk}")
        return f"esteira/reuploads/{item.doc_issue_id}/{safe_name}"[:500]

    def _planned_agent_upload_path(self, issue: DocIssue, *, source_name: str) -> str:
        safe_name = get_valid_filename(Path(source_name).name or f"agent-upload-{issue.pk}")
        return f"esteira/agent_uploads/{issue.associado_id}/{safe_name}"[:500]

    def _extract_agent_upload_path(self, entry: dict[str, object]) -> str:
        for key in (
            "storage_path",
            "legacy_path",
            "relative_path",
            "file_relative_path",
            "path",
            "arquivo",
        ):
            value = str(entry.get(key) or "").strip()
            if value:
                return value
        return ""

    def _coerce_dict(self, payload) -> dict[str, object]:
        if isinstance(payload, dict):
            return dict(payload)
        return {}
