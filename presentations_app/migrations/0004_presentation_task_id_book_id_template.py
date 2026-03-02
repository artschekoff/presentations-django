from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0003_presentation_grade_subject"),
    ]

    operations = [
        migrations.AddField(
            model_name="presentation",
            name="task_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="presentation",
            name="book_id",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="presentation",
            name="template",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
