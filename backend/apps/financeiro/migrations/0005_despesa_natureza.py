from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("financeiro", "0004_alter_despesa_descricao"),
    ]

    operations = [
        migrations.AddField(
            model_name="despesa",
            name="natureza",
            field=models.CharField(
                choices=[
                    ("despesa_operacional", "Despesa operacional"),
                    ("complemento_receita", "Complemento de receita"),
                ],
                default="despesa_operacional",
                max_length=30,
            ),
        ),
    ]
