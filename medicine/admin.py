from django.contrib import admin

from .models import MedicineRecord


@admin.register(MedicineRecord)
class MedicineRecordAdmin(admin.ModelAdmin):
    list_display = ["medicine_name", "flock", "medicine_type", "date_administered"]
    list_filter = ["medicine_type", "date_administered"]
