"""Celery tasks for generating presentations."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterable

from asgiref.sync import sync_to_async
from celery import shared_task
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from django.urls import reverse
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
)
from playwright._impl._errors import TargetClosedError

from presentations_module import SokraticSource, DownloadFormat

from .models import Presentation, PresentationLog
from .s3 import build_s3_storage_if_configured

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared browser pool
# ---------------------------------------------------------------------------

class _BrowserPool:
    """Single Playwright browser shared across all Celery tasks.

    Runs in a background daemon thread with its own persistent event loop.
    An asyncio.Semaphore limits the number of concurrent browser contexts
    (= tabs) to PRESENTATIONS_MAX_TABS.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._active_tabs = 0
        self._active_tabs_lock: asyncio.Lock | None = None
        self._auth_lock: asyncio.Lock | None = None
        self._is_authenticated = False
        self._auth_failed_until: float = 0.0
        self._init_error: Exception | None = None
        self._ready = threading.Event()

    # --- internal ---

    def _loop_thread(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._init())
        except Exception as exc:  # pragma: no cover
            self._init_error = exc
            logger.exception("BrowserPool: failed to initialize: %s", exc)
        finally:
            self._ready.set()
        if self._init_error is not None:
            return
        self._loop.run_forever()

    async def _init(self) -> None:
        from django.conf import settings as _s
        self._playwright = await async_playwright().start()
        max_tabs = _s.PRESENTATIONS_MAX_TABS
        self._semaphore = asyncio.Semaphore(max_tabs)
        self._active_tabs_lock = asyncio.Lock()
        self._auth_lock = asyncio.Lock()
        self._restart_lock = asyncio.Lock()
        await self._launch_browser()

    async def _launch_browser(self) -> None:
        from django.conf import settings as _s
        headless = _s.PRESENTATIONS_HEADLESS
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._context = await self._browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 720},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        self._is_authenticated = False
        self._auth_failed_until = 0.0
        logger.info(
            "BrowserPool: started (headless=%s, max_tabs=%d, worker_pid=%d, browser_id=%s)",
            headless,
            _s.PRESENTATIONS_MAX_TABS,
            os.getpid(),
            hex(id(self._browser)),
        )

    async def _reinit_browser(self) -> None:
        """Tear down dead browser and launch a fresh one."""
        async with self._restart_lock:
            if self._browser and self._browser.is_connected():
                return
            logger.warning(
                "BrowserPool: browser died, restarting (worker_pid=%d)",
                os.getpid(),
            )
            try:
                if self._context:
                    await self._context.close()
            except Exception:
                pass
            try:
                if self._browser:
                    await self._browser.close()
            except Exception:
                pass
            await self._launch_browser()
            logger.info(
                "BrowserPool: browser restarted (worker_pid=%d, browser_id=%s)",
                os.getpid(),
                hex(id(self._browser)),
            )

    # --- public ---

    def _ensure_running(self) -> None:
        need_wait = False
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                if self._ready.is_set():
                    if self._init_error is not None:
                        raise RuntimeError(
                            f"BrowserPool: init failed: {self._init_error}"
                        ) from self._init_error
                    return
                need_wait = True
            else:
                self._ready.clear()
                self._init_error = None
                self._thread = threading.Thread(
                    target=self._loop_thread, daemon=True, name="browser-pool"
                )
                self._thread.start()
                need_wait = True
        if need_wait and not self._ready.wait(timeout=60):
            raise RuntimeError("BrowserPool: browser did not start in time")
        if self._init_error is not None:
            raise RuntimeError(
                f"BrowserPool: init failed: {self._init_error}"
            ) from self._init_error

    def restart_browser(self) -> None:
        """Synchronously restart the browser from a Celery worker thread."""
        self._ensure_running()
        future = asyncio.run_coroutine_threadsafe(
            self._reinit_browser(), self.loop
        )
        future.result(timeout=60)

    @property
    def playwright(self) -> Playwright:
        self._ensure_running()
        assert self._playwright is not None
        return self._playwright

    @property
    def browser(self) -> Browser:
        self._ensure_running()
        assert self._browser is not None
        return self._browser

    @property
    def semaphore(self) -> asyncio.Semaphore:
        self._ensure_running()
        if self._semaphore is None:
            raise RuntimeError("BrowserPool: semaphore is not initialized")
        return self._semaphore

    @property
    def context(self) -> BrowserContext:
        self._ensure_running()
        if self._context is None:
            raise RuntimeError("BrowserPool: context is not initialized")
        return self._context

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        self._ensure_running()
        assert self._loop is not None
        return self._loop

    @property
    def active_tabs(self) -> int:
        self._ensure_running()
        return self._active_tabs

    @property
    def local_active_tabs(self) -> int:
        """Active tab count without triggering pool initialization."""
        with self._lock:
            if (
                self._thread is not None
                and self._thread.is_alive()
                and self._ready.is_set()
                and self._init_error is None
            ):
                return self._active_tabs
        return 0

    @asynccontextmanager
    async def tab_slot(self, task_id: str) -> AsyncIterator[None]:
        self._ensure_running()
        semaphore = self.semaphore
        await semaphore.acquire()
        assert self._active_tabs_lock is not None
        async with self._active_tabs_lock:
            self._active_tabs += 1
            active_now = self._active_tabs
        logger.info(
            "Browser tab acquired: task_id=%s active_tabs=%d/%d worker_pid=%d browser_id=%s",
            task_id,
            active_now,
            settings.PRESENTATIONS_MAX_TABS,
            os.getpid(),
            hex(id(self.browser)),
        )
        try:
            yield
        finally:
            async with self._active_tabs_lock:
                self._active_tabs -= 1
                active_now = self._active_tabs
            semaphore.release()
            logger.info(
                "Browser tab released: task_id=%s active_tabs=%d/%d worker_pid=%d browser_id=%s",
                task_id,
                active_now,
                settings.PRESENTATIONS_MAX_TABS,
                os.getpid(),
                hex(id(self.browser)),
            )

    def run(self, coro: Any) -> Any:
        """Submit *coro* to the shared event loop and block until it completes."""
        self._ensure_running()
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    async def open_tab(self) -> Page:
        self._ensure_running()
        return await self.context.new_page()

    _AUTH_COOLDOWN_S = 30

    async def ensure_authenticated(
        self,
        *,
        generation_id: str,
        logger_obj: logging.Logger,
        storage: Any,
    ) -> None:
        import time

        self._ensure_running()
        if self._is_authenticated:
            return
        if self._auth_lock is None:
            raise RuntimeError("BrowserPool: auth lock is not initialized")

        now = time.monotonic()
        if now < self._auth_failed_until:
            raise RuntimeError(
                f"BrowserPool: auth on cooldown, retry in {self._auth_failed_until - now:.0f}s"
            )

        async with self._auth_lock:
            if self._is_authenticated:
                return
            now = time.monotonic()
            if now < self._auth_failed_until:
                raise RuntimeError(
                    f"BrowserPool: auth on cooldown, retry in {self._auth_failed_until - now:.0f}s"
                )

            login = os.environ.get("SOKRATIC_USERNAME")
            password = os.environ.get("SOKRATIC_PASSWORD")
            if not login or not password:
                raise RuntimeError("SOKRATIC_USERNAME/SOKRATIC_PASSWORD are not set")

            logger.info(
                "BrowserPool: opening auth tab (worker_pid=%d, browser_id=%s)",
                os.getpid(),
                hex(id(self.browser)),
            )
            auth_source = SokraticSource(
                self.playwright,
                logger=logger_obj,
                generation_dir=settings.PRESENTATIONS_DIR,
                generation_timeout=settings.PRESENTATIONS_GENERATION_TIMEOUT_MS,
                playwright_default_timeout=settings.PLAYWRIGHT_DEFAULT_TIMEOUT_MS,
                save_screenshots=settings.PRESENTATIONS_SAVE_SCREENSHOTS,
                save_logs=settings.PRESENTATIONS_SAVE_LOGS,
                site_throttle_delay_ms=settings.PRESENTATIONS_SITE_THROTTLE_DELAY_MS,
                storage=storage,
            )
            auth_source.browser = self.browser
            auth_source.context = self.context
            auth_source.is_init = True
            auth_source.page = await self.open_tab()
            if auth_source.playwright_default_timeout is not None:
                auth_source.page.set_default_timeout(auth_source.playwright_default_timeout)

            try:
                await auth_source.authenticate(
                    login=login,
                    password=password,
                    generation_id=f"auth-{generation_id}",
                )
                self._is_authenticated = True
                self._auth_failed_until = 0.0
                logger.info(
                    "BrowserPool: shared authentication completed (worker_pid=%d, browser_id=%s)",
                    os.getpid(),
                    hex(id(self.browser)),
                )
            except Exception:
                self._auth_failed_until = time.monotonic() + self._AUTH_COOLDOWN_S
                logger.warning(
                    "BrowserPool: auth failed, cooldown %ds (worker_pid=%d)",
                    self._AUTH_COOLDOWN_S,
                    os.getpid(),
                )
                raise
            finally:
                if auth_source.page is not None:
                    try:
                        await auth_source.page.close()
                    except Exception:
                        logger.debug("BrowserPool: auth tab already closed")
                auth_source.page = None
                auth_source.context = None
                auth_source.browser = None


