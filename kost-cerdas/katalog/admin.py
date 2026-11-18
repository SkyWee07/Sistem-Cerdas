from django.contrib import admin
from .models import Kos


@admin.register(Kos)
class KosAdmin(admin.ModelAdmin):
    list_display = ("nama", "harga", "jarak_km", "rating", "ac")
    list_filter = ("ac",)
    search_fields = ("nama",)
    ordering = ("nama",)
