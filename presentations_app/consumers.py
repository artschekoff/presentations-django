"""Websocket consumers for progress updates."""

from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer


class PresentationProgressConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self.presentation_id = self.scope["url_route"]["kwargs"]["presentation_id"]
        self.group_name = f"presentation_{self.presentation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def progress_message(self, event) -> None:
        await self.send_json(event["payload"])
