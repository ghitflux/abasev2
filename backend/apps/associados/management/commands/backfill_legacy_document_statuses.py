from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.associados.models import Associado, Documento, only_digits
from apps.esteira.models import DocIssue, Pendencia


class Command(BaseCommand):
    help = (
        "Aprova documentos legados de cadastro que já possuem arquivo local e não "
        "possuem pendência operacional aberta."
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
            Documento.objects.filter(
                origem=Documento.Origem.LEGADO_CADASTRO,
                status=Documento.Status.PENDENTE,
            )
            .exclude(arquivo="")
            .annotate(
                has_doc_issue=Exists(
                    DocIssue.objects.filter(
                        associado_id=OuterRef("associado_id"),
                        status=DocIssue.Status.INCOMPLETO,
                    )
                ),
                has_pendencia=Exists(
                    Pendencia.objects.filter(
                        esteira_item__associado_id=OuterRef("associado_id"),
                        status=Pendencia.Status.ABERTA,
                    )
                ),
            )
            .filter(has_doc_issue=False, has_pendencia=False)
            .select_related("associado")
        )

        if cpf:
            queryset = queryset.filter(associado__cpf_cnpj=cpf)

        documento_ids = list(queryset.values_list("id", flat=True))
        associado_ids = sorted(set(queryset.values_list("associado_id", flat=True)))

        self.stdout.write(
            f"Documentos elegíveis para aprovação: {len(documento_ids)} "
            f"(associados: {len(associado_ids)})"
        )

        if not execute or not documento_ids:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run concluído. Use --execute para persistir as alterações."
                )
            )
            return

        now = timezone.now()
        Documento.objects.filter(id__in=documento_ids).update(
            status=Documento.Status.APROVADO,
            updated_at=now,
        )

        for associado in Associado.objects.filter(id__in=associado_ids):
            associado.sync_documents_snapshot()

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfill concluído: {len(documento_ids)} documentos aprovados."
            )
        )
