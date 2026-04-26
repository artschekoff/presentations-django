# Upload form change

The upload flow now supports bulk task import from a `.csv` file.

## Requirements

1. The first screen is a choice between two modes: manual and CSV import.
2. Manual mode uses the same task-creation form as before (plus a “new task” button).
3. CSV import is a file upload with the following columns:
  `|task_id (string)|book_id (number)|topic_title (string)|class (number)|subject (string)|lang (string)|template (number|none)|`
  The first row is headers, then one row per task.
4. There are two actions: “Verify” and “Add to queue”.
5. “Add to queue” is enabled only after “Verify” and no validation errors.
6. On “Verify”, the full CSV is read; each row is validated to match the `presentation` type. Invalid rows are listed with row number and error message.
7. On “Add to queue”, each row becomes a `presentation` task, same as “Start generation” in manual mode.
8. Task results must be persisted in the database.

## Clarifications

### CSV fields not on the `Presentation` model

`task_id`, `book_id`, and `template` are added as nullable columns:

- `task_id` — `CharField`, nullable
- `book_id` — `IntegerField`, nullable
- `template` — `IntegerField`, nullable

A new migration is required.

### `author` field

Not present in the CSV. For CSV-imported tasks, `author` is always `null`.

### `slides_amount`

Not in the CSV. It is set on the import form (selector, e.g. 10, 20, 30) and applied to all rows.

### `book_id` and `template`

Stored as metadata. Not passed to `generate_presentation_task`.

### `task_id` uniqueness

Only checked within the uploaded file. Duplicates in the same file are a validation error with row reference. No DB uniqueness check at verify time.

### CSV format

Semicolon (`;`) delimiter. UTF-8 encoding.

### Valid `lang` values

The `lang` cell may be `Kazakh`, `Russian`, or the legacy Cyrillic spellings for the same two languages; all map to `kz` and `ru` in the database.

### Mode selection UX

The start screen has two large buttons: “Manual” and “CSV import”. The chosen mode shows the corresponding form.

### After “Add to queue”

The import form stays above the task list. Tasks with progress appear below, as in manual mode.

## Acceptance criteria

1. The user can pick manual or CSV import.
2. Manual mode behaves as before.
3. Import loads and validates the file and can enqueue tasks correctly.
4. Validation errors are clear to the user.
5. Tasks are written to the database correctly before execution.
6. Task results (presentation file paths) are stored and shown to the user.
