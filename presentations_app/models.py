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
