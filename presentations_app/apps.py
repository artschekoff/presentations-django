"""AppConfig for the presentations_app application."""

from django.apps import AppConfig


class PresentationsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "presentations_app"
    verbose_name = "Presentations"

    def ready(self) -> None:
        import importlib.metadata
        import logging
        import pathlib

        logger = logging.getLogger(__name__)

        version_file = pathlib.Path(__file__).resolve().parent.parent / "VERSION"
        app_version = version_file.read_text().strip() if version_file.exists() else "unknown"

        try:
            module_version = importlib.metadata.version("presentations_module")
        except importlib.metadata.PackageNotFoundError:
            module_version = "unknown"

        logger.info("presentations-django v%s | presentations-module v%s", app_version, module_version)
