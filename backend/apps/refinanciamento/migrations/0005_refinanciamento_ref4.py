from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("refinanciamento", "0004_ajustevalor_data_referencia_negocio_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="refinanciamento",
            name="ref4",
            field=models.DateField(blank=True, null=True),
        ),
    ]
