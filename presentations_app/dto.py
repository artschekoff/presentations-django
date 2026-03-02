"""Data transfer objects shared by presentation services."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CreatePresentationCommandDto:
    """
    Simplified command object inspired by the `PresentationDocument` from
    `presentations-module`. The fields mirror the shared dataclass.
    """

    topic: str
    language: str
    slides_amount: int
    grade: int
    subject: str
    author: str | None = None
    task_id: str | None = None
    book_id: int | None = None
    template: int | None = None
    status: str = "pending"
    files: list[str] = field(default_factory=list)

    def with_status(self, status: str) -> "CreatePresentationCommandDto":
        """Return a copy with an explicit status for volatility handling."""
        return CreatePresentationCommandDto(
            topic=self.topic,
            language=self.language,
            slides_amount=self.slides_amount,
            grade=self.grade,
            subject=self.subject,
            author=self.author,
            task_id=self.task_id,
            book_id=self.book_id,
            template=self.template,
            status=status,
            files=list(self.files),
        )
