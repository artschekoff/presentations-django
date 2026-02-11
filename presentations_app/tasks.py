"""Celery tasks for generating presentations."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Iterable

from asgiref.sync import sync_to_async
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.urls import reverse
from playwright.async_api import async_playwright

from presentations_module import SokraticSource

from .models import Presentation, PresentationLog

logger = logging.getLogger(__name__)


async def _send_progress_async(presentation_id: str, payload: dict[str, Any]) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    await channel_layer.group_send(
        f"presentation_{presentation_id}",
        {"type": "progress.message", "payload": payload},
    )


def _safe_files(value: Iterable[str] | None) -> list[str]:
    if not value:
        return []
    return [str(item) for item in value]


def _log_event(
    presentation: Presentation,
    *,
    kind: str,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
    stage: str | None = None,
    percent: int | None = None,
) -> None:
    PresentationLog.objects.create(
        presentation=presentation,
        kind=kind,
        message=message or "",
        payload=payload or {},
        stage=stage,
        percent=percent,
    )


@shared_task(bind=True)
def generate_presentation_task(self, presentation_id: str) -> None:
    sokratic_logger = logging.getLogger("presentations_module")
    if not sokratic_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        sokratic_logger.addHandler(handler)
    sokratic_logger.setLevel(logging.DEBUG)
    sokratic_logger.propagate = True

    logger.info("Generate task started for presentation %s", presentation_id)
    try:
        presentation = Presentation.objects.get(id=presentation_id)
    except Presentation.DoesNotExist:
        logger.error("Presentation %s does not exist", presentation_id)
        return

    Presentation.objects.filter(id=presentation_id).update(status="processing")
    _log_event(
        presentation,
        kind="status",
        message="Queued for generation",
        stage="queued",
        percent=0,
    )
    asyncio.run(
        _send_progress_async(
            presentation_id,
            {
                "stage": "queued",
                "step": 0,
                "total_steps": 7,
                "percent": 0,
            },
        )
    )

    async def _run() -> list[str]:
        files: list[str] = []
        apw = await async_playwright().start()
        logger.info("Playwright started for presentation %s", presentation_id)
        source = SokraticSource(
            apw,
            logger=sokratic_logger,
            assets_dir=settings.PRESENTATIONS_ASSETS_DIR,
            generation_timeout=settings.PRESENTATIONS_GENERATION_TIMEOUT_MS,
        )
        if not hasattr(source, "browser"):
            source.browser = None

        try:
            headless = (
                os.environ.get("PRESENTATIONS_HEADLESS", "true").lower() == "true"
            )
            logger.info(
                "Starting browser in %s mode for presentation %s",
                "headless" if headless else "headed",
                presentation_id,
            )

            await source.init_async(headless=headless)

            login = os.environ.get("SOKRATIC_USERNAME")
            password = os.environ.get("SOKRATIC_PASSWORD")
            if not login or not password:
                raise RuntimeError("SOKRATIC_USERNAME/SOKRATIC_PASSWORD are not set")

            logger.info(
                "Authenticating SokraticSource for presentation %s", presentation_id
            )
            await source.authenticate(login=login, password=password)

            async for update in source.generate_presentation(
                topic=presentation.topic,
                language=presentation.language,
                slides_amount=presentation.slides_amount,
                audience=presentation.audience,
                author=presentation.author,
            ):
                payload = dict(update)
                payload["presentation_id"] = presentation_id
                if payload.get("files"):
                    files_now = _safe_files(payload.get("files"))
                    await sync_to_async(
                        Presentation.objects.filter(id=presentation_id).update
                    )(files=files_now)
                    payload["file_urls"] = [
                        reverse(
                            "presentation-file-download",
                            kwargs={
                                "presentation_id": presentation_id,
                                "file_index": index,
                            },
                        )
                        for index in range(len(files_now))
                    ]
                await _send_progress_async(presentation_id, payload)
                await sync_to_async(_log_event)(
                    presentation,
                    kind="progress",
                    payload=payload,
                    stage=payload.get("stage"),
                    percent=payload.get("percent"),
                )
                if payload.get("stage"):
                    logger.info(
                        "Progress %s: stage=%s percent=%s",
                        presentation_id,
                        payload.get("stage"),
                        payload.get("percent"),
                    )

                if update.get("stage") == "done":
                    files = _safe_files(update.get("files"))
        finally:
            logger.info("Disposing source for presentation %s", presentation_id)
            await source.dispose_async()
            logger.info("Stopping Playwright for presentation %s", presentation_id)
            await apw.stop()

        return files

    try:
        files = asyncio.run(_run())
        logger.info(
            "Generate task completed for presentation %s (files=%d)",
            presentation_id,
            len(files),
        )
        Presentation.objects.filter(id=presentation_id).update(
            status="done",
            files=files,
        )
        _log_event(
            presentation,
            kind="status",
            message="Presentation generated",
            stage="done",
            percent=100,
            payload={"files": files},
        )
        file_urls = [
            reverse(
                "presentation-file-download",
                kwargs={"presentation_id": presentation_id, "file_index": index},
            )
            for index in range(len(files))
        ]
        asyncio.run(
            _send_progress_async(
                presentation_id,
                {
                    "stage": "completed",
                    "step": 7,
                    "total_steps": 7,
                    "percent": 100,
                    "files": files,
                    "file_urls": file_urls,
                },
            )
        )
    except Exception as exc:  # pragma: no cover - runtime failures surfaced via socket
        logger.exception(
            "Generate task failed for presentation %s: %s", presentation_id, exc
        )
        Presentation.objects.filter(id=presentation_id).update(status="failed")
        _log_event(
            presentation,
            kind="error",
            message=str(exc),
            stage="failed",
            percent=0,
        )
        asyncio.run(
            _send_progress_async(
                presentation_id,
                {
                    "stage": "failed",
                    "step": 0,
                    "total_steps": 7,
                    "percent": 0,
                    "error": str(exc),
                },
            )
        )
        logger.exception("Failed to generate presentation %s", presentation_id)
