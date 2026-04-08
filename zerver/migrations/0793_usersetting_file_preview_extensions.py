from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0792_fix_animated_emoji_still_images"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmuserdefault",
            name="file_preview_extensions",
            field=models.TextField(default=""),
        ),
        migrations.AddField(
            model_name="userprofile",
            name="file_preview_extensions",
            field=models.TextField(default=""),
        ),
    ]
