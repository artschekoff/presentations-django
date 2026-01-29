"""Django admin configuration for Presentation."""

from __future__ import annotations

from django.contrib import admin

from .models import Presentation


@admin.register(Presentation)
class PresentationAdmin(admin.ModelAdmin):
    list_display = ("topic", "language", "status", "created_at")
    list_filter = ("status", "language")
    search_fields = ("topic", "audience", "author")
