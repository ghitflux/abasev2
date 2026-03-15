# Generated manually for competência integrity support.

import django.db.models.deletion
from django.db import migrations, models


def _build_lock(associado_id, referencia_mes):
    if not associado_id or not referencia_mes:
        return None
    return f"{associado_id}:{referencia_mes.strftime('%Y-%m')}"


def populate_parcela_associado_and_lock(apps, schema_editor):
    Parcela = apps.get_model("contratos", "Parcela")

    active_counts = {}
    snapshots = []

    queryset = Parcela.objects.select_related("ciclo__contrato").all().order_by("id")
    for parcela in queryset.iterator():
        associado_id = parcela.associado_id or parcela.ciclo.contrato.associado_id
        is_active = parcela.deleted_at is None and parcela.status != "cancelado"
        if is_active:
            key = (associado_id, parcela.referencia_mes)
            active_counts[key] = active_counts.get(key, 0) + 1
        snapshots.append((parcela.id, associado_id, parcela.referencia_mes, is_active))

    for parcela_id, associado_id, referencia_mes, is_active in snapshots:
        competencia_lock = None
        if is_active and active_counts.get((associado_id, referencia_mes), 0) == 1:
            competencia_lock = _build_lock(associado_id, referencia_mes)
        Parcela.objects.filter(pk=parcela_id).update(
            associado_id=associado_id,
            competencia_lock=competencia_lock,
        )


def clear_competencia_lock(apps, schema_editor):
    Parcela = apps.get_model("contratos", "Parcela")
    Parcela.objects.all().update(competencia_lock=None)


class Migration(migrations.Migration):
    dependencies = [
        ("associados", "0006_associado_agencia_associado_anticipations_json_and_more"),
        ("contratos", "0002_contrato_auxilio_liberado_em_contrato_contato_web_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="parcela",
            name="associado",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="parcelas",
                to="associados.associado",
            ),
        ),
        migrations.AddField(
            model_name="parcela",
            name="competencia_lock",
            field=models.CharField(blank=True, max_length=32, null=True),
        ),
        migrations.RunPython(
            populate_parcela_associado_and_lock,
            reverse_code=clear_competencia_lock,
        ),
        migrations.AlterField(
            model_name="parcela",
            name="associado",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="parcelas",
                to="associados.associado",
            ),
        ),
        migrations.AlterField(
            model_name="parcela",
            name="competencia_lock",
            field=models.CharField(
                blank=True,
                max_length=32,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddIndex(
            model_name="parcela",
            index=models.Index(
                fields=["associado", "referencia_mes"],
                name="contratos_p_associa_d43752_idx",
            ),
        ),
    ]
