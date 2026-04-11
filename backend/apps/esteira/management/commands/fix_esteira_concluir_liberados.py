"""
Management command: conclui EsteiraItems que estão travados em etapa=ANALISE
mas cujo contrato já teve auxilio_liberado_em preenchido (pagamento liberado).

Esses registros nunca foram avançados para CONCLUIDO quando o pagamento foi
liberado, fazendo com que 437 associados apareçam incorretamente como
"Novos Contratos" no dashboard de análise.

O que este comando faz:
1. Identifica EsteiraItems com etapa_atual=ANALISE onde o associado tem
   ao menos um contrato com auxilio_liberado_em preenchido.
2. Move esses itens para etapa_atual=CONCLUIDO / status=APROVADO,
   usando auxilio_liberado_em do contrato mais recente como concluido_em.
3. Corrige os contratos associados que ainda estão em status=em_analise
   apesar de terem auxilio_liberado_em preenchido → status=ativo.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.contratos.models import Contrato
from apps.esteira.models import EsteiraItem


class Command(BaseCommand):
    help = (
        "Conclui EsteiraItems travados em ANALISE cujo contrato já teve "
        "pagamento liberado (auxilio_liberado_em preenchido)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas lista o que seria alterado, sem persistir.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN — nenhuma alteração será salva ==="))

        # ── 1. EsteiraItems a concluir ──────────────────────────────────────
        items_qs = (
            EsteiraItem.objects.filter(etapa_atual=EsteiraItem.Etapa.ANALISE)
            .filter(associado__contratos__auxilio_liberado_em__isnull=False)
            .select_related("associado")
            .prefetch_related("associado__contratos")
            .distinct()
        )

        total_items = items_qs.count()
        self.stdout.write(f"EsteiraItems a concluir: {total_items}")

        # ── 2. Contratos a corrigir (em_analise com pagamento liberado) ──────
        # Excluir contratos cujo associado está na fila de TESOURARIA para
        # não interferir no fluxo de pagamento em andamento.
        contratos_qs = Contrato.objects.filter(
            status=Contrato.Status.EM_ANALISE,
            auxilio_liberado_em__isnull=False,
        ).exclude(
            associado__esteira_item__etapa_atual=EsteiraItem.Etapa.TESOURARIA
        ).select_related("associado")

        total_contratos = contratos_qs.count()
        self.stdout.write(f"Contratos em_analise com auxilio_liberado_em: {total_contratos}")

        if dry_run:
            self.stdout.write("\nExemplos (primeiros 10 EsteiraItems):")
            for item in items_qs[:10]:
                contrato = (
                    item.associado.contratos
                    .filter(auxilio_liberado_em__isnull=False)
                    .order_by("-auxilio_liberado_em")
                    .first()
                )
                self.stdout.write(
                    f"  EsteiraItem id={item.id} "
                    f"associado={item.associado.nome_completo} "
                    f"auxilio_liberado_em={contrato.auxilio_liberado_em if contrato else 'N/A'}"
                )
            self.stdout.write(self.style.WARNING("Dry run concluído. Nenhuma alteração feita."))
            return

        # ── 3. Executar correções ────────────────────────────────────────────
        items_corrigidos = 0
        contratos_corrigidos = 0

        with transaction.atomic():
            # Corrigir EsteiraItems
            for item in items_qs.iterator(chunk_size=100):
                contrato = (
                    item.associado.contratos
                    .filter(auxilio_liberado_em__isnull=False)
                    .order_by("-auxilio_liberado_em")
                    .first()
                )
                if contrato and contrato.auxilio_liberado_em:
                    # auxilio_liberado_em é um campo date — converter para datetime aware
                    from datetime import datetime, time
                    concluido_em = timezone.make_aware(
                        datetime.combine(contrato.auxilio_liberado_em, time(12, 0))
                    )
                else:
                    concluido_em = timezone.now()

                item.etapa_atual = EsteiraItem.Etapa.CONCLUIDO
                item.status = EsteiraItem.Situacao.APROVADO
                item.concluido_em = concluido_em
                item.save(update_fields=["etapa_atual", "status_atual", "status", "concluido_em", "updated_at"])
                items_corrigidos += 1

            # Corrigir contratos em_analise com pagamento liberado
            contratos_corrigidos = contratos_qs.update(status=Contrato.Status.ATIVO)

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ {items_corrigidos} EsteiraItem(s) movidos para CONCLUIDO/APROVADO."
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ {contratos_corrigidos} Contrato(s) atualizados de em_analise → ativo."
            )
        )
