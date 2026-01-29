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
            audience=command.audience,
            author=command.author,
            status=command.status,
            files=list(command.files),
        )
