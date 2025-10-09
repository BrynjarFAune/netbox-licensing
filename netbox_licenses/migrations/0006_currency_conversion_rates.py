# Generated migration for CurrencyConversionRate model
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0005_payment_method_and_responsibility'),
    ]

    operations = [
        migrations.CreateModel(
            name='CurrencyConversionRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, editable=False)),
                ('from_currency', models.CharField(
                    choices=[
                        ('NOK', 'Norwegian Krone (NOK)'),
                        ('USD', 'US Dollar (USD)'),
                        ('EUR', 'Euro (EUR)'),
                        ('GBP', 'British Pound (GBP)'),
                        ('JPY', 'Japanese Yen (JPY)'),
                        ('AUD', 'Australian Dollar (AUD)'),
                        ('CAD', 'Canadian Dollar (CAD)'),
                        ('CHF', 'Swiss Franc (CHF)'),
                        ('SEK', 'Swedish Krona (SEK)'),
                        ('DKK', 'Danish Krone (DKK)')
                    ],
                    help_text='Source currency code',
                    max_length=3
                )),
                ('to_currency', models.CharField(
                    choices=[
                        ('NOK', 'Norwegian Krone (NOK)'),
                        ('USD', 'US Dollar (USD)'),
                        ('EUR', 'Euro (EUR)'),
                        ('GBP', 'British Pound (GBP)'),
                        ('JPY', 'Japanese Yen (JPY)'),
                        ('AUD', 'Australian Dollar (AUD)'),
                        ('CAD', 'Canadian Dollar (CAD)'),
                        ('CHF', 'Swiss Franc (CHF)'),
                        ('SEK', 'Swedish Krona (SEK)'),
                        ('DKK', 'Danish Krone (DKK)')
                    ],
                    default='NOK',
                    help_text='Target currency code',
                    max_length=3
                )),
                ('rate', models.DecimalField(
                    decimal_places=6,
                    help_text='Conversion rate (1 from_currency = X to_currency)',
                    max_digits=12
                )),
                ('source', models.CharField(
                    choices=[('api', 'API (Norges Bank)'), ('manual', 'Manual Override')],
                    default='api',
                    help_text='Source of this rate (API or manual override)',
                    max_length=20
                )),
                ('effective_date', models.DateField(help_text='Date this rate became effective')),
                ('notes', models.TextField(blank=True, help_text='Additional notes about this rate')),
            ],
            options={
                'ordering': ['-effective_date', 'from_currency'],
            },
        ),
        migrations.AddIndex(
            model_name='currencyconversionrate',
            index=models.Index(fields=['from_currency', 'to_currency', '-effective_date'], name='netbox_lice_from_cu_7a8c8f_idx'),
        ),
        migrations.AddIndex(
            model_name='currencyconversionrate',
            index=models.Index(fields=['source', '-effective_date'], name='netbox_lice_source_fd8b29_idx'),
        ),
    ]
