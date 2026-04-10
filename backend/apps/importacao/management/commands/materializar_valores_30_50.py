from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.reconciliacao import MotorReconciliacao
from apps.importacao.small_value_return_materialization import (
    materialize_small_value_return_items,
)
from apps.importacao.models import ArquivoRetornoItem


def parse_month_argument(value: str) -> date:
    try:
        year, month = value.split("-", 1)
        return date(int(year), int(month), 1)
    except (TypeError, ValueError) as exc:
        raise CommandError(
            f"Competência inválida: {value}. Use o formato YYYY-MM."
        ) from exc


class Command(BaseCommand):
    help = (
        "Materializa associados, contratos, ciclos e parcelas dos itens 30/50 "
        "dos arquivos retorno, vinculando os itens às parcelas corretas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cpf",
            help="Restringe a execução a um CPF específico.",
        )
        parser.add_argument(
            "--competencia-inicial",
            help="Competência inicial no formato YYYY-MM.",
        )
        parser.add_argument(
            "--competencia-final",
            help="Competência final no formato YYYY-MM.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a materialização no banco. Sem esta flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        competencia_inicial = (
            parse_month_argument(options["competencia_inicial"])
            if options.get("competencia_inicial")
            else None
        )
        competencia_final = (
            parse_month_argument(options["competencia_final"])
            if options.get("competencia_final")
            else None
        )
        report = materialize_small_value_return_items(
            cpf_cnpj=options.get("cpf"),
            competencia_inicial=competencia_inicial,
            competencia_final=competencia_final,
            apply=bool(options["apply"]),
        )

        self.stdout.write(f"modo: {report['mode']}")
        summary = report["summary"]
        self.stdout.write(f"cpf_total: {summary.get('cpf_total', 0)}")
        self.stdout.write(f"item_total: {summary.get('item_total', 0)}")
        self.stdout.write(f"associados_criados: {summary.get('associados_criados', 0)}")
        self.stdout.write(f"contratos_criados: {summary.get('contratos_criados', 0)}")
        self.stdout.write(f"contracts_reused: {summary.get('contracts_reused', 0)}")
        self.stdout.write(f"items_linked: {summary.get('items_linked', 0)}")
        self.stdout.write(f"payments_linked: {summary.get('payments_linked', 0)}")
        self.stdout.write(f"parcelas_created: {summary.get('parcelas_created', 0)}")
        self.stdout.write(f"parcelas_updated: {summary.get('parcelas_updated', 0)}")
        self.stdout.write(
            f"parcelas_soft_deleted: {summary.get('parcelas_soft_deleted', 0)}"
        )

        if options["apply"]:
            affected_item_ids = report.get("affected_item_ids", [])
            queryset = (
                ArquivoRetornoItem.objects.filter(id__in=affected_item_ids)
                .select_related("arquivo_retorno")
                .order_by("arquivo_retorno_id", "linha_numero", "id")
            )
            current_arquivo_id = None
            motor = None
            reprocessados = 0
            for item in queryset:
                if item.arquivo_retorno_id != current_arquivo_id:
                    current_arquivo_id = item.arquivo_retorno_id
                    motor = MotorReconciliacao(item.arquivo_retorno)
                if motor is None:
                    continue
                motor.reconciliar_item(item)
                reprocessados += 1
            self.stdout.write(f"itens_reconciliados: {reprocessados}")

        for row in report["results"]:
            self.stdout.write(
                f"{row['cpf_cnpj']}: associado={row['associado_id']} "
                f"contrato={row['contrato_codigo']} "
                f"refs={','.join(row['references'])}"
            )