_browser_pool = _BrowserPool()


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


def _reconnect_and(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Close stale DB connections before calling *func*.

    Required when ORM calls originate from async contexts (e.g. sync_to_async
    inside the browser-pool event loop). PostgreSQL may silently drop idle
    connections; calling close_old_connections() forces Django to open a fresh
    one rather than reusing a dead socket.
    """
    close_old_connections()
    return func(*args, **kwargs)


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
    logger.exception("Generate task failed: task_id=%s: %s", presentation.task_id, exc)
    Presentation.objects.filter(id=presentation_id).update(retry_count=F("retry_count") + 1)
    retry_count = Presentation.objects.get(id=presentation_id).retry_count
    max_retries = 3

    if retry_count < max_retries:
        logger.info("Retrying task_id=%s (attempt %d/%d)", presentation.task_id, retry_count, max_retries)
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
        logger.error("task_id=%s failed after %d attempts", presentation.task_id, retry_count)
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

    try:
        presentation = Presentation.objects.get(id=presentation_id)
    except Presentation.DoesNotExist:
        logger.error("Presentation id=%s does not exist", presentation_id)
        return
    task_id = presentation.task_id or str(presentation_id)
    logger.info("Generate task started: task_id=%s", task_id)

    # Atomically claim the task: accept "queued" (normal path via relay)
    # or "pending" (backward compat / manual dispatch).
    claimed = Presentation.objects.filter(
        id=presentation_id, status__in=["queued", "pending"]
    ).update(status="processing", processing_since=timezone.now())
    if not claimed:
        logger.info(
            "task_id=%s already claimed or finished, skipping.", task_id
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
        generation_id = presentation.task_id or str(presentation.id)
        generation_dir = settings.PRESENTATIONS_DIR
        storage = build_s3_storage_if_configured()

        await _browser_pool.ensure_authenticated(
            generation_id=generation_id,
            logger_obj=sokratic_logger,
            storage=storage,
        )

        logger.info("Waiting for browser tab: task_id=%s", generation_id)
        async with _browser_pool.tab_slot(generation_id):
            source = SokraticSource(
                _browser_pool.playwright,
                logger=sokratic_logger,
                generation_dir=generation_dir,
                generation_timeout=settings.PRESENTATIONS_GENERATION_TIMEOUT_MS,
                playwright_default_timeout=settings.PLAYWRIGHT_DEFAULT_TIMEOUT_MS,
                save_screenshots=settings.PRESENTATIONS_SAVE_SCREENSHOTS,
                save_logs=settings.PRESENTATIONS_SAVE_LOGS,
                site_throttle_delay_ms=settings.PRESENTATIONS_SITE_THROTTLE_DELAY_MS,
                storage=storage,
            )
            # Inject the shared browser so init_async is skipped.
            # We create a fresh page (= tab) in one shared context per task.
            source.browser = _browser_pool.browser
            source.is_init = True
            source.context = _browser_pool.context
            source.page = None

            try:
                async for update in source.generate_presentation(
                    generation_id=generation_id,
                    topic=presentation.topic,
                    language=presentation.language,
                    slides_amount=presentation.slides_amount,
                    grade=str(presentation.grade),
                    subject=presentation.subject,
                    author=presentation.author,
                    style_id=str(presentation.template) if presentation.template is not None else None,
                    formats_to_download=[
                        DownloadFormat.POWERPOINT,
                        DownloadFormat.PDF,
                        DownloadFormat.TEXT,
                    ],
                ):
                    payload: dict[str, Any] = dict(update)
                    payload["presentation_id"] = presentation_id
                    if payload.get("files"):
                        files_now = _safe_files(payload.get("files"))
                        await sync_to_async(_reconnect_and)(
                            Presentation.objects.filter(id=presentation_id).update,
                            files=files_now,
                        )
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
                    await sync_to_async(_reconnect_and)(
                        _log_event,
                        presentation,
                        kind="progress",
                        payload=payload,
                        stage=str(payload["stage"]) if "stage" in payload else None,
                        percent=int(payload["percent"]) if "percent" in payload else None,
                    )
                    if payload.get("stage"):
                        logger.info(
                            "Progress task_id=%s: stage=%s percent=%s",
                            generation_id,
                            payload.get("stage"),
                            payload.get("percent"),
                        )

                    if update.get("stage") == "done":
                        files = _safe_files(update.get("files"))
            finally:
                logger.info("Disposing context: task_id=%s", generation_id)
                # Prevent dispose_async from closing shared browser/context.
                source.browser = None
                source.page = None
                source.context = None
                await source.dispose_async()
                logger.info("Context disposed: task_id=%s", generation_id)

        return files

    try:
        files = _browser_pool.run(_run())
        logger.info(
            "Generate task completed: task_id=%s (files=%d)",
            task_id,
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
    except TargetClosedError as exc:
        logger.warning(
            "Browser context died during task_id=%s, restarting browser pool",
            task_id,
        )
        try:
            _browser_pool.restart_browser()
        except Exception:
            logger.exception("Failed to restart browser pool")
        _handle_task_failure(presentation, presentation_id, exc)
        dispatch_pending_presentations.apply_async(countdown=2)
    # Intentional broad catch: task may fail for any reason (network, Playwright, API).
    except Exception as exc:  # pragma: no cover
        _handle_task_failure(presentation, presentation_id, exc)
        dispatch_pending_presentations.apply_async(countdown=2)


@shared_task
def dispatch_pending_presentations() -> None:
    """Outbox relay: reset stuck presentations and dispatch pending ones.

    Runs every minute (configurable via PRESENTATIONS_DISPATCH_INTERVAL_S).
    Uses atomic UPDATE WHERE status='pending' to claim work, so duplicate
    dispatches are safe.
    """
    try:
        status_counts = Presentation.objects.values("status").annotate(n=Count("id"))
        logger.info("Outbox relay DB snapshot: %s", {r["status"]: r["n"] for r in status_counts})

        # --- recover stuck processing tasks (lease > 30 min) ---
        stuck_cutoff = timezone.now() - timezone.timedelta(seconds=settings.PRESENTATIONS_LEASE_TIMEOUT_S)
        stuck_ids = list(
            Presentation.objects.filter(
                Q(status="processing", processing_since__lt=stuck_cutoff)
                | Q(status="processing", processing_since__isnull=True)
            ).values_list("id", flat=True)
        )
        if stuck_ids:
            logger.warning("Outbox relay: resetting %d stuck processing presentation(s) to pending.", len(stuck_ids))
            Presentation.objects.filter(id__in=stuck_ids).update(
                status="pending", processing_since=None
            )

        # --- recover stuck queued tasks (dispatched but never claimed) ---
        queued_cutoff = timezone.now() - timezone.timedelta(minutes=5)
        stuck_queued = Presentation.objects.filter(
            status="queued", processing_since__lt=queued_cutoff
        ).update(status="pending", processing_since=None)
        if stuck_queued:
            logger.warning("Outbox relay: reset %d stuck queued presentation(s) to pending.", stuck_queued)

        # --- dispatch pending tasks based on LOCAL worker capacity ---
        # Each worker independently manages its own tab budget via the
        # in-process _browser_pool, so multiple workers sharing the same
        # DB no longer starve each other.
        local_active = _browser_pool.local_active_tabs
        available_slots = max(settings.PRESENTATIONS_MAX_TABS - local_active, 0)

        if available_slots <= 0:
            logger.info(
                "Outbox relay: no free slots (local_active=%d, max_tabs=%d).",
                local_active,
                settings.PRESENTATIONS_MAX_TABS,
            )
            return

        # Atomically select and mark as "queued" using row-level locking.
        # SKIP LOCKED ensures concurrent relays (e.g. production + slave)
        # pick different presentations without duplicates.
        with transaction.atomic():
            pending_ids = list(
                Presentation.objects
                .select_for_update(skip_locked=True)
                .filter(status="pending")
                .order_by("created_at")
                .values_list("id", flat=True)[:available_slots]
            )
            if pending_ids:
                Presentation.objects.filter(id__in=pending_ids).update(
                    status="queued", processing_since=timezone.now()
                )

        for pres_id in pending_ids:
            generate_presentation_task.delay(str(pres_id))
        if pending_ids:
            logger.info(
                "Outbox relay dispatched %d presentation(s) (local_active=%d, max_tabs=%d).",
                len(pending_ids),
                local_active,
                settings.PRESENTATIONS_MAX_TABS,
            )
    except Exception:
        logger.exception("Outbox relay failed")
