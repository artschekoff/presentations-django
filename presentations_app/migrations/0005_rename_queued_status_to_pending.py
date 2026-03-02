"""Data migration: rename status 'queued' -> 'pending' for existing records."""

from django.db import migrations


def rename_queued_to_pending(apps, schema_editor):
    Presentation = apps.get_model("presentations_app", "Presentation")
    Presentation.objects.filter(status="queued").update(status="pending")


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0004_presentation_task_id_book_id_template"),
    ]

    operations = [
        migrations.RunPython(rename_queued_to_pending, migrations.RunPython.noop),
    ]
