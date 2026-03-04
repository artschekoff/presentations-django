"""Django admin configuration for Presentation."""

from __future__ import annotations

from django.contrib import admin

from .models import Presentation, PresentationLog, UserToken


@admin.register(Presentation)
class PresentationAdmin(admin.ModelAdmin):
    list_display = ("topic", "language", "status", "created_at")
    list_filter = ("status", "language")
    search_fields = ("topic", "audience", "author")


@admin.register(PresentationLog)
class PresentationLogAdmin(admin.ModelAdmin):
    list_display = ("presentation", "kind", "stage", "percent", "created_at")
    list_filter = ("kind", "stage")
    search_fields = ("presentation__topic", "message")
    readonly_fields = ("presentation", "kind", "stage", "percent", "message", "payload", "created_at")


@admin.register(UserToken)
class UserTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "token")
    readonly_fields = ("token", "created_at")
