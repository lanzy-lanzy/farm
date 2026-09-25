import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("expenses", "0002_expenserecord_supplier"),
    ]

    operations = [
        migrations.AddField(
            model_name="expenserecord",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
