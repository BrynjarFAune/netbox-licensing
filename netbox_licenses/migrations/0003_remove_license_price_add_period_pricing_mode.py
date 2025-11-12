# Generated migration for pricing refactor

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0002_assignment_types_to_many'),
    ]

    operations = [
        # Add pricing_mode to LicensePeriod
        migrations.AddField(
            model_name='licenseperiod',
            name='pricing_mode',
            field=models.CharField(
                choices=[('total', 'Total License Price'), ('per_seat', 'Price Per Seat')],
                default='per_seat',
                help_text='Whether price is total or per-seat',
                max_length=20
            ),
        ),
        # Remove price and currency from License
        migrations.RemoveField(
            model_name='license',
            name='price',
        ),
        migrations.RemoveField(
            model_name='license',
            name='currency',
        ),
    ]
