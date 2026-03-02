"""Django settings for the presentations project."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _list_env(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [host.strip() for host in raw.split(",") if host.strip()]


def _read_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    return default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    cleaned = value.strip()
    if "*" in cleaned:
        try:
            parts = [int(part.strip()) for part in cleaned.split("*")]
            product = 1
            for part in parts:
                product *= part
            return product
        except ValueError:
            return default
    try:
        return int(cleaned)
    except ValueError:
        return default


SECRET_KEY = _read_env("DJANGO_SECRET_KEY", "django-insecure-REPLACE_WITH_YOUR_SECRET_KEY")
DEBUG = _bool_env("DJANGO_DEBUG", True)
ALLOWED_HOSTS = _list_env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "presentations_app.apps.PresentationsAppConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "presentations.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "presentations.wsgi.application"
ASGI_APPLICATION = "presentations.asgi.application"

default_engine = os.getenv("DJANGO_DB_ENGINE", "django.db.backends.sqlite3")
database_name = _read_env("DJANGO_DB_NAME")

if default_engine == "django.db.backends.sqlite3":
    resolved_name = database_name or BASE_DIR / "db.sqlite3"
else:
    resolved_name = database_name or "presentations"

DATABASES = {
    "default": {
        "ENGINE": default_engine,
        "NAME": str(resolved_name),
        "USER": _read_env("DJANGO_DB_USER", ""),
        "PASSWORD": _read_env("DJANGO_DB_PASSWORD", ""),
        "HOST": _read_env("DJANGO_DB_HOST", "localhost"),
        "PORT": _read_env("DJANGO_DB_PORT", ""),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

CELERY_BROKER_URL = _read_env("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = _read_env("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PRESENTATIONS_ASSETS_DIR = str(
    BASE_DIR / _read_env("PRESENTATIONS_ASSETS_DIR", "generated_presentations")
)
PRESENTATIONS_GENERATION_TIMEOUT_MS = _int_env(
    "PRESENTATIONS_GENERATION_TIMEOUT_MS",
    1200000,
)
PLAYWRIGHT_DEFAULT_TIMEOUT_MS = _int_env(
    "PLAYWRIGHT_DEFAULT_TIMEOUT_MS",
    90000,
)

CHANNEL_REDIS_URL = _read_env("CHANNEL_REDIS_URL", CELERY_BROKER_URL)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [CHANNEL_REDIS_URL]},
    }
}

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "DEBUG",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "filename": str(LOG_DIR / "app.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "level": "DEBUG",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "DEBUG"},
    "loggers": {
        "presentations_app": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "presentations_module": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
