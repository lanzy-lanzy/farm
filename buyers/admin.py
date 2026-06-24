from django.contrib import admin

from .models import Buyer


@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "phone", "buyer_type", "is_active"]
    list_filter = ["buyer_type", "is_active"]
    search_fields = ["name", "contact_person"]
