# Generated manually for netbox_licenses

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0007_add_billing_cycle_auto_renew'),
    ]

    operations = [
        migrations.AddField(
            model_name='licenseinstance',
            name='auto_renew',
            field=models.BooleanField(
                blank=True,
                default=None,
                help_text='Override auto-renew setting for this instance (leave blank to use license default)',
                null=True
            ),
        ),
    ]