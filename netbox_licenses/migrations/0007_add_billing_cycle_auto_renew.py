# Generated manually for netbox_licenses

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0006_phase3_business_logic_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='billing_cycle',
            field=models.CharField(
                choices=[
                    ('monthly', 'Monthly'),
                    ('quarterly', 'Quarterly'),
                    ('yearly', 'Yearly'),
                    ('one_time', 'One-time Purchase'),
                    ('custom', 'Custom Period')
                ],
                default='monthly',
                help_text='How frequently this license is billed',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='license',
            name='auto_renew',
            field=models.BooleanField(
                default=False,
                help_text='Whether this license automatically renews'
            ),
        ),
    ]