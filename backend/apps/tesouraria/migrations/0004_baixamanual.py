import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tesouraria", "0003_pagamento"),
        ("contratos", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BaixaManual",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("comprovante", models.FileField(upload_to="baixas_manuais/")),
                ("nome_comprovante", models.CharField(blank=True, max_length=255)),
                ("observacao", models.TextField(blank=True)),
                ("valor_pago", models.DecimalField(decimal_places=2, max_digits=10)),
                ("data_baixa", models.DateField()),
                (
                    "parcela",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="baixa_manual",
                        to="contratos.parcela",
                    ),
                ),
                (
                    "realizado_por",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="baixas_manuais",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
