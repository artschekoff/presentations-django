"""HTTP controllers for presentation endpoints."""

from __future__ import annotations

import json
from typing import Any

import os
import mimetypes

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .dto import CreatePresentationCommandDto
from .models import Presentation
from .services import PresentationService
from .tasks import generate_presentation_task


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
        return render(request, "presentations_app/presentation_form.html")


class PresentationCreateView(View):
    """Controller that creates new presentations."""

    service = PresentationService()

    @method_decorator(csrf_exempt)
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"detail": "Invalid JSON payload"}, status=400)

        required_fields = {"topic", "language", "slides_amount", "grade", "subject"}
        missing = required_fields - payload.keys()
        if missing:
            return JsonResponse(
                {"detail": f"Missing required fields: {', '.join(sorted(missing))}"},
                status=400,
            )

        slides_amount_value = payload["slides_amount"]
        try:
            slides_amount = int(slides_amount_value)
        except (TypeError, ValueError):
            return JsonResponse({"detail": "slides_amount must be an integer"}, status=400)

        if slides_amount < 0:
            return JsonResponse({"detail": "slides_amount must be non-negative"}, status=400)

        try:
            grade = int(payload["grade"])
        except (TypeError, ValueError):
            return JsonResponse({"detail": "grade must be an integer"}, status=400)

        if grade < 1 or grade > 11:
            return JsonResponse({"detail": "grade must be between 1 and 11"}, status=400)

        files = payload.get("files", [])
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            return JsonResponse({"detail": "files must be a list of strings"}, status=400)

        status = payload.get("status", "pending")
        if not isinstance(status, str):
            return JsonResponse({"detail": "status must be a string"}, status=400)

        author = payload.get("author")
        if author is not None and not isinstance(author, str):
            return JsonResponse({"detail": "author must be a string if provided"}, status=400)

        task_id = payload.get("task_id")
        if task_id is not None and not isinstance(task_id, str):
            return JsonResponse({"detail": "task_id must be a string if provided"}, status=400)

        if task_id:
            existing = Presentation.objects.filter(task_id=task_id).first()
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

        book_id = payload.get("book_id")
        if book_id is not None:
            try:
                book_id = int(book_id)
            except (TypeError, ValueError):
                return JsonResponse({"detail": "book_id must be an integer if provided"}, status=400)

        template = payload.get("template")
        if template is not None:
            try:
                template = int(template)
            except (TypeError, ValueError):
                return JsonResponse({"detail": "template must be an integer if provided"}, status=400)

        command = CreatePresentationCommandDto(
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
        )

        presentation = self.service.create_presentation(command.with_status("pending"))
        generate_presentation_task.delay(str(presentation.id))
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

    @method_decorator(csrf_exempt)
    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> JsonResponse:
        return super().dispatch(request, *args, **kwargs)

    def post(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any) -> JsonResponse:
        presentation = get_object_or_404(Presentation, id=presentation_id)
        Presentation.objects.filter(id=presentation_id).update(status="pending", files=[], retry_count=0)
        generate_presentation_task.delay(str(presentation.id))
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

    def head(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        pdf_path = next(
            (path for path in presentation.files if path.lower().endswith(".pdf")),
            None,
        )
        if not pdf_path or not os.path.exists(pdf_path):
            raise Http404("PDF file not found")
        return _head_download_response(pdf_path)

    def get(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        pdf_path = next(
            (path for path in presentation.files if path.lower().endswith(".pdf")),
            None,
        )
        if not pdf_path or not os.path.exists(pdf_path):
            raise Http404("PDF file not found")
        return _file_download_response(pdf_path)


class PresentationFileDownloadView(View):
    """Download any generated file by index."""

    def head(
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
        if not file_path or not os.path.exists(file_path):
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
        if not file_path or not os.path.exists(file_path):
            raise Http404("File not found")
        return _file_download_response(file_path)
