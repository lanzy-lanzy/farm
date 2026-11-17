from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("buyers", "0004_orderrequest_source")]
    operations = [migrations.AlterField(model_name="orderrequest", name="requested_date", field=models.DateField(null=True, blank=True))]
