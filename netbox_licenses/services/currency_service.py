"""
Currency conversion rate service with Norges Bank API integration.

Norges Bank provides exchange rates via their API:
https://data.norges-bank.no/api/data/EXR/
"""

import requests
from decimal import Decimal
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class NorgesBankAPIError(Exception):
    """Exception raised when Norges Bank API fails"""
    pass


def fetch_currency_rate_from_api(currency_code):
    """
    Fetch the latest exchange rate for a currency from Norges Bank API.

    Args:
        currency_code (str): ISO 4217 currency code (e.g., 'USD', 'EUR')

    Returns:
        Decimal: The exchange rate (1 currency_code = X NOK)

    Raises:
        NorgesBankAPIError: If API request fails or currency not found
    """
    currency_code = currency_code.upper()

    if currency_code == 'NOK':
        return Decimal('1.0')

    # Norges Bank API endpoint
    # B = Business day frequency
    # SP = Spot rate
    url = f"https://data.norges-bank.no/api/data/EXR/B.{currency_code}.NOK.SP"
    params = {
        'format': 'sdmx-json',
        'lastNObservations': 1,  # Get only the most recent rate
        'locale': 'en'
    }

    try:
        logger.info(f"Fetching rate for {currency_code} from Norges Bank API")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Parse the SDMX-JSON response
        # Structure: data.dataSets[0].series['0:0:0:0'].observations['0'][0]
        try:
            datasets = data.get('data', {}).get('dataSets', [])
            if not datasets:
                raise NorgesBankAPIError(f"No data found for currency {currency_code}")

            series = datasets[0].get('series', {})
            if not series:
                raise NorgesBankAPIError(f"No series data for currency {currency_code}")

            # Get the first (and only) series
            series_key = list(series.keys())[0]
            observations = series[series_key].get('observations', {})

            if not observations:
                raise NorgesBankAPIError(f"No observations for currency {currency_code}")

            # Get the most recent observation
            obs_key = list(observations.keys())[0]
            rate_value = observations[obs_key][0]  # [0] is the rate value

            rate = Decimal(str(rate_value))
            logger.info(f"Successfully fetched rate for {currency_code}: {rate} NOK")
            return rate

        except (KeyError, IndexError, TypeError) as e:
            raise NorgesBankAPIError(
                f"Failed to parse Norges Bank API response for {currency_code}: {e}"
            )

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise NorgesBankAPIError(
                f"Currency {currency_code} not found in Norges Bank database. "
                f"This currency may not be available or may require manual entry."
            )
        else:
            raise NorgesBankAPIError(
                f"HTTP error fetching rate for {currency_code}: {e}"
            )

    except requests.exceptions.RequestException as e:
        raise NorgesBankAPIError(
            f"Network error fetching rate for {currency_code}: {e}"
        )


def sync_currency_rate(currency_rate):
    """
    Sync a single currency rate object from the API.

    Args:
        currency_rate: CurrencyConversionRate model instance

    Returns:
        bool: True if sync succeeded, False otherwise

    Raises:
        NorgesBankAPIError: If API request fails
    """
    from netbox_licenses.models import CurrencyConversionRate

    if currency_rate.source != 'api':
        logger.warning(
            f"Cannot sync {currency_rate.currency_code}: source is '{currency_rate.source}', not 'api'"
        )
        return False

    try:
        new_rate = fetch_currency_rate_from_api(currency_rate.currency_code)
        currency_rate.rate_to_nok = new_rate
        currency_rate.save()

        logger.info(
            f"Updated {currency_rate.currency_code} rate to {new_rate} NOK"
        )
        return True

    except NorgesBankAPIError as e:
        logger.error(f"Failed to sync {currency_rate.currency_code}: {e}")
        raise


def sync_all_currency_rates():
    """
    Sync all API-sourced currency rates from Norges Bank.

    Returns:
        dict: Summary of sync results with 'success', 'failed', and 'skipped' counts
    """
    from netbox_licenses.models import CurrencyConversionRate

    api_rates = CurrencyConversionRate.objects.filter(source='api')

    results = {
        'success': [],
        'failed': [],
        'total': api_rates.count()
    }

    logger.info(f"Starting sync for {results['total']} API-sourced currencies")

    for rate in api_rates:
        try:
            sync_currency_rate(rate)
            results['success'].append(rate.currency_code)
        except NorgesBankAPIError as e:
            results['failed'].append({
                'currency': rate.currency_code,
                'error': str(e)
            })

    logger.info(
        f"Currency sync complete: {len(results['success'])} succeeded, "
        f"{len(results['failed'])} failed"
    )

    return results


def create_currency_from_api(currency_code, notes=''):
    """
    Create a new currency conversion rate by fetching from API.

    Args:
        currency_code (str): ISO 4217 currency code
        notes (str): Optional notes about the currency

    Returns:
        CurrencyConversionRate: The created currency rate object

    Raises:
        NorgesBankAPIError: If API request fails
        ValidationError: If currency already exists
    """
    from netbox_licenses.models import CurrencyConversionRate
    from django.core.exceptions import ValidationError

    currency_code = currency_code.upper()

    # Check if currency already exists
    if CurrencyConversionRate.objects.filter(currency_code=currency_code).exists():
        raise ValidationError(
            f"Currency {currency_code} already exists. "
            f"Use the sync button to update its rate."
        )

    # Fetch rate from API
    rate = fetch_currency_rate_from_api(currency_code)

    # Create the currency rate
    currency_rate = CurrencyConversionRate.objects.create(
        currency_code=currency_code,
        rate_to_nok=rate,
        source='api',
        notes=notes
    )

    logger.info(f"Created new currency {currency_code} with rate {rate} NOK")
    return currency_rate
