from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contratos", "0013_descartado_parcela"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrato",
            name="origem_operacional",
            field=models.CharField(
                choices=[
                    ("cadastro", "Cadastro"),
                    ("reativacao", "Reativação"),
                ],
                default="cadastro",
                max_length=20,
            ),
        ),
    ]
