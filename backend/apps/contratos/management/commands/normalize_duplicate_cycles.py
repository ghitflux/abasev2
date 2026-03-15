from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.contratos.cycle_normalization import normalize_duplicate_cycles


class Command(BaseCommand):
    help = (
        "Normaliza ciclos duplicados com mesmo associado, numero e período, "
        "sincronizando status das parcelas duplicadas sem cancelar contratos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cpf", dest="cpf_cnpj", help="Filtra por CPF/CNPJ.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Executa a normalização. Sem este flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        execute = options["execute"]
        cpf_cnpj = options.get("cpf_cnpj")
        summary = normalize_duplicate_cycles(cpf_cnpj=cpf_cnpj, execute=execute)

        if not execute:
            self.stdout.write(self.style.WARNING("Dry-run: nenhuma alteração foi aplicada."))

        self.stdout.write(
            "\n".join(
                [
                    f"Grupos duplicados: {summary['groups']}",
                    f"Ciclos duplicados: {summary['duplicate_cycles']}",
                    f"Itens do retorno reatribuídos: {summary['reassigned_return_items']}",
                ]
            )
        )

        for resolution in summary["resolutions"][:20]:
            self.stdout.write(
                (
                    "keep ciclo={canonical_cycle} contrato={canonical_contract} | "
                    "sync ciclo={duplicate_cycle} contrato={duplicate_contract} | "
                    "retorno={reassigned}"
                ).format(
                    canonical_cycle=resolution.canonical_cycle_id,
                    canonical_contract=resolution.canonical_contract_id,
                    duplicate_cycle=resolution.duplicate_cycle_id,
                    duplicate_contract=resolution.duplicate_contract_id,
                    reassigned=resolution.reassigned_return_items,
                )
            )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run concluído. Execute novamente com --execute para aplicar."
                )
            )
