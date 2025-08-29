# Generated migration for currency support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='currency',
            field=models.CharField(choices=[('NOK', 'Norwegian Krone (NOK)'), ('EUR', 'Euro (EUR)'), ('SEK', 'Swedish Krona (SEK)'), ('USD', 'US Dollar (USD)')], default='NOK', help_text='Currency for the license price', max_length=3),
        ),
        migrations.AddField(
            model_name='licenseinstance',
            name='currency_override',
            field=models.CharField(blank=True, choices=[('NOK', 'Norwegian Krone (NOK)'), ('EUR', 'Euro (EUR)'), ('SEK', 'Swedish Krona (SEK)'), ('USD', 'US Dollar (USD)')], help_text='Override currency for this specific instance', max_length=3, null=True),
        ),
        migrations.AddField(
            model_name='licenseinstance',
            name='conversion_rate_to_nok',
            field=models.DecimalField(blank=True, decimal_places=6, help_text='Conversion rate from instance currency to NOK (multiplier)', max_digits=10, null=True),
        ),
    ]