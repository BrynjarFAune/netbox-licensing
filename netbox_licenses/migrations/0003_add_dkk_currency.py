# Migration to add Danish Krone (DKK) to currency choices

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0002_add_currency_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='license',
            name='currency',
            field=models.CharField(choices=[('NOK', 'Norwegian Krone (NOK)'), ('EUR', 'Euro (EUR)'), ('SEK', 'Swedish Krona (SEK)'), ('USD', 'US Dollar (USD)'), ('DKK', 'Danish Krone (DKK)')], default='NOK', help_text='Currency for the license price', max_length=3),
        ),
        migrations.AlterField(
            model_name='licenseinstance',
            name='currency_override',
            field=models.CharField(blank=True, choices=[('NOK', 'Norwegian Krone (NOK)'), ('EUR', 'Euro (EUR)'), ('SEK', 'Swedish Krona (SEK)'), ('USD', 'US Dollar (USD)'), ('DKK', 'Danish Krone (DKK)')], help_text='Override currency for this specific instance', max_length=3, null=True),
        ),
    ]