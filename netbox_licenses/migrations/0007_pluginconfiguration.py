# Generated manually for plugin configuration model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0006_currency_conversion_rates'),
    ]

    operations = [
        migrations.CreateModel(
            name='PluginConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('utilization_excellent_threshold', models.IntegerField(default=90, help_text='Excellent utilization (green badge) - licenses are well utilized')),
                ('utilization_good_threshold', models.IntegerField(default=70, help_text='Good utilization (blue badge) - acceptable usage')),
                ('utilization_moderate_threshold', models.IntegerField(default=50, help_text='Moderate utilization (yellow badge) - approaching underutilization')),
                ('currency_sync_enabled', models.BooleanField(default=True, help_text='Enable automatic currency rate synchronization')),
                ('currency_sync_interval_hours', models.IntegerField(default=24, help_text='Hours between automatic currency rate syncs')),
                ('currency_stale_days', models.IntegerField(default=7, help_text='Days before a currency rate is considered stale')),
                ('renewal_warning_days', models.IntegerField(default=90, help_text='Days before expiry to show renewal warnings')),
                ('renewal_critical_days', models.IntegerField(default=30, help_text='Days before expiry to show critical renewal alerts')),
            ],
            options={
                'verbose_name': 'Plugin Configuration',
                'verbose_name_plural': 'Plugin Configuration',
            },
        ),
    ]
