from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("contratos", "0009_contrato_cancelado_em_contrato_cancelamento_motivo_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrato",
            name="contrato_canonico",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="contratos_sombra",
                to="contratos.contrato",
            ),
        ),
        migrations.AddField(
            model_name="contrato",
            name="tipo_unificacao",
            field=models.CharField(
                blank=True,
                choices=[
                    ("retimp_shadow", "Contrato RETIMP sombra"),
                    ("duplicate_ctr_shadow", "Contrato CTR duplicado sombra"),
                ],
                default="",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="contrato",
            name="unificado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
