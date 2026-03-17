from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tesouraria", "0005_baixamanual_data_referencia_negocio_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pagamento",
            name="legacy_tesouraria_pagamento_id",
            field=models.PositiveIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="pagamento",
            name="origem",
            field=models.CharField(
                choices=[
                    ("operacional", "Operacional"),
                    ("legado", "Legado"),
                    ("override_manual", "Override manual"),
                ],
                default="operacional",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="pagamento",
            name="referencias_externas",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
