from django.contrib import admin

from .models import Product, SalesRecord


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ["product_name", "product_type", "quantity", "unit_price", "total_amount", "date_sold"]
    list_filter = ["product_type", "payment_status"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "product_type", "unit_label", "unit_price", "is_active"]
    list_filter = ["product_type", "is_active"]
    search_fields = ["name"]
