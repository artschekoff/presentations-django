"""Django settings for the presentations project."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    from mongoengine import connect as mongoengine_connect
except ImportError:  # pragma: no cover - happens if dependencies aren’t installed yet
    mongoengine_connect = None

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

def _connect_mongoengine() -> None:
    if mongoengine_connect is None:
        return

    mongo_db = _read_env("MONGO_DB_NAME", "presentations")
    mongo_alias = _read_env("MONGO_ALIAS", "default")
    mongo_uri = _read_env("MONGO_URI")

    kwargs: dict[str, str] = {"db": mongo_db, "alias": mongo_alias}

    if mongo_uri:
        kwargs["host"] = mongo_uri
    else:
        kwargs["host"] = _read_env("MONGO_HOST", "localhost")
        port = _read_env("MONGO_PORT")
        if port:
            try:
                kwargs["port"] = int(port)
            except ValueError:
                kwargs["port"] = port
        username = _read_env("MONGO_USER")
        password = _read_env("MONGO_PASSWORD")
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password
        auth_source = _read_env("MONGO_AUTH_SOURCE")
        if auth_source:
            kwargs["authentication_source"] = auth_source

    mongoengine_connect(**kwargs)


_connect_mongoengine()
