from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.overdue_forecast_correction import (
    OverdueForecastCorrectionError,
    parse_competencia_argument,
    run_overdue_forecast_correction,
)


class Command(BaseCommand):
    help = (
        "Saneia parcelas em previsão de competências passadas, alinhando com o "
        "retorno importado quando existir e marcando o restante como não descontado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--competencia-inicial",
            required=True,
            help="Competência inicial no formato YYYY-MM.",
        )
        parser.add_argument(
            "--competencia-final",
            required=True,
            help="Competência final no formato YYYY-MM.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção no banco. Sem esta flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        try:
            competencia_inicial = parse_competencia_argument(options["competencia_inicial"])
            competencia_final = parse_competencia_argument(options["competencia_final"])
            report = run_overdue_forecast_correction(
                competencia_inicial=competencia_inicial,
                competencia_final=competencia_final,
                apply=bool(options["apply"]),
            )
        except OverdueForecastCorrectionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"modo: {report['mode']}")
        self.stdout.write(f"competencia_inicial: {report['competencia_inicial']}")
        self.stdout.write(f"competencia_final: {report['competencia_final']}")
        self.stdout.write(
            "competencias_processadas: "
            + ",".join(report["competencias_processadas"])
        )
        summary = report["summary"]
        self.stdout.write(f"parcelas_avaliadas: {summary['parcelas_avaliadas']}")
        self.stdout.write(f"parcelas_descontado: {summary['parcelas_descontado']}")
        self.stdout.write(
            f"parcelas_nao_descontado: {summary['parcelas_nao_descontado']}"
        )
        self.stdout.write(f"parcelas_sem_item: {summary['parcelas_sem_item']}")
        self.stdout.write(f"cpf_conflito_total: {summary['cpf_conflito_total']}")

        for row in report["results"]:
            self.stdout.write(
                f"{row['competencia']}: avaliadas={row['parcelas_avaliadas']} "
                f"descontado={row['descontado']} "
                f"nao_descontado={row['nao_descontado']} "
                f"sem_item={row['sem_item']} "
                f"cpf_conflito_total={row['cpf_conflito_total']}"
            )

