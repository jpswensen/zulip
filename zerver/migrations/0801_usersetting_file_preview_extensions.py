from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0800_cleanup_case_mismatched_legacy_apns_tokens"),
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
