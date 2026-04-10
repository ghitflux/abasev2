from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contratos", "0011_alter_ciclo_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="contrato",
            name="allow_small_value_renewal",
            field=models.BooleanField(default=False),
        ),
    ]
