# Generated migration for payment method and responsibility tracking

from django.db import migrations, models
import django.db.models.deletion


def migrate_auto_renew_to_payment_method(apps, schema_editor):
    """Migrate auto_renew field to payment_method"""
    License = apps.get_model('netbox_licenses', 'License')

    for license in License.objects.all():
        if hasattr(license, 'auto_renew'):
            if license.auto_renew:
                license.payment_method = 'card_auto'
            else:
                license.payment_method = 'invoice'
            license.save()


def reverse_payment_method_to_auto_renew(apps, schema_editor):
    """Reverse migration"""
    License = apps.get_model('netbox_licenses', 'License')

    for license in License.objects.all():
        if hasattr(license, 'payment_method'):
            license.auto_renew = (license.payment_method == 'card_auto')
            license.save()


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0012_contactassignment_custom_fields'),
        ('netbox_licenses', '0004_remove_conversion_rate_add_nok_price'),
    ]

    operations = [
        # Add new fields to License model
        migrations.AddField(
            model_name='license',
            name='payment_method',
            field=models.CharField(
                choices=[
                    ('invoice', 'Invoice (Manual Approval & Payment)'),
                    ('card_auto', 'Credit Card (Auto-Charge)'),
                    ('card_manual', 'Credit Card (Manual Payment)'),
                    ('bank_transfer', 'Bank Transfer'),
                    ('purchase_order', 'Purchase Order'),
                    ('prepaid', 'Prepaid'),
                    ('free_trial', 'Free/Trial')
                ],
                default='invoice',
                help_text='How this license is paid for',
                max_length=30
            ),
        ),
        migrations.AddField(
            model_name='license',
            name='payment_portal_url',
            field=models.URLField(
                blank=True,
                null=True,
                max_length=500,
                help_text='URL to payment portal or subscription management page'
            ),
        ),
        migrations.AddField(
            model_name='license',
            name='responsible_contact',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='responsible_for_licenses',
                to='tenancy.contact',
                help_text='Person responsible for maintaining this license (payments, renewals, compliance)'
            ),
        ),

        # Remove price override fields from LicenseInstance
        migrations.RemoveField(
            model_name='licenseinstance',
            name='price_override',
        ),
        migrations.RemoveField(
            model_name='licenseinstance',
            name='currency_override',
        ),
        migrations.RemoveField(
            model_name='licenseinstance',
            name='nok_price_override',
        ),
        migrations.RemoveField(
            model_name='licenseinstance',
            name='auto_renew',
        ),

        # Run data migration to convert auto_renew to payment_method
        migrations.RunPython(
            migrate_auto_renew_to_payment_method,
            reverse_payment_method_to_auto_renew
        ),

        # Update auto_renew field help text to indicate deprecation
        migrations.AlterField(
            model_name='license',
            name='auto_renew',
            field=models.BooleanField(
                default=False,
                help_text='Automatically renew instances when they expire (deprecated - use payment_method instead)'
            ),
        ),
    ]