from django.db import migrations

NAMES = [
    "Outdoors & Adventure", "Food & Drinks", "Sports & Fitness", "Games & Hangouts", "Arts & Culture",
    "Music & Events", "Study & Learning", "Travel & Road Trips", "Volunteering", "Other",
]


def add_categories(apps, schema_editor):
    from django.utils.text import slugify
    Category = apps.get_model("activities", "Category")
    for name in NAMES:
        Category.objects.get_or_create(slug=slugify(name), defaults={"name": name})


class Migration(migrations.Migration):
    dependencies = [("activities", "0001_initial")]
    operations = [migrations.RunPython(add_categories, migrations.RunPython.noop)]
