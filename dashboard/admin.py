from django.contrib import admin

from .models import FarmProfile


@admin.register(FarmProfile)
class FarmProfileAdmin(admin.ModelAdmin):
    list_display = ["farm_name", "location", "farm_type", "user"]
    list_filter = ["farm_type"]
    search_fields = ["farm_name", "location"]
