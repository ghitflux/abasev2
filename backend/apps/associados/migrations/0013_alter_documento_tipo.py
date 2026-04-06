from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("associados", "0012_associado_importacao_retorno_fields"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documento",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("rg", "RG"),
                    ("cpf", "CPF"),
                    ("documento_frente", "Documento (frente)"),
                    ("documento_verso", "Documento (verso)"),
                    ("comprovante_residencia", "Comprovante de residência"),
                    ("divulgacao", "Divulgação"),
                    ("contracheque", "Contracheque"),
                    ("termo_adesao", "Termo de adesão"),
                    ("termo_antecipacao", "Termo de antecipação"),
                    ("anexo_extra_1", "Anexo extra 1"),
                    ("anexo_extra_2", "Anexo extra 2"),
                    ("outro", "Outro"),
                ],
                max_length=40,
            ),
        ),
    ]
