"""HTTP controllers for presentation endpoints."""

from __future__ import annotations

import json
from typing import Any
from functools import wraps

import os
import mimetypes

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import View
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.db import connection, transaction

from .dto import CreatePresentationCommandDto
from .models import Presentation, UserToken
from .s3 import build_s3_storage
from .services import PresentationService


# Simple API token authentication
API_TOKEN = os.environ.get("PRESENTATION_API_TOKEN", "")


def _require_api_token(view_func):
    """Decorator to verify API token or user token in Authorization header."""
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        # Check Bearer token
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            # Check static API token
            if API_TOKEN and token == API_TOKEN:
                return view_func(request, *args, **kwargs)

            # Check user token
            try:
                user_token = UserToken.objects.get(token=token)
                request.user = user_token.user
                return view_func(request, *args, **kwargs)
            except UserToken.DoesNotExist:
                return JsonResponse({"detail": "Invalid API token"}, status=403)

        return JsonResponse({"detail": "Missing or invalid Authorization header"}, status=401)
    return wrapper


def _s3_presigned_redirect(s3_uri: str) -> HttpResponseRedirect:
    """Generate a presigned S3 URL and redirect to it."""
    storage = build_s3_storage()
    url = storage.s3_presigned_redirect(s3_uri, expires_in=settings.S3_PRESIGN_EXPIRY)
    return HttpResponseRedirect(url)


def _download_headers(file_path: str) -> dict[str, str]:
    filename = os.path.basename(file_path)
    content_type, _ = mimetypes.guess_type(file_path)
    return {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(os.path.getsize(file_path)),
        "Content-Type": content_type or "application/octet-stream",
    }


def _head_download_response(file_path: str) -> HttpResponse:
    response = HttpResponse(status=200)
    for key, value in _download_headers(file_path).items():
        response[key] = value
    return response


def _file_download_response(file_path: str) -> HttpResponse:
    with open(file_path, "rb") as file_stream:
        payload = file_stream.read()
    response = HttpResponse(payload, status=200)
    for key, value in _download_headers(file_path).items():
        response[key] = value
    return response


class PresentationFormView(View):
    """Render the presentation generation form."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        context = {}
        if request.user.is_authenticated:
            try:
                token_obj = UserToken.objects.get(user=request.user)
                context["api_token"] = token_obj.token
            except UserToken.DoesNotExist:
                pass
        return render(request, "presentations_app/presentation_form.html", context)


class LoginView(View):
    """User login view."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any):
        if request.user.is_authenticated:
            return redirect("presentation-form")
        return render(request, "presentations_app/login.html")

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            django_login(request, user)
            # Generate or get token for user
            UserToken.objects.get_or_create(user=user)
            return redirect("presentation-form")
        return render(
            request,
            "presentations_app/login.html",
            {"error": "Invalid username or password"},
            status=401,
        )


class LogoutView(View):
    """User logout view."""

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any):
        django_logout(request)
        return redirect("login")


