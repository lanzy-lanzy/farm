# Hand-written for the mortality -> deaths app rename.
#
# The model is pinned (via Meta.db_table) to the historical physical table
# "mortality_mortalityrecord", so running ``migrate deaths --fake-initial``
# detects the existing table, marks this migration applied without touching
# the schema, and every pre-existing row is preserved verbatim.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("flocks", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DeathRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date_recorded", models.DateField()),
                ("quantity", models.PositiveIntegerField()),
                (
                    "cause_of_death",
                    models.CharField(blank=True, max_length=200, null=True),
                ),
                ("symptoms", models.TextField(blank=True, null=True)),
                ("action_taken", models.TextField(blank=True, null=True)),
                ("remarks", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "flock",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="death_records",
                        to="flocks.flockbatch",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Death Record",
                "verbose_name_plural": "Death Records",
                "db_table": "mortality_mortalityrecord",
                "ordering": ["-date_recorded"],
            },
        ),
    ]
