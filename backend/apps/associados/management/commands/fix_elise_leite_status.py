"""
Management command: corrige o status do Associado da Elise Leite (CPF 03488545369).

O associado está marcado como INATIVO no campo status, porém tem Ciclo 2 ativo
com pendência. Este comando:
1. Corrige o campo status do Associado para ATIVO.
2. Reativa refinanciamentos DESATIVADOS, restituindo-os para APROVADO_PARA_RENOVACAO
   (fila de pagamento da tesouraria), pois foram desativados como consequência
   do status INATIVO incorreto.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.associados.models import Associado
from apps.refinanciamento.models import Refinanciamento


class Command(BaseCommand):
    help = "Corrige status INATIVO → ATIVO e reativa refinanciamentos para a associada Elise Leite (CPF 03488545369)"

    def handle(self, *args, **options):
        cpf = "03488545369"

        try:
            associado = Associado.objects.get(cpf_cnpj=cpf)
        except Associado.DoesNotExist:
            raise CommandError(f"Associado com CPF {cpf} não encontrado.")

        self.stdout.write(f"Associado: {associado.nome_completo} (id={associado.id})")
        self.stdout.write(f"Status atual: {associado.status}")

        # Corrige status do associado
        if associado.status != Associado.Status.ATIVO:
            associado.status = Associado.Status.ATIVO
            associado.save(update_fields=["status", "updated_at"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Status atualizado para ATIVO para {associado.nome_completo}."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Status já é ATIVO. Nenhuma alteração no associado."))

        # Reativa refinanciamentos DESATIVADOS
        refinanciamentos_desativados = Refinanciamento.objects.filter(
            associado=associado,
            status=Refinanciamento.Status.DESATIVADO,
        )
        count = refinanciamentos_desativados.count()
        if count == 0:
            self.stdout.write("Nenhum refinanciamento DESATIVADO encontrado. Nenhuma alteração necessária.")
            return

        for refin in refinanciamentos_desativados:
            self.stdout.write(
                f"  Refinanciamento id={refin.id}: DESATIVADO → APROVADO_PARA_RENOVACAO"
            )
            refin.status = Refinanciamento.Status.APROVADO_PARA_RENOVACAO
            refin.save(update_fields=["status", "updated_at"])

        self.stdout.write(
            self.style.SUCCESS(
                f"{count} refinanciamento(s) reativado(s) para APROVADO_PARA_RENOVACAO."
            )
        )
