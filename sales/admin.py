from django.contrib import admin

from .models import Product, SalesRecord


@admin.register(SalesRecord)
class SalesRecordAdmin(admin.ModelAdmin):
    list_display = ["product_name", "product_type", "quantity", "unit_price", "total_amount", "date_sold"]
    list_filter = ["product_type", "payment_status"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "product_type", "unit_label", "unit_price", "is_active", "created_by"]
    list_filter = ["product_type", "is_active"]
    search_fields = ["name"]
    readonly_fields = ["created_by", "created_at", "updated_at"]

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
