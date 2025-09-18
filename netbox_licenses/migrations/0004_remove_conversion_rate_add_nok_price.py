# Dummy migration to match database state
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_licenses', '0003_add_dkk_currency'),
    ]
    operations = []