def _validate_create_payload(  # pylint: disable=too-many-return-statements,too-many-branches
    payload: dict[str, Any],
) -> tuple[CreatePresentationCommandDto | None, JsonResponse | None]:
    """Validate POST payload and return a command DTO or an error response."""
    required_fields = {"topic", "language", "grade", "subject"}
    missing = required_fields - payload.keys()
    if missing:
        return None, JsonResponse(
            {"detail": f"Missing required fields: {', '.join(sorted(missing))}"},
            status=400,
        )

    try:
        slides_amount = int(payload.get("slides_amount", 20))
    except (TypeError, ValueError):
        return None, JsonResponse({"detail": "slides_amount must be an integer"}, status=400)
    if slides_amount < 0:
        return None, JsonResponse({"detail": "slides_amount must be non-negative"}, status=400)

    try:
        grade = int(payload["grade"])
    except (TypeError, ValueError):
        return None, JsonResponse({"detail": "grade must be an integer"}, status=400)
    if grade < 1 or grade > 11:
        return None, JsonResponse({"detail": "grade must be between 1 and 11"}, status=400)

    files = payload.get("files", [])
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        return None, JsonResponse({"detail": "files must be a list of strings"}, status=400)

    status = payload.get("status", "pending")
    if not isinstance(status, str):
        return None, JsonResponse({"detail": "status must be a string"}, status=400)

    author = payload.get("author")
    if author is not None and not isinstance(author, str):
        return None, JsonResponse({"detail": "author must be a string if provided"}, status=400)

    task_id = payload.get("task_id")
    if task_id is not None and not isinstance(task_id, str):
        return None, JsonResponse({"detail": "task_id must be a string if provided"}, status=400)

    book_id = payload.get("book_id")
    if book_id is not None:
        try:
            book_id = int(book_id)
        except (TypeError, ValueError):
            return None, JsonResponse({"detail": "book_id must be an integer if provided"}, status=400)

    template = payload.get("template")
    if template is not None:
        try:
            template = int(template)
        except (TypeError, ValueError):
            return None, JsonResponse({"detail": "template must be an integer if provided"}, status=400)

    return CreatePresentationCommandDto(
        topic=payload["topic"],
        language=payload["language"],
        slides_amount=slides_amount,
        grade=grade,
        subject=payload["subject"],
        author=author,
        task_id=task_id,
        book_id=book_id,
        template=template,
        files=list(files),
        status=status,
    ), None


class PresentationCreateView(View):
    """Controller that creates new presentations."""

    service = PresentationService()

    @method_decorator(_require_api_token)
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

        command, error = _validate_create_payload(payload)
        if error is not None:
            return error
        if command is None:
            return JsonResponse({"detail": "Invalid payload"}, status=400)

        if command.task_id:
            existing = Presentation.objects.filter(task_id=command.task_id).first()
            if existing is not None:
                return JsonResponse(
                    {
                        "id": str(existing.id),
                        "topic": existing.topic,
                        "language": existing.language,
                        "slides_amount": existing.slides_amount,
                        "status": existing.status,
                        "skipped": True,
                    },
                    status=200,
                )

        presentation = self.service.create_presentation(command.with_status("pending"))
        # No explicit dispatch — the outbox relay (Celery Beat) will pick it up.
        return JsonResponse(
            {
                "id": str(presentation.id),
                "topic": presentation.topic,
                "language": presentation.language,
                "slides_amount": presentation.slides_amount,
                "grade": presentation.grade,
                "subject": presentation.subject,
                "author": presentation.author,
                "status": presentation.status,
                "files": presentation.files,
                "download_url": reverse(
                    "presentation-download",
                    kwargs={"presentation_id": presentation.id},
                ),
            },
            status=201,
        )


