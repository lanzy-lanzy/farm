from django.contrib import admin

from .models import FlockBatch


@admin.register(FlockBatch)
class FlockBatchAdmin(admin.ModelAdmin):
    list_display = ["batch_number", "breed", "quantity", "current_quantity", "growing_stage", "status"]
    list_filter = ["status", "growing_stage"]
    search_fields = ["batch_number", "breed"]
