"""Presentation persistence models."""

from __future__ import annotations

import uuid
from django.db import models


class Presentation(models.Model):
    """Django model that mirrors the shared PresentationDocument."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.CharField(max_length=255)
    language = models.CharField(max_length=64)
    slides_amount = models.PositiveIntegerField()
    audience = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=32, default="pending")
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

    def __str__(self) -> str:
        return f"{self.presentation_id} {self.kind} {self.stage or ''}".strip()
