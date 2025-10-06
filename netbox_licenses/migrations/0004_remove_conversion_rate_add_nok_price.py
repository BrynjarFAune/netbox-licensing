# Dummy migration to match database state
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('netbox_licenses', '0001_initial_complete'),
    ]
    operations = []
