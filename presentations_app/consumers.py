"""Websocket consumers for progress updates."""

from __future__ import annotations

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.urls import reverse

from .models import Presentation


class PresentationProgressConsumer(AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.presentation_id: str = ""
        self.group_name: str = ""

    async def connect(self) -> None:
        self.presentation_id = self.scope["url_route"]["kwargs"]["presentation_id"]
        self.group_name = f"presentation_{self.presentation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_initial_state()

    async def _send_initial_state(self) -> None:
        try:
            presentation = await sync_to_async(Presentation.objects.get)(
                id=self.presentation_id
            )
        except Presentation.DoesNotExist:
            return

        last_log = await sync_to_async(
            lambda: presentation.logs.filter(stage__isnull=False).last()
        )()

        stage = last_log.stage if last_log else presentation.status
        percent = last_log.percent if last_log and last_log.percent is not None else 0

        payload: dict = {"stage": stage, "percent": percent}

        if presentation.files:
            payload["files"] = presentation.files
            payload["file_urls"] = [
                reverse(
                    "presentation-file-download",
                    kwargs={
                        "presentation_id": str(presentation.id),
                        "file_index": i,
                    },
                )
                for i in range(len(presentation.files))
            ]

        await self.send_json(payload)

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def progress_message(self, event) -> None:
        await self.send_json(event["payload"])