class PresentationBulkCreateView(View):
    """Create multiple presentations in one request."""

    @method_decorator(_require_api_token)
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

        items = payload.get("items", [])
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            return JsonResponse({"detail": "items must be a list of objects"}, status=400)

        try:
            slides_amount = int(payload.get("slides_amount", 20))
        except (TypeError, ValueError):
            return JsonResponse({"detail": "slides_amount must be an integer"}, status=400)
        if slides_amount < 0:
            return JsonResponse({"detail": "slides_amount must be non-negative"}, status=400)

        commands: list[CreatePresentationCommandDto] = []
        for item in items:
            row_payload = dict(item)
            row_payload["slides_amount"] = slides_amount
            row_payload.setdefault("status", "pending")
            row_payload.setdefault("files", [])

            command, error = _validate_create_payload(row_payload)
            if error is not None or command is None:
                return JsonResponse({"detail": "Invalid row payload"}, status=400)

            commands.append(command.with_status("pending"))

        task_ids = [command.task_id for command in commands if command.task_id]
        existing_by_task_id = {
            presentation.task_id: presentation
            for presentation in Presentation.objects.filter(task_id__in=task_ids)
            if presentation.task_id
        }

        seen_new_task_ids: set[str] = set()
        to_create: list[Presentation] = []
        skipped: list[dict[str, Any]] = []

        for command in commands:
            if command.task_id:
                if command.task_id in existing_by_task_id:
                    existing = existing_by_task_id[command.task_id]
                    skipped.append(
                        {
                            "id": str(existing.id),
                            "task_id": existing.task_id,
                            "topic": existing.topic,
                            "reason": "already_exists",
                        }
                    )
                    continue
                if command.task_id in seen_new_task_ids:
                    skipped.append(
                        {
                            "id": None,
                            "task_id": command.task_id,
                            "topic": command.topic,
                            "reason": "duplicate_in_request",
                        }
                    )
                    continue
                seen_new_task_ids.add(command.task_id)

            to_create.append(
                Presentation(
                    topic=command.topic,
                    language=command.language,
                    slides_amount=command.slides_amount,
                    grade=command.grade,
                    subject=command.subject,
                    author=command.author,
                    task_id=command.task_id,
                    book_id=command.book_id,
                    template=command.template,
                    status=command.status,
                    files=list(command.files),
                )
            )

        created = Presentation.objects.bulk_create(to_create)

        created_payload = [
            {
                "id": str(presentation.id),
                "topic": presentation.topic,
                "language": presentation.language,
                "slides_amount": presentation.slides_amount,
                "status": presentation.status,
                "task_id": presentation.task_id,
            }
            for presentation in created
        ]

        return JsonResponse(
            {
                "created": created_payload,
                "skipped": skipped,
                "created_count": len(created_payload),
                "skipped_count": len(skipped),
            },
            status=201,
        )


class PresentationCheckTaskIdsView(View):
    """Return which of the supplied task_ids already exist in the DB."""

    batch_size = 1000

    def _existing_via_batches(self, unique_task_ids: list[str]) -> set[str]:
        existing_set: set[str] = set()
        for offset in range(0, len(unique_task_ids), self.batch_size):
            batch = unique_task_ids[offset : offset + self.batch_size]
            existing_set.update(
                Presentation.objects.filter(task_id__in=batch).values_list("task_id", flat=True)
            )
        return existing_set

    def _existing_via_temp_table(self, unique_task_ids: list[str]) -> set[str]:
        if not unique_task_ids:
            return set()

        table_name = connection.ops.quote_name(Presentation._meta.db_table)
        existing_set: set[str] = set()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS tmp_task_ids")
                cursor.execute(
                    "CREATE TEMP TABLE tmp_task_ids (task_id text PRIMARY KEY) ON COMMIT DROP"
                )
                for offset in range(0, len(unique_task_ids), self.batch_size):
                    batch = unique_task_ids[offset : offset + self.batch_size]
                    cursor.executemany(
                        "INSERT INTO tmp_task_ids (task_id) VALUES (%s) ON CONFLICT DO NOTHING",
                        [(task_id,) for task_id in batch],
                    )

                cursor.execute(
                    f"""
                    SELECT p.task_id
                    FROM {table_name} p
                    INNER JOIN tmp_task_ids t ON t.task_id = p.task_id
                    WHERE p.task_id IS NOT NULL
                    """
                )
                existing_set = {row[0] for row in cursor.fetchall() if row and row[0] is not None}
        return existing_set

    @method_decorator(_require_api_token)
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

        task_ids = payload.get("task_ids", [])
        if not isinstance(task_ids, list) or not all(isinstance(t, str) for t in task_ids):
            return JsonResponse({"detail": "task_ids must be a list of strings"}, status=400)

        unique_task_ids = list(dict.fromkeys(task_ids))

        if connection.vendor == "postgresql":
            existing_set = self._existing_via_temp_table(unique_task_ids)
        else:
            existing_set = self._existing_via_batches(unique_task_ids)

        existing = [task_id for task_id in unique_task_ids if task_id in existing_set]
        return JsonResponse({"existing": existing})


