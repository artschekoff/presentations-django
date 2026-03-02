"""Service layer encapsulating presentation business rules."""

from __future__ import annotations

from .dto import CreatePresentationCommandDto
from .models import Presentation


class PresentationService:
    """Operations for creating and managing presentations."""

    def create_presentation(
        self, command: CreatePresentationCommandDto
    ) -> Presentation:
        """Create a Presentation record from the provided command DTO."""

        return Presentation.objects.create(
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
