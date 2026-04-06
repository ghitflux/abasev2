from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.server_return_correction import (
    ServerReturnCorrectionError,
    parse_competencia_argument,
    run_server_return_correction,
)


class Command(BaseCommand):
    help = (
        "Reprocessa uma competência de arquivo retorno para fechar o financeiro oficial "
        "e corrigir as parcelas reais existentes, sem alterar ciclos."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia",
            required=True,
            help="Competência da correção no formato YYYY-MM.",
        )
        parser.add_argument(
            "--arquivo-retorno-id",
            dest="arquivo_retorno_id",
            type=int,
            help="ID opcional do ArquivoRetorno a ser reprocessado.",
        )
        parser.add_argument(
            "--arquivo-path",
            dest="arquivo_path",
            help="Caminho do arquivo retorno quando não houver ArquivoRetorno prévio.",
        )
        parser.add_argument(
            "--uploaded-by-id",
            dest="uploaded_by_id",
            type=int,
            help="Usuário responsável pelo upload quando usar --arquivo-path sem ArquivoRetorno prévio.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção. Sem esta flag, roda apenas em dry-run.",
        )

    def handle(self, *args, **options):
        try:
            competencia = parse_competencia_argument(options["competencia"])
            report = run_server_return_correction(
                competencia=competencia,
                apply=bool(options["apply"]),
                arquivo_retorno_id=options.get("arquivo_retorno_id"),
                arquivo_path=options.get("arquivo_path"),
                uploaded_by_id=options.get("uploaded_by_id"),
            )
        except (ServerReturnCorrectionError, ValueError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"modo: {report['mode']}")
        self.stdout.write(f"competencia: {report['competencia']}")
        self.stdout.write(f"arquivo_retorno_id: {report['arquivo_retorno_id']}")
        self.stdout.write(f"arquivo_nome: {report['arquivo_nome']}")
        self.stdout.write(f"esperado_total: {report['expected']['total']}")
        self.stdout.write(f"esperado_ok: {report['expected']['ok']}")
        self.stdout.write(f"esperado_faltando: {report['expected']['faltando']}")
        self.stdout.write(f"esperado_valor: {report['expected']['esperado']}")
        self.stdout.write(f"recebido_valor: {report['expected']['recebido']}")
        self.stdout.write(f"status_counts: {report['expected']['status_counts']}")
        self.stdout.write(f"financeiro_before: {report['financeiro_before']}")
        self.stdout.write(f"parcelas_preview: {report['parcelas_preview']}")

        if not options["apply"]:
            return

        self.stdout.write(f"pagamentos_before_total: {report['pagamentos_before_total']}")
        self.stdout.write(f"pagamentos_after_total: {report['pagamentos_after_total']}")
        self.stdout.write(
            "pagamentos_extra_fora_do_arquivo_total: "
            f"{report['pagamentos_extra_fora_do_arquivo_total']}"
        )
        self.stdout.write(f"financeiro_after_cached: {report['financeiro_after_cached']}")
        self.stdout.write(f"arquivo_retorno: {report['arquivo_retorno']}")
        self.stdout.write(f"financeiro: {report['financeiro']}")
        self.stdout.write(f"parcelas_apply: {report['parcelas_apply']}")
