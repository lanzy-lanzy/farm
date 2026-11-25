"""Rename seeded 'Manila Egg Traders' buyer contact to 'Tambulig Egg Traders'."""

from django.db import migrations


def rename_to_tambulig(apps, schema_editor):
    Buyer = apps.get_model("buyers", "Buyer")
    User = apps.get_model("accounts", "User")

    old_name = "Manila Egg Traders"
    new_name = "Tambulig Egg Traders"

    if not Buyer.objects.filter(name=new_name).exists():
        Buyer.objects.filter(name=old_name).update(name=new_name)
    User.objects.filter(first_name=old_name).update(first_name=new_name)


def rename_back(apps, schema_editor):
    Buyer = apps.get_model("buyers", "Buyer")
    User = apps.get_model("accounts", "User")

    old_name = "Manila Egg Traders"
    new_name = "Tambulig Egg Traders"

    if not Buyer.objects.filter(name=old_name).exists():
        Buyer.objects.filter(name=new_name).update(name=old_name)
    User.objects.filter(first_name=new_name).update(first_name=old_name)


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0002_seed_farm_data"),
    ]

    operations = [
        migrations.RunPython(rename_to_tambulig, rename_back),
    ]
