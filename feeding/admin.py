from django.contrib import admin

from .models import FeedingRecord


@admin.register(FeedingRecord)
class FeedingRecordAdmin(admin.ModelAdmin):
    list_display = ["flock", "feed_item", "quantity_used", "feeding_date"]
    list_filter = ["feeding_date"]
