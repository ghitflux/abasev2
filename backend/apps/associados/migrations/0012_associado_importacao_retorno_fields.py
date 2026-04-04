from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("associados", "0011_adminoverrideevent_adminoverridechange"),
    ]

    operations = [
        migrations.AddField(
            model_name="associado",
            name="arquivo_retorno_origem",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="associado",
            name="competencia_importacao_retorno",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="associado",
            name="data_geracao_importacao_retorno",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="associado",
            name="ultimo_arquivo_retorno",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="associado",
            name="status",
            field=models.CharField(
                choices=[
                    ("cadastrado", "Cadastrado"),
                    ("importado", "Importado"),
                    ("em_analise", "Em análise"),
                    ("ativo", "Ativo"),
                    ("pendente", "Pendente"),
                    ("inativo", "Inativo"),
                    ("inadimplente", "Inadimplente"),
                ],
                default="cadastrado",
                max_length=20,
            ),
        ),
    ]
