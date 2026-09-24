from django.db import migrations
from django.utils import timezone


def approve_existing(apps, schema_editor):
    Buyer = apps.get_model("buyers", "Buyer")
    Buyer.objects.update(verification_status="approved", verified_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("buyers", "0002_buyer_credit_limit_buyer_rejection_reason_buyer_user_and_more"),
    ]

    operations = [
        migrations.RunPython(approve_existing, reverse_code=migrations.RunPython.noop),
    ]
