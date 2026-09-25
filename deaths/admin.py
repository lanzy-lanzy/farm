from django.contrib import admin

from .models import DeathRecord


@admin.register(DeathRecord)
class DeathRecordAdmin(admin.ModelAdmin):
    list_display = ["flock", "quantity", "cause_of_death", "date_recorded"]
    list_filter = ["date_recorded"]
