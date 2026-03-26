from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tesouraria", "0011_liquidacaocontratoanexo"),
    ]

    operations = [
        migrations.AddField(
            model_name="liquidacaocontrato",
            name="origem_solicitacao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("agente", "Agente"),
                    ("coordenacao", "Coordenação"),
                    ("administracao", "Administração"),
                    ("renovacao", "Renovação"),
                ],
                default="",
                max_length=20,
            ),
        ),
    ]
