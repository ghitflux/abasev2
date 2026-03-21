from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tesouraria", "0006_pagamento_legacy_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PagamentoNotificacao",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "data_referencia_negocio",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("lida_em", models.DateTimeField(blank=True, null=True)),
                (
                    "agente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pagamento_notificacoes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "pagamento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notificacoes",
                        to="tesouraria.pagamento",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="pagamentonotificacao",
            constraint=models.UniqueConstraint(
                fields=("pagamento", "agente"),
                name="uniq_pagamento_notificacao_por_agente",
            ),
        ),
    ]
