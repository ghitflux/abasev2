from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("refinanciamento", "0010_comprovante_status_validacao"),
    ]

    operations = [
        migrations.AlterField(
            model_name="refinanciamento",
            name="status",
            field=models.CharField(
                choices=[
                    ("apto_a_renovar", "Apto a renovar"),
                    ("solicitado_para_liquidacao", "Solicitado para liquidação"),
                    ("em_analise_renovacao", "Em análise para renovação"),
                    (
                        "aprovado_analise_renovacao",
                        "Aprovado pela análise para renovação",
                    ),
                    ("aprovado_para_renovacao", "Aprovado para renovação"),
                    ("pendente_apto", "Pendente apto"),
                    ("bloqueado", "Bloqueado"),
                    ("concluido", "Concluído"),
                    ("desativado", "Desativado"),
                    ("revertido", "Revertido"),
                    ("efetivado", "Efetivado"),
                    ("solicitado", "Solicitado"),
                    ("em_analise", "Em análise"),
                    ("aprovado", "Aprovado"),
                    ("rejeitado", "Rejeitado"),
                ],
                default="pendente_apto",
                max_length=40,
            ),
        ),
    ]
