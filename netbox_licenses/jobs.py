"""
Background jobs for NetBox Licenses plugin
"""
from datetime import timedelta
from django.utils import timezone
from netbox.jobs import Job
from .models import CurrencyConversionRate, PluginConfiguration
from .services.currency_service import sync_currency_rate


class SyncCurrencyRatesJob(Job):
    """
    Background job to sync all API-sourced currency rates from Norges Bank.
    Runs on a configurable schedule to keep exchange rates current.
    Schedule and enabled status are controlled by plugin configuration.
    """

    class Meta:
        name = "Sync Currency Rates"
        description = "Synchronize API-sourced currency exchange rates from Norges Bank"
        scheduling_enabled = True
        interval = 86400  # Default 24 hours, overridden by config

    def run(self, *args, **kwargs):
        """Execute the currency sync job"""

        # Check if sync is enabled in configuration
        try:
            config = PluginConfiguration.get_config()
            if not config.currency_sync_enabled:
                self.log_info("Currency sync is disabled in plugin configuration")
                return
        except Exception as e:
            self.log_warning(f"Could not load plugin configuration: {e}. Proceeding with sync.")

        # Get all API-sourced currencies
        api_currencies = CurrencyConversionRate.objects.filter(source='api')

        if not api_currencies.exists():
            self.log_info("No API-sourced currencies found to sync")
            return

        success_count = 0
        failed_count = 0
        failed_currencies = []

        self.log_info(f"Starting sync for {api_currencies.count()} currency rate(s)")

        for currency in api_currencies:
            try:
                old_rate = currency.rate_to_nok
                sync_currency_rate(currency)

                # Log if rate changed
                if old_rate != currency.rate_to_nok:
                    self.log_success(
                        f"Updated {currency.currency_code}: {old_rate} → {currency.rate_to_nok} NOK"
                    )
                else:
                    self.log_info(f"No change for {currency.currency_code}: {currency.rate_to_nok} NOK")

                success_count += 1

            except Exception as e:
                self.log_failure(f"Failed to sync {currency.currency_code}: {str(e)}")
                failed_count += 1
                failed_currencies.append(currency.currency_code)

        # Final summary
        if success_count > 0:
            self.log_success(f"Successfully synced {success_count} currency rate(s)")

        if failed_count > 0:
            self.log_warning(
                f"Failed to sync {failed_count} currency rate(s): {', '.join(failed_currencies)}"
            )


class CleanupStaleCurrencyRatesJob(Job):
    """
    Background job to identify and report stale currency rates.
    Stale threshold is configurable in plugin settings.
    """

    class Meta:
        name = "Check for Stale Currency Rates"
        description = "Identify currency rates that haven't been updated recently"
        scheduling_enabled = True
        interval = 86400  # Run daily

    def run(self, *args, **kwargs):
        """Check for stale currency rates"""

        # Get stale threshold from config
        try:
            config = PluginConfiguration.get_config()
            stale_days = config.currency_stale_days
        except Exception:
            stale_days = 7  # Fallback default

        stale_threshold = timezone.now() - timedelta(days=stale_days)
        stale_currencies = CurrencyConversionRate.objects.filter(
            last_updated__lt=stale_threshold
        )

        if not stale_currencies.exists():
            self.log_success("All currency rates are current")
            return

        self.log_warning(f"Found {stale_currencies.count()} stale currency rate(s):")

        for currency in stale_currencies:
            days_old = (timezone.now() - currency.last_updated).days
            self.log_info(
                f"{currency.currency_code}: {days_old} days old (last updated: {currency.last_updated})"
            )

        # Count how many are API-sourced (can be auto-synced)
        api_stale = stale_currencies.filter(source='api').count()
        manual_stale = stale_currencies.filter(source='manual').count()

        if api_stale > 0:
            self.log_info(f"{api_stale} API-sourced rate(s) can be synced automatically")

        if manual_stale > 0:
            self.log_warning(f"{manual_stale} manual rate(s) require manual update")


jobs = [SyncCurrencyRatesJob, CleanupStaleCurrencyRatesJob]
