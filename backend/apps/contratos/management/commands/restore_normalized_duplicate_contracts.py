from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.contratos.cycle_normalization import restore_normalized_duplicate_contracts


class Command(BaseCommand):
    help = (
        "Restaura contratos cancelados pela normalização antiga de ciclos duplicados, "
        "reabrindo contratos/ciclos e sincronizando o status das parcelas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica a restauração. Sem este flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        execute = options["execute"]
        summary = restore_normalized_duplicate_contracts(
            cpf_cnpj=options.get("cpf_cnpj"),
            execute=execute,
        )

        if not execute:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração foi aplicada."))

        self.stdout.write(
            "\n".join(
                [
                    f"Contratos encontrados: {summary['contracts']}",
                    f"Ciclos restaurados: {summary['restored_cycles']}",
                    f"Parcelas restauradas: {summary['restored_parcelas']}",
                ]
            )
        )

        for resolution in summary["resolutions"][:20]:
            self.stdout.write(
                (
                    "contrato={contract_id} codigo={contract_code} "
                    "source_contract={source_contract} ciclos={cycles} parcelas={parcelas}"
                ).format(
                    contract_id=resolution.contract_id,
                    contract_code=resolution.contract_code,
                    source_contract=resolution.source_contract_id or "-",
                    cycles=resolution.restored_cycles,
                    parcelas=resolution.restored_parcelas,
                )
            )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run concluído. Execute novamente com --execute para aplicar."
                )
            )
