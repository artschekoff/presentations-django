"""HTTP controllers for presentation endpoints."""

from __future__ import annotations

import json
from typing import Any

import os

from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .dto import CreatePresentationCommandDto
from .models import Presentation
from .services import PresentationService
from .tasks import generate_presentation_task


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

        required_fields = {"topic", "language", "slides_amount", "audience"}
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

        files = payload.get("files", [])
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            return JsonResponse({"detail": "files must be a list of strings"}, status=400)

        status = payload.get("status", "pending")
        if not isinstance(status, str):
            return JsonResponse({"detail": "status must be a string"}, status=400)

        author = payload.get("author")
        if author is not None and not isinstance(author, str):
            return JsonResponse({"detail": "author must be a string if provided"}, status=400)

        command = CreatePresentationCommandDto(
            topic=payload["topic"],
            language=payload["language"],
            slides_amount=slides_amount,
            audience=payload["audience"],
            author=author,
            files=list(files),
            status=status,
        )

        presentation = self.service.create_presentation(command.with_status("queued"))
        generate_presentation_task.delay(str(presentation.id))
        return JsonResponse(
            {
                "id": str(presentation.id),
                "topic": presentation.topic,
                "language": presentation.language,
                "slides_amount": presentation.slides_amount,
                "audience": presentation.audience,
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


class PresentationDownloadView(View):
    """Download the generated PDF presentation."""

    def get(self, request: HttpRequest, presentation_id: str, *args: Any, **kwargs: Any):
        presentation = get_object_or_404(Presentation, id=presentation_id)
        pdf_path = next(
            (path for path in presentation.files if path.lower().endswith(".pdf")),
            None,
        )
        if not pdf_path or not os.path.exists(pdf_path):
            raise Http404("PDF file not found")

        response = FileResponse(open(pdf_path, "rb"), as_attachment=True)
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(pdf_path)}"'
        )
        return response


class PresentationFileDownloadView(View):
    """Download any generated file by index."""

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
        except (IndexError, ValueError, TypeError):
            raise Http404("File not found")
        if not file_path or not os.path.exists(file_path):
            raise Http404("File not found")

        response = FileResponse(open(file_path, "rb"), as_attachment=True)
        response["Content-Disposition"] = (
            f'attachment; filename="{os.path.basename(file_path)}"'
        )
        return response
