# File naming, formats, and task IDs

This document describes how output files are named and which formats are kept.

## Requirements

- Only pptx + text (no PDF in this flow)
- Folder name = `task_id`
- Presentation file name = `task_id`
- Text file name = `task_id`
- 20 slides per presentation by default
- Screenshots must not be saved

## Q&A

| Question | Answer |
| -------- | ------ |
| What if `task_id` is missing? | Use the presentation UUID (`Presentation.id`) |
| How to pin 20 slides? | Default = 20; can be overridden in the request |
| What about screenshot code? | Set env `SAVE_SCREENSHOTS=false` |
| `presentations_module` names files — how to align? | Rename folder and files after generation finishes |

## Acceptance checks

- Folder is named `task_id`, or the presentation UUID if `task_id` is absent
- Files `<task_id>.pptx` and `<task_id>.txt` live inside that folder
- No PDF is produced
- `slides_amount` defaults to 20 (overridable in the request)
- Screenshots are not stored
