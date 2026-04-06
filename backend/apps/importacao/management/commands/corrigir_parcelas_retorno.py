from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.importacao.parcelas_retorno_correction import (
    ParcelasRetornoCorrectionError,
    parse_competencia_argument,
    run_parcelas_retorno_correction,
)


class Command(BaseCommand):
    help = (
        "Corrige em massa os status de parcelas de uma competência com base em um "
        "arquivo retorno ETIPI, sem rebuild de ciclos."
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
            help="ID opcional de ArquivoRetorno para usar como fonte.",
        )
        parser.add_argument(
            "--arquivo-path",
            dest="arquivo_path",
            help="Caminho opcional do arquivo retorno quando não houver ArquivoRetorno concluído.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica a correção no banco. Sem esta flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        try:
            competencia = parse_competencia_argument(options["competencia"])
            report = run_parcelas_retorno_correction(
                competencia=competencia,
                apply=bool(options["apply"]),
                arquivo_retorno_id=options.get("arquivo_retorno_id"),
                arquivo_path=options.get("arquivo_path"),
            )
        except ParcelasRetornoCorrectionError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"modo: {report['mode']}")
        self.stdout.write(f"competencia: {report['competencia_display']}")
        self.stdout.write(f"data_geracao: {report['data_geracao']}")
        self.stdout.write(f"fonte: {report['source']['label']}")
        self.stdout.write(f"fonte_path: {report['source']['path']}")
        self.stdout.write(f"linhas_brutas_total: {report['linhas_brutas_total']}")
        self.stdout.write(f"cpfs_unicos_total: {report['cpfs_unicos_total']}")
        self.stdout.write(f"cpfs_duplicados_total: {report['cpfs_duplicados_total']}")
        self.stdout.write(f"warnings_count: {report['warnings_count']}")
        self.stdout.write(f"parcelas_elegiveis_total: {report['parcelas_elegiveis_total']}")
        self.stdout.write(f"parcelas_descontado_total: {report['parcelas_descontado_total']}")
        self.stdout.write(f"parcelas_descontado_valor: {report['parcelas_descontado_valor']}")
        self.stdout.write(
            f"parcelas_nao_descontado_total: {report['parcelas_nao_descontado_total']}"
        )
        self.stdout.write(
            f"parcelas_nao_descontado_valor: {report['parcelas_nao_descontado_valor']}"
        )
        self.stdout.write(f"parcelas_sem_match_total: {report['parcelas_sem_match_total']}")
        self.stdout.write(f"parcelas_sem_match_valor: {report['parcelas_sem_match_valor']}")
        self.stdout.write(f"cpfs_sem_parcela_total: {report['cpfs_sem_parcela_total']}")

        if report["status_bruto_por_codigo"]:
            self.stdout.write("status_bruto_por_codigo:")
            for code, total in report["status_bruto_por_codigo"].items():
                self.stdout.write(f"  {code}: {total}")

        if report["cpfs_duplicados"]:
            self.stdout.write("cpfs_duplicados:")
            for row in report["cpfs_duplicados"]:
                linhas_ignoradas = ",".join(str(item) for item in row["linhas_ignoradas"])
                self.stdout.write(
                    f"  cpf={row['cpf_cnpj']} linha_mantida={row['linha_mantida']} "
                    f"linhas_ignoradas={linhas_ignoradas} status={row['status_codigo']} "
                    f"valor={row['valor_descontado']}"
                )

        if report["parcelas_sem_match"]:
            self.stdout.write("parcelas_sem_match:")
            for row in report["parcelas_sem_match"]:
                self.stdout.write(
                    f"  parcela_id={row['parcela_id']} cpf={row['cpf_cnpj']} "
                    f"status_atual={row['status_atual']}"
                )

        if report["cpfs_sem_parcela"]:
            self.stdout.write("cpfs_sem_parcela:")
            for row in report["cpfs_sem_parcela"]:
                self.stdout.write(
                    f"  cpf={row['cpf_cnpj']} linha={row['linha_numero']} "
                    f"status={row['status_codigo']} nome={row['nome_servidor']}"
                )

        smoke = report["smoke_test"]
        self.stdout.write(
            f"smoke_test: cpf={smoke['cpf_cnpj']} found={str(smoke['found']).lower()}"
        )
        for parcela in smoke["parcelas"]:
            self.stdout.write(
                f"  smoke_parcela id={parcela['id']} status={parcela['status']} "
                f"data_pagamento={parcela['data_pagamento']} valor={parcela['valor']}"
            )

