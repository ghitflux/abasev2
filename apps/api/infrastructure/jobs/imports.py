from celery import shared_task
import csv
from ...core.models import Associado


@shared_task
def import_associados_csv(path: str) -> int:
    count = 0
    with open(path, newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            Associado.objects.update_or_create(
                cpf=row["cpf"],
                defaults={
                    "nome": row.get("nome", ""),
                    "email": row.get("email") or None,
                    "telefone": row.get("telefone") or None,
                    "endereco": row.get("endereco") or None,
                },
            )
            count += 1
    return count
