from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0002_presentationlog"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="presentation",
            name="audience",
        ),
        migrations.AddField(
            model_name="presentation",
            name="grade",
            field=models.PositiveSmallIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="presentation",
            name="subject",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
    ]
