from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.importacao.legacy import list_legacy_pagamento_snapshots_from_dump
from apps.importacao.models import PagamentoMensalidade
from apps.importacao.services import _apply_legacy_snapshot_to_pagamento


def _parse_competencia(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise CommandError("Competência inválida. Use YYYY-MM.") from exc


class Command(BaseCommand):
    help = (
        "Sincroniza os campos manuais do legado (pagamentos_mensalidades) "
        "para importacao_pagamentomensalidade."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="scriptsphp/abasedb1203.sql",
            help="Dump SQL legado com a tabela pagamentos_mensalidades.",
        )
        parser.add_argument(
            "--competencia",
            help="Competência no formato YYYY-MM para limitar o sync.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Persiste as alterações. Sem isso, executa em dry-run.",
        )
        parser.add_argument(
            "--include-refi-flags",
            action="store_true",
            help="Inclui a sincronização de agente_refi_solicitado.",
        )

    def handle(self, *args, **options):
        dump_path = Path(options["file"]).resolve()
        if not dump_path.exists():
            raise CommandError(f"Dump não encontrado: {dump_path}")

        competencia = _parse_competencia(options.get("competencia"))
        snapshots = list_legacy_pagamento_snapshots_from_dump(
            dump_path=dump_path,
            competencia=competencia,
        )
        if not snapshots:
            self.stdout.write(self.style.WARNING("Nenhum snapshot manual encontrado no dump."))
            return

        pagamentos = PagamentoMensalidade.objects.all()
        if competencia:
            pagamentos = pagamentos.filter(referencia_month=competencia)

        pagamentos = pagamentos.order_by("referencia_month", "cpf_cnpj", "id")
        total_pagamentos = pagamentos.count()
        total_snapshots = len(snapshots)
        matched_keys: set[tuple[str, object]] = set()
        matched = 0
        updated = 0
        unchanged = 0
        missing = 0
        field_updates: dict[str, int] = {}

        with transaction.atomic():
            for pagamento in pagamentos.iterator():
                key = (
                    re.sub(r"\D", "", pagamento.cpf_cnpj or ""),
                    pagamento.referencia_month,
                )
                snapshot = snapshots.get(key)
                if snapshot is None:
                    missing += 1
                    continue

                matched += 1
                matched_keys.add(key)
                original_agente_refi_solicitado = pagamento.agente_refi_solicitado
                updated_fields = _apply_legacy_snapshot_to_pagamento(pagamento, snapshot)
                if (
                    not options["include_refi_flags"]
                    and "agente_refi_solicitado" in updated_fields
                ):
                    pagamento.agente_refi_solicitado = original_agente_refi_solicitado
                    updated_fields = [
                        field_name
                        for field_name in updated_fields
                        if field_name != "agente_refi_solicitado"
                    ]
                if (
                    "manual_paid_at" in updated_fields
                    and pagamento.manual_paid_at
                    and timezone.is_naive(pagamento.manual_paid_at)
                ):
                    pagamento.manual_paid_at = timezone.make_aware(pagamento.manual_paid_at)
                if not updated_fields:
                    unchanged += 1
                    continue

                updated += 1
                for field_name in updated_fields:
                    field_updates[field_name] = field_updates.get(field_name, 0) + 1

                if options["execute"]:
                    pagamento.save(update_fields=[*updated_fields, "updated_at"])

            if not options["execute"]:
                transaction.set_rollback(True)

        unmatched_snapshots = total_snapshots - len(matched_keys)
        mode = "execute" if options["execute"] else "dry-run"
        self.stdout.write(f"modo: {mode}")
        self.stdout.write(f"dump: {dump_path}")
        if competencia:
            self.stdout.write(f"competencia: {competencia.strftime('%Y-%m')}")
        self.stdout.write(f"pagamentos avaliados: {total_pagamentos}")
        self.stdout.write(f"snapshots manuais: {total_snapshots}")
        self.stdout.write(f"pagamentos com snapshot correspondente: {matched}")
        self.stdout.write(f"pagamentos sem snapshot correspondente: {missing}")
        self.stdout.write(f"snapshots sem pagamento atual correspondente: {unmatched_snapshots}")
        self.stdout.write(f"pagamentos alterados: {updated}")
        self.stdout.write(f"pagamentos já completos: {unchanged}")
        if field_updates:
            for field_name in sorted(field_updates):
                self.stdout.write(f"  - {field_name}: {field_updates[field_name]}")
