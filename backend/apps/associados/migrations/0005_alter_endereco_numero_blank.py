from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("associados", "0004_alter_associado_matricula_orgao_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="endereco",
            name="numero",
            field=models.CharField(blank=True, max_length=60),
        ),
    ]
