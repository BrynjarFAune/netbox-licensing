"""
Management command to sync currency rates from Norges Bank API
Can be run manually or via cron/systemd timer
"""
from django.core.management.base import BaseCommand
from netbox_licenses.models import CurrencyConversionRate, PluginConfiguration
from netbox_licenses.services.currency_service import sync_currency_rate


class Command(BaseCommand):
    help = 'Synchronize API-sourced currency exchange rates from Norges Bank'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force sync even if disabled in configuration',
        )

    def handle(self, *args, **options):
        # Check if sync is enabled in configuration
        try:
            config = PluginConfiguration.get_config()
            if not config.currency_sync_enabled and not options['force']:
                self.stdout.write(
                    self.style.WARNING('Currency sync is disabled in plugin configuration. Use --force to override.')
                )
                return
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Could not load plugin configuration: {e}. Proceeding with sync.')
            )

        # Get all API-sourced currencies
        api_currencies = CurrencyConversionRate.objects.filter(source='api')

        if not api_currencies.exists():
            self.stdout.write(
                self.style.WARNING('No API-sourced currencies found to sync')
            )
            return

        success_count = 0
        failed_count = 0
        failed_currencies = []

        self.stdout.write(f'Starting sync for {api_currencies.count()} currency rate(s)...')

        for currency in api_currencies:
            try:
                old_rate = currency.rate_to_nok
                sync_currency_rate(currency)

                # Log if rate changed
                if old_rate != currency.rate_to_nok:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✓ Updated {currency.currency_code}: {old_rate} → {currency.rate_to_nok} NOK'
                        )
                    )
                else:
                    self.stdout.write(
                        f'  No change for {currency.currency_code}: {currency.rate_to_nok} NOK'
                    )

                success_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to sync {currency.currency_code}: {str(e)}')
                )
                failed_count += 1
                failed_currencies.append(currency.currency_code)

        # Final summary
        self.stdout.write('')
        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully synced {success_count} currency rate(s)')
            )

        if failed_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'Failed to sync {failed_count} currency rate(s): {", ".join(failed_currencies)}'
                )
            )
