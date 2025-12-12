import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Models", "0007_align_insumo_schema"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReservaInsumo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("cantidad_utilizada", models.PositiveIntegerField()),
                (
                    "insumo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="Models.insumo"
                    ),
                ),
                (
                    "reserva",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insumos_utilizados",
                        to="Models.reserva",
                    ),
                ),
            ],
            options={
                "db_table": "RESERVA_INSUMO",
                "managed": True,
                "unique_together": {("reserva", "insumo")},
            },
        ),
    ]
