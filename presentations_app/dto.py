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
    audience: str
    author: str | None = None
    status: str = "pending"
    files: list[str] = field(default_factory=list)

    def with_status(self, status: str) -> "CreatePresentationCommandDto":
        """Return a copy with an explicit status for volatility handling."""
        return CreatePresentationCommandDto(
            topic=self.topic,
            language=self.language,
            slides_amount=self.slides_amount,
            audience=self.audience,
            author=self.author,
            status=status,
            files=list(self.files),
        )
