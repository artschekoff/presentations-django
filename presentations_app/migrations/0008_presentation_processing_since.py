from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0007_presentation_retry_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="presentation",
            name="processing_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
