from django.contrib import admin

from .models import EggProduction


@admin.register(EggProduction)
class EggProductionAdmin(admin.ModelAdmin):
    list_display = ["flock", "production_date", "good_eggs", "cracked_eggs", "total_eggs"]
    list_filter = ["production_date"]
