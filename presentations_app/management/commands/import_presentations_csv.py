"""Management command: import presentations from a CSV file, skipping duplicates by task_id."""

from __future__ import annotations

import csv
import sys

from django.core.management.base import BaseCommand, CommandError

from presentations_app.dto import CreatePresentationCommandDto
from presentations_app.models import Presentation
from presentations_app.services import PresentationService


REQUIRED_COLUMNS = {"topic", "language", "grade", "subject"}

_service = PresentationService()


class Command(BaseCommand):
    help = "Import presentations from a CSV file. Rows whose task_id already exists in the DB are skipped."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the CSV file to import")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database",
        )

    def handle(self, *args, **options):  # pylint: disable=too-many-locals
        csv_path = options["csv_file"]
        dry_run = options["dry_run"]

        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except FileNotFoundError as exc:
            raise CommandError(f"File not found: {csv_path}") from exc
        except (UnicodeDecodeError, csv.Error, OSError) as exc:
            raise CommandError(f"Could not read CSV: {exc}") from exc

        if not rows:
            self.stdout.write("CSV is empty, nothing to import.")
            return

        missing = REQUIRED_COLUMNS - rows[0].keys()
        if missing:
            raise CommandError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        # Collect all task_ids from the CSV that are non-empty.
        csv_task_ids = {r["task_id"].strip() for r in rows if r.get("task_id", "").strip()}

        # Single query: find which of those already exist.
        existing_task_ids = set(
            Presentation.objects.filter(task_id__in=csv_task_ids).values_list("task_id", flat=True)
        )

        skipped = 0
        created = 0
        errors = 0

        for line_no, row in enumerate(rows, start=2):  # start=2 because row 1 is the header
            task_id = row.get("task_id", "").strip() or None

            if task_id and task_id in existing_task_ids:
                self.stdout.write(f"  line {line_no}: skipped (task_id={task_id} already in DB)")
                skipped += 1
                continue

            try:
                command = _parse_row(row)
            except ValueError as exc:
                self.stderr.write(f"  line {line_no}: validation error — {exc}")
                errors += 1
                continue

            if dry_run:
                self.stdout.write(f"  line {line_no}: would create task_id={task_id}")
                created += 1
                continue

            _service.create_presentation(command.with_status("pending"))
            created += 1

        label = "Would create" if dry_run else "Created"
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. {label}: {created}, skipped (duplicate): {skipped}, errors: {errors}"
            )
        )
        if errors:
            sys.exit(1)


def _parse_row(row: dict) -> CreatePresentationCommandDto:  # pylint: disable=too-many-branches
    topic = row.get("topic", "").strip()
    if not topic:
        raise ValueError("topic is required")

    language = row.get("language", "").strip()
    if not language:
        raise ValueError("language is required")

    try:
        slides_amount = int(row.get("slides_amount") or 20)
    except (TypeError, ValueError) as exc:
        raise ValueError("slides_amount must be an integer") from exc
    if slides_amount < 0:
        raise ValueError("slides_amount must be non-negative")

    try:
        grade = int(row.get("grade") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("grade must be an integer") from exc
    if grade < 1 or grade > 11:
        raise ValueError("grade must be between 1 and 11")

    subject = row.get("subject", "").strip()
    if not subject:
        raise ValueError("subject is required")

    author = row.get("author", "").strip() or None
    task_id = row.get("task_id", "").strip() or None

    book_id_raw = row.get("book_id", "").strip()
    if book_id_raw:
        try:
            book_id = int(book_id_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("book_id must be an integer") from exc
    else:
        book_id = None

    template_raw = row.get("template", "").strip()
    if template_raw:
        try:
            template = int(template_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("template must be an integer") from exc
    else:
        template = None

    return CreatePresentationCommandDto(
        topic=topic,
        language=language,
        slides_amount=slides_amount,
        grade=grade,
        subject=subject,
        author=author,
        task_id=task_id,
        book_id=book_id,
        template=template,
    )
