from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("importacao", "0006_alter_arquivoretornoitem_resultado_processamento_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="arquivoretorno",
            name="dry_run_resultado",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="arquivoretorno",
            name="status",
            field=models.CharField(
                choices=[
                    ("aguardando_confirmacao", "Aguardando Confirmação"),
                    ("pendente", "Pendente"),
                    ("processando", "Processando"),
                    ("concluido", "Concluído"),
                    ("erro", "Erro"),
                ],
                default="pendente",
                max_length=24,
            ),
        ),
    ]
