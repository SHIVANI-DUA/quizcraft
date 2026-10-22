from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("quizzes", "0001_initial")]
    operations = [
        migrations.AddField(model_name="quiz", name="is_archived", field=models.BooleanField(default=False)),
    ]
