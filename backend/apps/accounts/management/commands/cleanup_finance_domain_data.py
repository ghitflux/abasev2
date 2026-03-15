from __future__ import annotations

from dataclasses import dataclass

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models.fields.reverse_related import ForeignObjectRel

from apps.importacao.models import (
    ArquivoRetorno,
    ArquivoRetornoItem,
    ImportacaoLog,
    PagamentoMensalidade,
)
from apps.refinanciamento.models import AjusteValor, Assumption, Comprovante, Item, Refinanciamento


@dataclass(frozen=True)
class TargetTable:
    label: str
    model: type


TARGET_TABLES = (
    TargetTable("importacao_pagamentomensalidade", PagamentoMensalidade),
    TargetTable("importacao_arquivoretorno", ArquivoRetorno),
    TargetTable("importacao_arquivoretornoitem", ArquivoRetornoItem),
    TargetTable("importacao_importacaolog", ImportacaoLog),
    TargetTable("refinanciamento_refinanciamento", Refinanciamento),
    TargetTable("refinanciamento_item", Item),
)

TRUNCATE_ORDER = (
    ImportacaoLog,
    ArquivoRetornoItem,
    ArquivoRetorno,
    PagamentoMensalidade,
    Item,
    Refinanciamento,
)

OUT_OF_SCOPE_LABELS = {
    Comprovante._meta.db_table: "refinanciamento_comprovante",
    Assumption._meta.db_table: "refinanciamento_assumption",
    AjusteValor._meta.db_table: "refinanciamento_ajustevalor",
}


class Command(BaseCommand):
    help = (
        "Limpa seletivamente dados de importação/retorno e refinanciamento, "
        "removendo arquivos físicos de retorno e resetando auto-increment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe o que seria removido sem alterar banco ou storage.",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Executa a limpeza de forma definitiva.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        execute = bool(options["execute"])
        if dry_run == execute:
            raise CommandError(
                "Informe exatamente um modo: use `--dry-run` ou `--execute`."
            )

        self._validate_required_tables()
        self._validate_refinanciamento_dependencies()

        summary = self._build_summary()
        self._print_header(summary, dry_run=dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING("[DRY-RUN] Nenhuma alteração foi aplicada."))
            return

        file_result = self._delete_return_files(summary["file_paths"])
        self._truncate_target_tables()
        self._print_footer(summary, file_result)

    def _validate_required_tables(self):
        existing_tables = set(connection.introspection.table_names())
        missing = [
            target.label
            for target in TARGET_TABLES
            if target.model._meta.db_table not in existing_tables
        ]
        if missing:
            raise CommandError(
                "Tabelas obrigatórias ausentes para a limpeza: " + ", ".join(missing)
            )

    def _validate_refinanciamento_dependencies(self):
        target_tables = {target.model._meta.db_table for target in TARGET_TABLES}
        blocking_dependencies: list[str] = []

        for rel in Refinanciamento._meta.related_objects:
            if not isinstance(rel, ForeignObjectRel):
                continue
            related_model = rel.related_model
            if related_model is None:
                continue

            table_name = related_model._meta.db_table
            if table_name in target_tables:
                continue

            field_name = rel.field.name
            manager = getattr(related_model, "all_objects", related_model._default_manager)
            if manager.filter(**{f"{field_name}__isnull": False}).exists():
                blocking_dependencies.append(
                    OUT_OF_SCOPE_LABELS.get(table_name, table_name)
                )

        if blocking_dependencies:
            labels = ", ".join(sorted(set(blocking_dependencies)))
            raise CommandError(
                "Limpeza abortada: existem tabelas fora do escopo apontando para "
                f"`refinanciamento_refinanciamento`: {labels}. "
                "Limpe essas dependências manualmente antes de executar este comando."
            )

    def _build_summary(self) -> dict[str, object]:
        table_counts = {}
        for target in TARGET_TABLES:
            manager = getattr(target.model, "all_objects", target.model._default_manager)
            table_counts[target.label] = manager.count()

        file_paths = self._collect_file_paths()
        return {
            "table_counts": table_counts,
            "file_paths": file_paths,
            "included_tables": [target.label for target in TARGET_TABLES],
            "excluded_tables": sorted(OUT_OF_SCOPE_LABELS.values()),
        }

    def _collect_file_paths(self) -> list[str]:
        manager = getattr(ArquivoRetorno, "all_objects", ArquivoRetorno._default_manager)
        raw_paths = manager.exclude(arquivo_url="").values_list("arquivo_url", flat=True)
        return sorted({path for path in raw_paths if path})

    def _print_header(self, summary: dict[str, object], *, dry_run: bool):
        mode = "DRY-RUN" if dry_run else "EXECUTE"
        self.stdout.write(f"[{mode}] Tabelas incluídas: {', '.join(summary['included_tables'])}")
        self.stdout.write(f"[{mode}] Tabelas fora do escopo: {', '.join(summary['excluded_tables'])}")
        self.stdout.write(
            f"[{mode}] Arquivos de retorno candidatos: {len(summary['file_paths'])}"
        )

        for table_name, count in summary["table_counts"].items():
            self.stdout.write(f"[{mode}] {table_name}: {count} registros")

    def _delete_return_files(self, file_paths: list[str]) -> dict[str, int]:
        removed = 0
        missing = 0

        for path in file_paths:
            if default_storage.exists(path):
                default_storage.delete(path)
                removed += 1
            else:
                missing += 1

        return {"removed": removed, "missing": missing}

    def _truncate_target_tables(self):
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            try:
                for model in TRUNCATE_ORDER:
                    cursor.execute(
                        f"TRUNCATE TABLE {connection.ops.quote_name(model._meta.db_table)}"
                    )
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    def _print_footer(self, summary: dict[str, object], file_result: dict[str, int]):
        self.stdout.write(
            self.style.SUCCESS(
                "[EXECUTE] Arquivos removidos: "
                f"{file_result['removed']} (não encontrados: {file_result['missing']})"
            )
        )
        for table_name, count in summary["table_counts"].items():
            self.stdout.write(
                self.style.SUCCESS(
                    f"[EXECUTE] {table_name}: {count} registros removidos"
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                "[EXECUTE] Auto-increment resetado via TRUNCATE nas tabelas alvo."
            )
        )
