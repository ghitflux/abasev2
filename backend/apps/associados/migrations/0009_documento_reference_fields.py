from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("associados", "0008_associado_data_referencia_negocio_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="documento",
            name="arquivo_referencia_path",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="documento",
            name="nome_original",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="documento",
            name="origem",
            field=models.CharField(
                choices=[
                    ("operacional", "Operacional"),
                    ("legado_cadastro", "Legado cadastro"),
                    ("outro", "Outro"),
                ],
                default="operacional",
                max_length=40,
            ),
        ),
    ]
