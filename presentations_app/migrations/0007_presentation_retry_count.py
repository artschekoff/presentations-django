from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0006_presentationlog_fk_cascade"),
    ]

    operations = [
        migrations.AddField(
            model_name="presentation",
            name="retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
