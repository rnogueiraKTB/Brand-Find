from django.contrib import admin

from .models import BrandEntry


@admin.register(BrandEntry)
class BrandEntryAdmin(admin.ModelAdmin):
    list_display = ("brand", "inquire_to", "info_received_from", "last_changed_on")
    search_fields = ("brand", "inquire_to", "info_received_from", "notes")
    ordering = ("brand",)
    readonly_fields = ("last_changed_on",)
