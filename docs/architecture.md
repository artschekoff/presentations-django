# Architecture

## Directory layout

```
presentations/          Django project config (settings, urls, celery, asgi, wsgi)
presentations_app/      Main app — models, views, tasks, consumers, services
presentations-module/   Git submodule — SokraticSource (Playwright-based generator)
scripts/                S3 management and batch DB utilities
docker/                 Entry scripts and data volumes
```

## Data flow

1. Client POSTs to `/api/presentations/` → `PresentationCreateView` validates, creates `Presentation` (status=`pending`), enqueues Celery task.
2. Worker picks up the task (`tasks.py`), drives `SokraticSource` via Playwright to generate slides, streams progress over Django Channels WebSocket.
3. `artifact_pipeline.py` finalises artifacts (zip, optional GhostScript PDF compression), uploads to storage, updates `Presentation.files` and `status`.
4. Client downloads via `/presentations/<uuid>/download/` or `/presentations/<uuid>/files/<int>/download/`.

## Key modules

- **`models.py`** — `Presentation` (UUID PK, status: pending → processing → done/failed), `PresentationLog`.
- **`tasks.py`** — Celery shared tasks; `asyncio` + `sync_to_async` runs the async Playwright pipeline inside a thread-pool worker.
- **`artifact_pipeline.py`** — zip packaging, GhostScript PDF compression, storage upload.
- **`storage.py`** — storage abstraction; backend auto-selected from env (see `docs/runtime.md`).
- **`consumers.py`** — Django Channels WebSocket consumer for real-time progress.
- **`views.py`** — API views guarded by `_require_api_token`; web UI (`/`, `/login/`, `/logout/`) uses Django session auth.

## Runtime processes

Production runs three processes: **Daphne** (ASGI — HTTP + WebSocket), **Celery worker** (thread pool, concurrency = `PRESENTATIONS_MAX_TABS`), **Celery beat** (periodic tasks, including hourly Telegram stats).

## presentations-module submodule

`presentations-module/src/presentations_module/` is a separate git repo installed as a package. Exports `SokraticSource` (async generator driving a headless browser session) and `DownloadFormat`. Update with `make refresh-module`.
