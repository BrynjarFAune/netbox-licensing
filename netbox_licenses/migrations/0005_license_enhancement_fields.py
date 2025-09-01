# Migration to add license utilization tracking enhancements

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0004_remove_conversion_rate_add_nok_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='external_id',
            field=models.CharField(blank=True, max_length=255, null=True,
                                 help_text='Vendor-specific identifier (SKU ID, subscription ID, license key, etc.)'),
        ),
        migrations.AddField(
            model_name='license',
            name='total_licenses',
            field=models.PositiveIntegerField(default=1,
                                            help_text='Total available license slots purchased'),
        ),
        migrations.AddField(
            model_name='license',
            name='consumed_licenses',
            field=models.PositiveIntegerField(default=0,
                                            help_text='Currently assigned/consumed licenses'),
        ),
        migrations.AddField(
            model_name='license',
            name='metadata',
            field=models.JSONField(blank=True, default=dict,
                                 help_text='Vendor-specific data (service plans, features, API limits, etc.)'),
        ),
        migrations.AddIndex(
            model_name='license',
            index=models.Index(fields=['external_id'], name='netbox_licenses_license_external_id_idx'),
        ),
        migrations.AddIndex(
            model_name='license',
            index=models.Index(fields=['vendor', 'external_id'], name='netbox_licenses_license_vendor_external_idx'),
        ),
        migrations.AddIndex(
            model_name='license',
            index=models.Index(fields=['consumed_licenses', 'total_licenses'], name='netbox_licenses_license_utilization_idx'),
        ),
    ]