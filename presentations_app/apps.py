"""AppConfig for the presentations_app application."""

from django.apps import AppConfig


class PresentationsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "presentations_app"
    verbose_name = "Presentations"
