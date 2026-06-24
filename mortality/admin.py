from django.contrib import admin

from .models import MortalityRecord


@admin.register(MortalityRecord)
class MortalityRecordAdmin(admin.ModelAdmin):
    list_display = ["flock", "quantity", "cause_of_death", "date_recorded"]
    list_filter = ["date_recorded"]
