"""ASGI config for presentations project."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "presentations.settings")

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

http_application = get_asgi_application()

import presentations_app.routing  # noqa: E402 — must come after get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": http_application,
        "websocket": AuthMiddlewareStack(
            URLRouter(presentations_app.routing.websocket_urlpatterns)
        ),
    }
)
