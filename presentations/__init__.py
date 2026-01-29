"""Presentations project package initializer."""

from __future__ import annotations

from .celery import app as celery_app  # noqa: F401 (expose app for Celery discovery)
