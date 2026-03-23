from django.db import migrations, models


def migrate_operational_refinanciamentos(apps, schema_editor):
    Refinanciamento = apps.get_model("refinanciamento", "Refinanciamento")

    base_queryset = Refinanciamento.objects.filter(
        deleted_at__isnull=True,
        origem="operacional",
        legacy_refinanciamento_id__isnull=True,
        executado_em__isnull=True,
    )
    base_queryset.filter(status="aprovado").update(
        status="aprovado_analise_renovacao"
    )
    base_queryset.filter(status="concluido", data_ativacao_ciclo__isnull=True).update(
        status="aprovado_analise_renovacao"
    )
    base_queryset.filter(status="aprovado_para_renovacao").update(
        status="aprovado_analise_renovacao"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("refinanciamento", "0008_comprovante_reference_path"),
    ]

    operations = [
        migrations.AlterField(
            model_name="refinanciamento",
            name="status",
            field=models.CharField(
                choices=[
                    ("apto_a_renovar", "Apto a renovar"),
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
        migrations.AlterField(
            model_name="comprovante",
            name="origem",
            field=models.CharField(
                choices=[
                    ("efetivacao_contrato", "Efetivação do contrato"),
                    ("solicitacao_renovacao", "Solicitação de renovação"),
                    ("analise_renovacao", "Análise da renovação"),
                    ("tesouraria_renovacao", "Tesouraria da renovação"),
                    ("legado", "Legado"),
                    ("outro", "Outro"),
                ],
                default="outro",
                max_length=40,
            ),
        ),
        migrations.RunPython(
            migrate_operational_refinanciamentos,
            migrations.RunPython.noop,
        ),
    ]
