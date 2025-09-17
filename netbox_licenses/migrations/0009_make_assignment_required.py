# Make assigned_object_id required for license instances

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0008_add_instance_auto_renew'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licenseinstance',
            name='assigned_object_id',
            field=models.PositiveIntegerField(),
        ),
    ]