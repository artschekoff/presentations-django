"""Websocket routing for presentation progress updates."""

from django.urls import re_path

from .consumers import PresentationProgressConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/presentations/(?P<presentation_id>[0-9a-f-]+)/$",
        PresentationProgressConsumer.as_asgi(),
    ),
]
