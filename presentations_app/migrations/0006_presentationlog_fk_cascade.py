"""Fix PresentationLog FK to enforce ON DELETE CASCADE at the database level."""

from django.db import migrations

FK_NAME = "presentations_app_pr_presentation_id_fde0f541_fk_presentat"
TABLE = "presentations_app_presentationlog"
REF_TABLE = "presentations_app_presentation"


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0005_rename_queued_status_to_pending"),
    ]

    operations = [
        migrations.RunSQL(
            sql=f"""
                ALTER TABLE {TABLE}
                DROP CONSTRAINT IF EXISTS "{FK_NAME}";

                ALTER TABLE {TABLE}
                ADD CONSTRAINT "{FK_NAME}"
                FOREIGN KEY (presentation_id)
                REFERENCES {REF_TABLE}(id)
                ON DELETE CASCADE
                DEFERRABLE INITIALLY DEFERRED;
            """,
            reverse_sql=f"""
                ALTER TABLE {TABLE}
                DROP CONSTRAINT IF EXISTS "{FK_NAME}";

                ALTER TABLE {TABLE}
                ADD CONSTRAINT "{FK_NAME}"
                FOREIGN KEY (presentation_id)
                REFERENCES {REF_TABLE}(id)
                DEFERRABLE INITIALLY DEFERRED;
            """,
        ),
    ]
