from django.contrib import admin

from .models import Supplier, SupplyItem


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "phone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "contact_person"]


@admin.register(SupplyItem)
class SupplyItemAdmin(admin.ModelAdmin):
    list_display = ["name", "supplier", "unit_price", "inventory_item"]
    list_filter = ["supplier"]
    search_fields = ["name", "supplier__name"]