class PresentationActiveView(View):
    """Return presentations currently pending or processing."""

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        try:
            limit = max(1, min(int(request.GET.get("limit", 50)), 200))
        except (TypeError, ValueError):
            limit = 50

        presentations = Presentation.objects.filter(
            status__in=["pending", "processing", "failed"]
        ).order_by("created_at")[:limit]

        data = []
        for p in presentations:
            file_urls = [
                reverse(
                    "presentation-file-download",
                    kwargs={"presentation_id": p.id, "file_index": i},
                )
                for i in range(len(p.files))
            ]
            data.append(
                {
                    "id": str(p.id),
                    "topic": p.topic,
                    "language": p.language,
                    "slides_amount": p.slides_amount,
                    "grade": p.grade,
                    "subject": p.subject,
                    "author": p.author,
                    "book_id": p.book_id,
                    "template": p.template,
                    "task_id": p.task_id,
                    "status": p.status,
                    "retry_count": p.retry_count,
                    "files": p.files,
                    "file_urls": file_urls,
                }
            )

        return JsonResponse(data, safe=False)


class PresentationRestartView(View):
    """Reset a failed presentation to pending and re-queue it."""

    @method_decorator(_require_api_token)
    def post(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any) -> JsonResponse:
        presentation = get_object_or_404(Presentation, id=presentation_id)
        Presentation.objects.filter(id=presentation_id).update(status="pending", files=[], retry_count=0)
        # No explicit dispatch — the outbox relay (Celery Beat) will pick it up.
        return JsonResponse(
            {
                "id": str(presentation.id),
                "topic": presentation.topic,
                "language": presentation.language,
                "slides_amount": presentation.slides_amount,
                "grade": presentation.grade,
                "subject": presentation.subject,
                "author": presentation.author,
                "status": "pending",
            },
            status=200,
        )


class PresentationDownloadView(View):
    """Download the generated PDF presentation."""

    def head(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any):  # pylint: disable=method-hidden
        presentation = get_object_or_404(Presentation, id=presentation_id)
        pptx_path = next(
            (path for path in presentation.files if path.lower().endswith(".pptx")),
            None,
        )
        if not pptx_path:
            raise Http404("Presentation file not found")
        if pptx_path.startswith("s3://"):
            return HttpResponse(status=200)
        if not os.path.exists(pptx_path):
            raise Http404("Presentation file not found")
        return _head_download_response(pptx_path)

    def get(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        pptx_path = next(
            (path for path in presentation.files if path.lower().endswith(".pptx")),
            None,
        )
        if not pptx_path:
            raise Http404("Presentation file not found")
        if pptx_path.startswith("s3://"):
            return _s3_presigned_redirect(pptx_path)
        if not os.path.exists(pptx_path):
            raise Http404("Presentation file not found")
        return _file_download_response(pptx_path)


class PresentationFileDownloadView(View):
    """Download any generated file by index."""

    def head(  # pylint: disable=method-hidden
        self,
        request: HttpRequest,
        presentation_id: str,
        file_index: int,
        *args: Any,
        **kwargs: Any,
    ):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        try:
            file_path = presentation.files[int(file_index)]
        except (IndexError, ValueError, TypeError) as exc:
            raise Http404("File not found") from exc
        if not file_path:
            raise Http404("File not found")
        if file_path.startswith("s3://"):
            return HttpResponse(status=200)
        if not os.path.exists(file_path):
            raise Http404("File not found")
        return _head_download_response(file_path)

    def get(
        self,
        request: HttpRequest,
        presentation_id: str,
        file_index: int,
        *args: Any,
        **kwargs: Any,
    ):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        try:
            file_path = presentation.files[int(file_index)]
        except (IndexError, ValueError, TypeError) as exc:
            raise Http404("File not found") from exc
        if not file_path:
            raise Http404("File not found")
        if file_path.startswith("s3://"):
            return _s3_presigned_redirect(file_path)
        if not os.path.exists(file_path):
            raise Http404("File not found")
        return _file_download_response(file_path)
