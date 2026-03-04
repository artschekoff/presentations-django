"""Presentation persistence models."""

from __future__ import annotations

import uuid
import secrets
from django.db import models
from django.conf import settings


class Presentation(models.Model):
    """Django model that mirrors the shared PresentationDocument."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=255)
    language = models.CharField(max_length=64)
    slides_amount = models.PositiveIntegerField()
    grade = models.PositiveSmallIntegerField()
    subject = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    task_id = models.CharField(max_length=255, blank=True, null=True)
    book_id = models.IntegerField(blank=True, null=True)
    template = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=32, default="pending")
    retry_count = models.PositiveSmallIntegerField(default=0)
    processing_since = models.DateTimeField(null=True, blank=True)
    files = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.topic} ({self.language})"


class PresentationLog(models.Model):
    """Structured logs for presentation generation."""

    presentation = models.ForeignKey(
        Presentation, on_delete=models.CASCADE, related_name="logs"
    )
    kind = models.CharField(max_length=32)
    stage = models.CharField(max_length=64, blank=True, null=True)
    percent = models.PositiveIntegerField(blank=True, null=True)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)


class UserToken(models.Model):
    """API token for authenticated users."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_token",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Token for {self.user.username}"
