from django.db import migrations
from django.utils import timezone


def approve_existing(apps, schema_editor):
    Supplier = apps.get_model("suppliers", "Supplier")
    Supplier.objects.update(verification_status="approved", verified_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [
        ("suppliers", "0002_supplier_dti_registration_supplier_payment_terms_and_more"),
    ]

    operations = [
        migrations.RunPython(approve_existing, reverse_code=migrations.RunPython.noop),
    ]
