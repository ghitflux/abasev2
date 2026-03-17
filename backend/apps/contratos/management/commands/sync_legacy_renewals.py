from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.associados.models import Associado
from apps.contratos.cycle_projection import refinanciamento_matches_contract_timeline
from apps.contratos.cycle_rebuild import rebuild_contract_cycle_state
from apps.contratos.legacy_renewals import load_legacy_renewals, next_month_start
from apps.contratos.models import Contrato
from apps.refinanciamento.models import Comprovante, Refinanciamento
from core.legacy_dump import LegacyDump


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
    help = "Sincroniza renovações legadas como ledger canônico de ciclos e atualiza comprovantes/termo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="scriptsphp/abase (2).sql",
            help="Dump SQL legado.",
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
        renewals = load_legacy_renewals(dump, cpf_filter=options.get("cpf"))
        if not renewals:
            raise CommandError("Nenhuma renovação legada encontrada para sincronização.")

        self._fallback_user_id = self._resolve_fallback_user_id()
        report_rows: list[dict[str, object]] = []
        impacted_contract_ids: set[int] = set()

        context = transaction.atomic() if not execute else nullcontext()
        with context:
            for renewal in renewals:
                payload = self._sync_renewal(renewal)
                report_rows.append(payload)
                if payload["contrato_id"] is not None:
                    impacted_contract_ids.add(int(payload["contrato_id"]))

            rebuild_reports = [
                rebuild_contract_cycle_state(contrato, execute=execute).as_dict()
                for contrato in Contrato.objects.filter(id__in=sorted(impacted_contract_ids))
                .select_related("associado", "agente")
                .order_by("associado__nome_completo", "id")
            ]
            if execute:
                self._relink_cycle_documents(impacted_contract_ids)
            if not execute:
                transaction.set_rollback(True)

        summary = {
            "mode": "execute" if execute else "dry-run",
            "legacy_renewals": len(report_rows),
            "contracts_impacted": len(impacted_contract_ids),
            "synced": sum(1 for row in report_rows if row["status"] == "synced"),
            "skipped": sum(1 for row in report_rows if row["status"] != "synced"),
            "proofs_synced": sum(int(row["proofs_synced"]) for row in report_rows),
            "terms_synced": sum(1 for row in report_rows if row["term_synced"]),
            "rebuild_reports": len(rebuild_reports),
        }
        payload = {
            "generated_at": datetime.now().isoformat(),
            "legacy_file": str(dump_path),
            "summary": summary,
            "renewals": report_rows,
            "rebuild": rebuild_reports,
        }

        target = (
            Path(options["report_json"])
            if options.get("report_json")
            else _default_report_path("sync_legacy_renewals")
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Sincronizadas {summary['synced']} renovação(ões) em modo {summary['mode']}."
            )
        )
        self.stdout.write(f"Relatório: {target}")

    def _resolve_fallback_user_id(self) -> int:
        user_model = get_user_model()
        user = user_model.all_objects.filter(is_active=True).order_by("id").only("id").first()
        if user is None:
            raise CommandError("Nenhum usuário ativo disponível para vincular os registros legados.")
        return int(user.pk)

    def _resolve_solicitante_id(self, renewal) -> int:
        user_model = get_user_model()
        legacy_user_id = renewal.created_by_user_id
        if legacy_user_id is None:
            return self._fallback_user_id
        user = user_model.all_objects.filter(pk=legacy_user_id).only("id").first()
        return int(user.pk) if user is not None else self._fallback_user_id

    def _resolve_associado(self, cpf_cnpj: str) -> Associado | None:
        return Associado.all_objects.filter(cpf_cnpj=cpf_cnpj).only("id", "nome_completo").first()

    def _legacy_storage_name(self, path: str, *, legacy_id: int | None) -> str:
        normalized = path.strip()
        if len(normalized) <= 100:
            return normalized
        suffix = Path(normalized).name[-60:]
        if legacy_id is None:
            return f"legacy/{suffix}"[:100]
        return f"legacy/{legacy_id}-{suffix}"[:100]

    def _stamp_timestamps(self, model, pk: int, reference_at):
        if reference_at is None:
            return
        model.all_objects.filter(pk=pk).update(
            created_at=reference_at,
            updated_at=reference_at,
        )

    def _resolve_contrato(self, renewal, associado: Associado | None) -> Contrato | None:
        if renewal.contrato_codigo_origem:
            contrato = (
                Contrato.all_objects.filter(codigo=renewal.contrato_codigo_origem)
                .select_related("associado")
                .first()
            )
            if contrato is not None:
                return contrato
        if associado is None:
            return None
        candidate_refi = Refinanciamento(
            legacy_refinanciamento_id=renewal.legacy_id,
            contrato_codigo_origem=renewal.contrato_codigo_origem,
            data_ativacao_ciclo=renewal.activation_at,
            executado_em=renewal.activation_at,
            ref1=renewal.ref1,
            ref2=renewal.ref2,
            ref3=renewal.ref3,
            ref4=renewal.ref4,
        )
        for contrato in (
            Contrato.all_objects.filter(associado=associado)
            .exclude(status=Contrato.Status.CANCELADO)
            .order_by("created_at", "id")
        ):
            if refinanciamento_matches_contract_timeline(contrato, candidate_refi):
                return contrato
        return None

    def _refinanciamento_defaults(self, renewal, associado: Associado, contrato: Contrato | None):
        referencias = [
            referencia
            for referencia in [renewal.ref1, renewal.ref2, renewal.ref3, renewal.ref4]
            if referencia is not None
        ]
        return {
            "associado": associado,
            "contrato_origem": contrato,
            "solicitado_por_id": self._resolve_solicitante_id(renewal),
            "competencia_solicitada": next_month_start(
                renewal.activation_at,
                ref1=renewal.ref1,
                ref2=renewal.ref2,
                ref3=renewal.ref3,
                ref4=renewal.ref4,
            ),
            "status": Refinanciamento.Status.EFETIVADO,
            "mode": "legacy_sync",
            "legacy_refinanciamento_id": renewal.legacy_id,
            "origem": Refinanciamento.Origem.LEGADO,
            "data_ativacao_ciclo": renewal.activation_at,
            "executado_em": renewal.activation_at,
            "deleted_at": None,
            "cycle_key": renewal.cycle_key,
            "ref1": renewal.ref1,
            "ref2": renewal.ref2,
            "ref3": renewal.ref3,
            "ref4": renewal.ref4,
            "cpf_cnpj_snapshot": renewal.cpf_cnpj,
            "nome_snapshot": renewal.nome_snapshot,
            "agente_snapshot": renewal.agente_snapshot,
            "filial_snapshot": renewal.filial_snapshot,
            "contrato_codigo_origem": renewal.contrato_codigo_origem,
            "observacao": renewal.notes,
            "parcelas_ok": len(referencias),
            "parcelas_json": [
                {"referencia_month": referencia.isoformat(), "status_code": "1"}
                for referencia in referencias
            ],
        }

    def _sync_renewal(self, renewal) -> dict[str, object]:
        associado = self._resolve_associado(renewal.cpf_cnpj)
        contrato = self._resolve_contrato(renewal, associado)
        if associado is None:
            return {
                "legacy_refinanciamento_id": renewal.legacy_id,
                "cpf_cnpj": renewal.cpf_cnpj,
                "contrato_id": None,
                "refinanciamento_id": None,
                "status": "skipped_associado_not_found",
                "proofs_synced": 0,
                "term_synced": False,
            }
        if contrato is None:
            return {
                "legacy_refinanciamento_id": renewal.legacy_id,
                "cpf_cnpj": renewal.cpf_cnpj,
                "contrato_id": None,
                "refinanciamento_id": None,
                "status": "skipped_contrato_not_found",
                "proofs_synced": 0,
                "term_synced": False,
            }

        refinanciamento, _created = Refinanciamento.all_objects.update_or_create(
            legacy_refinanciamento_id=renewal.legacy_id,
            defaults=self._refinanciamento_defaults(renewal, associado, contrato),
        )
        self._stamp_timestamps(
            Refinanciamento,
            refinanciamento.pk,
            renewal.activation_at,
        )
        refinanciamento.refresh_from_db()

        proofs_synced = 0
        for proof in renewal.proofs:
            tipo = Comprovante.Tipo.OUTRO
            papel = Comprovante.Papel.OPERACIONAL
            if "associado" in proof.kind:
                tipo = Comprovante.Tipo.COMPROVANTE_PAGAMENTO_ASSOCIADO
                papel = Comprovante.Papel.ASSOCIADO
            elif "agente" in proof.kind:
                tipo = Comprovante.Tipo.COMPROVANTE_PAGAMENTO_AGENTE
                papel = Comprovante.Papel.AGENTE
            elif "pix" in proof.kind:
                tipo = Comprovante.Tipo.PIX
            elif "contrato" in proof.kind:
                tipo = Comprovante.Tipo.CONTRATO

            comprovante, _ = Comprovante.all_objects.update_or_create(
                legacy_comprovante_id=proof.legacy_id,
                defaults={
                    "refinanciamento": refinanciamento,
                    "contrato": contrato,
                    "ciclo": refinanciamento.ciclo_destino,
                    "tipo": tipo,
                    "papel": papel,
                    "arquivo": self._legacy_storage_name(
                        proof.path,
                        legacy_id=proof.legacy_id,
                    ),
                    "arquivo_referencia_path": proof.path,
                    "nome_original": proof.original_name,
                    "data_pagamento": renewal.activation_at,
                    "origem": Comprovante.Origem.LEGADO,
                    "agente_snapshot": proof.agente_snapshot or renewal.agente_snapshot,
                    "filial_snapshot": proof.filial_snapshot or renewal.filial_snapshot,
                    "enviado_por_id": self._fallback_user_id,
                },
            )
            self._stamp_timestamps(
                Comprovante,
                comprovante.pk,
                renewal.activation_at,
            )
            proofs_synced += 1

        term_synced = False
        if renewal.term is not None:
            comprovante, _ = Comprovante.all_objects.update_or_create(
                refinanciamento=refinanciamento,
                tipo=Comprovante.Tipo.TERMO_ANTECIPACAO,
                arquivo=self._legacy_storage_name(renewal.term.path, legacy_id=renewal.legacy_id),
                defaults={
                    "contrato": contrato,
                    "ciclo": refinanciamento.ciclo_destino,
                    "papel": Comprovante.Papel.OPERACIONAL,
                    "arquivo_referencia_path": renewal.term.path,
                    "nome_original": renewal.term.original_name,
                    "mime": renewal.term.mime,
                    "size_bytes": renewal.term.size_bytes,
                    "data_pagamento": renewal.activation_at or renewal.term.uploaded_at,
                    "origem": Comprovante.Origem.LEGADO,
                    "enviado_por_id": self._fallback_user_id,
                },
            )
            self._stamp_timestamps(
                Comprovante,
                comprovante.pk,
                renewal.activation_at or renewal.term.uploaded_at,
            )
            refinanciamento.termo_antecipacao_path = renewal.term.path
            refinanciamento.termo_antecipacao_original_name = renewal.term.original_name
            refinanciamento.termo_antecipacao_mime = renewal.term.mime
            refinanciamento.termo_antecipacao_size_bytes = renewal.term.size_bytes
            refinanciamento.termo_antecipacao_uploaded_at = renewal.term.uploaded_at
            refinanciamento.save(
                update_fields=[
                    "termo_antecipacao_path",
                    "termo_antecipacao_original_name",
                    "termo_antecipacao_mime",
                    "termo_antecipacao_size_bytes",
                    "termo_antecipacao_uploaded_at",
                    "updated_at",
                ]
            )
            term_synced = True

        return {
            "legacy_refinanciamento_id": renewal.legacy_id,
            "cpf_cnpj": renewal.cpf_cnpj,
            "contrato_id": contrato.id,
            "contrato_codigo": contrato.codigo,
            "refinanciamento_id": refinanciamento.id,
            "status": "synced",
            "activation_at": renewal.activation_at,
            "proofs_synced": proofs_synced,
            "term_synced": term_synced,
        }

    def _relink_cycle_documents(self, contract_ids: set[int]) -> None:
        for refinanciamento in (
            Refinanciamento.objects.filter(contrato_origem_id__in=contract_ids)
            .select_related("ciclo_destino")
            .order_by("id")
        ):
            if refinanciamento.ciclo_destino_id is None:
                continue
            Comprovante.objects.filter(refinanciamento=refinanciamento).update(
                ciclo=refinanciamento.ciclo_destino
            )
