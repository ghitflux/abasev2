from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.accounts.legacy_restore_runtime import select_restore_uploaded_by
from apps.associados.models import Associado, only_digits
from apps.esteira.services import EsteiraService


class Command(BaseCommand):
    help = (
        "Cria itens iniciais de esteira para cadastros self-service que possuem "
        "usuário vinculado e ainda não entraram na fila operacional."
    )

    def add_arguments(self, parser):
        parser.add_argument("--cpf", help="Filtra por CPF/CNPJ do associado.")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Persiste as alterações. Sem esta flag, roda em dry-run.",
        )

    def handle(self, *args, **options):
        cpf = only_digits(options.get("cpf") or "")
        execute = bool(options.get("execute"))

        queryset = (
            Associado.objects.select_related("user")
            .filter(
                user__isnull=False,
                esteira_item__isnull=True,
                status__in=[
                    Associado.Status.CADASTRADO,
                    Associado.Status.EM_ANALISE,
                    Associado.Status.PENDENTE,
                ],
            )
            .order_by("created_at", "id")
        )
        if cpf:
            queryset = queryset.filter(cpf_cnpj=cpf)

        associados = list(queryset)
        self.stdout.write(f"Associados elegíveis: {len(associados)}")

        if not execute or not associados:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run concluído. Use --execute para persistir as alterações."
                )
            )
            return

        actor = select_restore_uploaded_by()
        created = 0
        for associado in associados:
            _esteira, was_created = EsteiraService.garantir_item_inicial_cadastro(
                associado,
                actor,
                observacao="Backfill da esteira inicial para cadastro self-service.",
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill concluído: {created} item(ns) de esteira criado(s)."
            )
        )
