from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("presentations_app", "0009_usertoken"),
    ]

    operations = [
        migrations.AlterField(
            model_name="presentation",
            name="task_id",
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True),
        ),
    ]
