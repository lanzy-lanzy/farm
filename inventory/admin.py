from django.contrib import admin

from .models import InventoryItem, InventoryCategory, Unit, InventoryTransaction


@admin.register(InventoryCategory)
class InventoryCategoryAdmin(admin.ModelAdmin):
    list_display = ["name"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation"]


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "quantity", "unit", "cost_per_unit", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ["item", "transaction_type", "quantity", "created_at"]
    list_filter = ["transaction_type"]
