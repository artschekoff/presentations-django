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
from django.db.models import F, Q
from django.utils import timezone

from django.urls import reverse
from playwright.async_api import async_playwright

from presentations_module import SokraticSource, DownloadFormat

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


def _handle_task_failure(
    presentation: Presentation, presentation_id: str, exc: Exception
) -> None:
    logger.exception("Generate task failed for presentation %s: %s", presentation_id, exc)
    Presentation.objects.filter(id=presentation_id).update(retry_count=F("retry_count") + 1)
    retry_count = Presentation.objects.get(id=presentation_id).retry_count
    max_retries = 3

    if retry_count < max_retries:
        logger.info("Retrying presentation %s (attempt %d/%d)", presentation_id, retry_count, max_retries)
        # Set back to pending — the outbox relay will re-dispatch.
        Presentation.objects.filter(id=presentation_id).update(
            status="pending", files=[], processing_since=None
        )
        _log_event(
            presentation,
            kind="error",
            message=f"Attempt {retry_count}/{max_retries} failed: {exc}. Retrying…",
            stage="retrying",
            percent=0,
        )
        asyncio.run(
            _send_progress_async(
                presentation_id,
                {"stage": "retrying", "retry_count": retry_count, "max_retries": max_retries,
                 "percent": 0, "error": str(exc)},
            )
        )
    else:
        logger.error("Presentation %s failed after %d attempts", presentation_id, retry_count)
        Presentation.objects.filter(id=presentation_id).update(status="failed")
        _log_event(presentation, kind="error", message=str(exc), stage="failed", percent=0)
        asyncio.run(
            _send_progress_async(
                presentation_id,
                {"stage": "failed", "retry_count": retry_count, "max_retries": max_retries,
                 "step": 0, "total_steps": 7, "percent": 0, "error": str(exc)},
            )
        )


@shared_task
def generate_presentation_task(presentation_id: str) -> None:
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

    # Atomically claim the task: only proceed if status is still 'pending'.
    # This prevents double-execution when the relay dispatches duplicates.
    claimed = Presentation.objects.filter(
        id=presentation_id, status="pending"
    ).update(status="processing", processing_since=timezone.now())
    if not claimed:
        logger.info(
            "Presentation %s already claimed or finished, skipping.", presentation_id
        )
        return
    _log_event(
        presentation,
        kind="status",
        message="Queued for generation",
        stage="pending",
        percent=0,
    )
    asyncio.run(
        _send_progress_async(
            presentation_id,
            {
                "stage": "pending",
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
            playwright_default_timeout=settings.PLAYWRIGHT_DEFAULT_TIMEOUT_MS,
            save_screenshots=settings.PRESENTATIONS_SAVE_SCREENSHOTS,
            site_throttle_delay_ms=settings.PRESENTATIONS_SITE_THROTTLE_DELAY_MS,
        )
        if not hasattr(source, "browser"):
            source.browser = None

        try:
            headless = settings.PRESENTATIONS_HEADLESS
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

            generation_id = presentation.task_id or str(presentation.id)
            async for update in source.generate_presentation(
                topic=presentation.topic,
                language=presentation.language,
                slides_amount=presentation.slides_amount,
                grade=str(presentation.grade),
                subject=presentation.subject,
                author=presentation.author,
                formats_to_download=[DownloadFormat.POWERPOINT, DownloadFormat.TEXT],
                generation_id=generation_id,
            ):
                payload: dict[str, Any] = dict(update)
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
                    stage=str(payload["stage"]) if "stage" in payload else None,
                    percent=int(payload["percent"]) if "percent" in payload else None,
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
            processing_since=None,
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
    # Intentional broad catch: task may fail for any reason (network, Playwright, API).
    except Exception as exc:  # pragma: no cover
        _handle_task_failure(presentation, presentation_id, exc)


@shared_task
def dispatch_pending_presentations() -> None:
    """Outbox relay: dispatch pending presentations and recover stuck ones.

    Runs on a Celery Beat schedule (CELERY_BEAT_SCHEDULE).
    Default interval: 30 minutes (1800 seconds), configurable via PRESENTATIONS_DISPATCH_INTERVAL_S env var.

    Two things happen each tick:
    1. Pending — any presentation with status='pending' is dispatched to Celery.
       The actual task uses an atomic UPDATE WHERE status='pending' to claim work,
       so duplicate dispatches are safe.
    2. Stuck — any presentation with status='processing' whose processing_since
       is older than the generation timeout is reset to 'pending' so it will be
       re-dispatched on the next tick.
    """
    try:
        # --- recover stuck processing tasks ---
        timeout_s = settings.PRESENTATIONS_GENERATION_TIMEOUT_MS / 1000
        stuck_cutoff = timezone.now() - timezone.timedelta(seconds=timeout_s)

        from django.db.models import Count
        status_counts = (
            Presentation.objects.values("status").annotate(n=Count("id"))
        )
        logger.info("Outbox relay DB snapshot: %s", {r["status"]: r["n"] for r in status_counts})
        stuck_ids = list(
            Presentation.objects.filter(
                Q(status="processing", processing_since__lt=stuck_cutoff)
                | Q(status="processing", processing_since__isnull=True)
            ).values_list("id", flat=True)
        )
        if stuck_ids:
            logger.warning(
                "Outbox relay: resetting %d stuck presentation(s) to pending.", len(stuck_ids)
            )
            Presentation.objects.filter(id__in=stuck_ids).update(
                status="pending", processing_since=None
            )

        # --- dispatch all pending tasks ---
        pending_ids = list(
            Presentation.objects.filter(status="pending").values_list("id", flat=True)
        )
        for pres_id in pending_ids:
            generate_presentation_task.delay(str(pres_id))
        if pending_ids:
            logger.info("Outbox relay dispatched %d presentation(s).", len(pending_ids))
    except Exception:
        logger.exception("Outbox relay failed")
