from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tesouraria", "0010_devolucaoassociado_quantidade_parcelas_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LiquidacaoContratoAnexo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("deleted_at", models.DateTimeField(blank=True, null=True)),
                ("data_referencia_negocio", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("arquivo", models.FileField(upload_to="liquidacoes_contrato/")),
                ("nome_arquivo", models.CharField(blank=True, max_length=255)),
                (
                    "liquidacao",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="anexos",
                        to="tesouraria.liquidacaocontrato",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
    ]
