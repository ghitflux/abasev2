from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contratos", "0010_contrato_contrato_canonico_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ciclo",
            name="status",
            field=models.CharField(
                choices=[
                    ("futuro", "Futuro"),
                    ("aberto", "Aberto"),
                    ("pendencia", "Pendência"),
                    ("ciclo_renovado", "Ciclo renovado"),
                    ("apto_a_renovar", "Apto a renovar"),
                    ("fechado", "Fechado"),
                ],
                default="futuro",
                max_length=20,
            ),
        ),
    ]
