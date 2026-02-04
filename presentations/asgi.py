"""ASGI config for presentations project."""
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import presentations_app.routing

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "presentations.settings")

http_application = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": http_application,
        "websocket": AuthMiddlewareStack(
            URLRouter(presentations_app.routing.websocket_urlpatterns)
        ),
    }
)
