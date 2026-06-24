from django.contrib import admin

from .models import SalesRecord


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ["product_name", "product_type", "quantity", "unit_price", "total_amount", "date_sold"]
    list_filter = ["product_type", "payment_status"]
