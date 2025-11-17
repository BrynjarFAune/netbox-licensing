import django_tables2 as tables
from django.utils.html import format_html

from netbox.tables import NetBoxTable, ChoiceFieldColumn, TagColumn
from .models import License, LicenseInstance, LicensePeriod, CurrencyConversionRate
from .choices import LicenseStatusChoices

class LicenseTable(NetBoxTable):
    # pk column provided automatically by NetBoxTable - do not redefine!
    name = tables.Column(linkify=True)
    vendor = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    external_id = tables.Column(verbose_name="External ID", empty_values=())
    status = tables.Column(empty_values=(), verbose_name="Status", orderable=False)
    tags = TagColumn(url_name='plugins:netbox_licenses:license_list')

    # UTILIZATION COLUMNS
    utilization = tables.Column(empty_values=(), verbose_name="Utilization %", orderable=False)
    total_licenses = tables.Column(verbose_name="Capacity")
    consumed_licenses = tables.Column(verbose_name="Used Seats")
    available_licenses = tables.Column(empty_values=(), verbose_name="Free Seats")

    # COST COLUMNS
    price = tables.Column(verbose_name="Unit Price", empty_values=())
    currency = tables.Column(verbose_name="Currency", empty_values=())
    total_cost = tables.Column(empty_values=(), verbose_name="Total Cost (NOK)")

    # PAYMENT AND RESPONSIBILITY COLUMNS
    payment_method = tables.Column(verbose_name="Payment Method")
    responsible_contact = tables.Column(linkify=True, verbose_name="Responsible")

    class Meta(NetBoxTable.Meta):
        model = License
        fields = (
            "pk", "name", "vendor", "tenant", "external_id", "status",
            "utilization", "total_licenses", "consumed_licenses", "available_licenses",
            "price", "currency", "total_cost", "payment_method", "responsible_contact",
            "tags", "created", "last_updated", "actions"
        )
        default_columns = (
            "pk", "name", "vendor", "status", "payment_method", "responsible_contact",
            "utilization", "total_licenses", "consumed_licenses", "available_licenses"
        )

    # NEW UTILIZATION RENDERING METHODS
    def render_external_id(self, record):
        return record.external_id or "—"

    def render_status(self, record):
        """Show active/inactive status badge based on periods"""
        if record.is_active:
            return format_html('<span class="badge text-bg-success">Active</span>')
        else:
            return format_html('<span class="badge text-bg-secondary">Inactive</span>')

    def render_utilization(self, record):
        from netbox_licenses.templatetags.license_helpers import utilization_badge
        return utilization_badge(record.utilization_percentage)

    def value_utilization(self, record):
        """Plain text value for CSV export"""
        return f"{record.utilization_percentage:.1f}%"

    def render_available_licenses(self, record):
        """Render free seats without color coding"""
        available = record.available_licenses
        if available < 0:
            return format_html('<span class="text-danger"><i class="mdi mdi-alert"></i> {}</span>', available)
        else:
            return available

    def value_available_licenses(self, record):
        """Plain text value for CSV export"""
        return record.available_licenses

    def render_price(self, record):
        """Render unit price as 'XXX.XX CUR → YYY.YY NOK'"""
        from .choices import PaymentMethodChoices
        if record.payment_method == PaymentMethodChoices.FREE_TRIAL:
            return "—"

        from netbox_licenses.models import CurrencyConversionRate

        per_seat_price = float(record.active_period_per_seat_price)
        currency = record.active_period_currency

        # If already in NOK, just show NOK price
        if currency == 'NOK':
            price_str = f"{per_seat_price:,.2f}".replace(',', "'")
            return f"{price_str} NOK"

        # Convert to NOK and show both
        rate = CurrencyConversionRate.get_rate_to_nok(currency)
        if rate:
            nok_price = per_seat_price * float(rate)
            native_str = f"{per_seat_price:.2f}"
            nok_str = f"{nok_price:,.2f}".replace(',', "'")
            return format_html('{} {} → {} NOK', native_str, currency, nok_str)
        else:
            return f"{per_seat_price:.2f} {currency}"

    def render_currency(self, record):
        """Display just the currency code"""
        return record.active_period_currency or "—"

    def render_total_cost(self, record):
        """Display total cost in NOK only with apostrophe separators"""
        from .choices import PaymentMethodChoices
        if record.payment_method == PaymentMethodChoices.FREE_TRIAL:
            return "—"

        from netbox_licenses.models import CurrencyConversionRate

        total_price = float(record.active_period_total_price)
        currency = record.active_period_currency

        # Get conversion rate to NOK
        rate = CurrencyConversionRate.get_rate_to_nok(currency)
        if rate is None:
            rate = 1  # Fallback if currency not found

        total_nok = total_price * float(rate)
        # Format with apostrophe as thousand separator
        formatted = f"{total_nok:,.2f}".replace(',', "'")
        return f"{formatted} NOK"

    def render_payment_method(self, record):
        from django.utils.html import format_html
        from .choices import PaymentMethodChoices
        method = record.get_payment_method_display()

        # Green for automatic operations
        if record.payment_method == PaymentMethodChoices.CARD_AUTO:
            return format_html('<span class="badge text-bg-success">{}</span>', method)
        # Yellow for manual operations
        elif record.payment_method in [PaymentMethodChoices.INVOICE, PaymentMethodChoices.CARD_MANUAL, PaymentMethodChoices.BANK_TRANSFER]:
            return format_html('<span class="badge text-bg-warning">{}</span>', method)
        # Gray for one-time purchases and free licenses (no action required)
        elif record.payment_method in [PaymentMethodChoices.PREPAID, PaymentMethodChoices.FREE_TRIAL]:
            return format_html('<span class="badge text-bg-secondary">{}</span>', method)
        else:
            return format_html('<span class="badge text-bg-secondary">{}</span>', method)

    def value_payment_method(self, record):
        """Plain text value for CSV export"""
        return record.get_payment_method_display()

    def render_responsible_contact(self, record):
        if record.responsible_contact:
            return record.responsible_contact
        return "—"

class LicenseInstanceTable(NetBoxTable):
    # pk column provided automatically by NetBoxTable
    license = tables.Column(linkify=True)
    assigned_object = tables.Column(verbose_name="Assigned To", orderable=False)
    start_date = tables.DateColumn(format='d/m/Y')
    end_date = tables.DateColumn(format='d/m/Y')
    status = tables.Column(verbose_name="Status", orderable=False, accessor='derived_status')
    instance_price_nok = tables.Column(empty_values=(), verbose_name="Price (NOK)")

    def render_assigned_object(self, record):
        """Render assigned object with proper link"""
        if record.assigned_object:
            url = getattr(record.assigned_object, 'get_absolute_url', lambda: '#')()
            return format_html('<a href="{}">{}</a>', url, record.assigned_object)
        return "—"

    class Meta(NetBoxTable.Meta):
        model = LicenseInstance
        fields = (
            'pk', 'id', 'license', 'assigned_object', 'start_date', 'end_date', 'status',
            'instance_price_nok', 'actions'
        )
        default_columns = (
            'pk', 'license', 'assigned_object', 'status', 'end_date'
        )

    def render_instance_price_nok(self, record):
        price = record.instance_price_nok
        if price:
            # Ensure we have a raw numeric value, not a SafeString
            price_value = float(str(price))
            return f"{price_value:.2f} NOK"
        return "—"

    def render_status(self, record):
        from .choices import LicenseStatusChoices
        from django.utils.html import format_html

        status = record.derived_status

        return format_html(
            '<span class="badge text-bg-{}">{}</span>',
            LicenseStatusChoices.CSS_CLASSES.get(status, "secondary"),
            dict(LicenseStatusChoices.CHOICES).get(status, status)
        )

    def value_status(self, record):
        """Plain text value for CSV export"""
        status = record.derived_status
        return dict(LicenseStatusChoices.CHOICES).get(status, status)


class CurrencyConversionRateTable(NetBoxTable):
    """Table for displaying currency conversion rates"""
    # pk column provided automatically by NetBoxTable
    currency_code = tables.Column(linkify=True, verbose_name='Currency')
    rate_to_nok = tables.Column(verbose_name='Rate to NOK')
    source = tables.Column(verbose_name='Source', empty_values=())
    last_updated = tables.DateTimeColumn(format='d/m/Y H:i', verbose_name='Last Updated')
    status = tables.Column(empty_values=(), verbose_name='Status', orderable=False)

    class Meta(NetBoxTable.Meta):
        model = CurrencyConversionRate
        fields = ('pk', 'currency_code', 'rate_to_nok', 'source', 'last_updated', 'status', 'actions')
        default_columns = ('currency_code', 'rate_to_nok', 'source', 'last_updated', 'status')

    def render_source(self, record):
        if record.source == 'manual':
            return format_html('<span class="badge text-bg-warning">Manual Entry</span>')
        else:
            return format_html('<span class="badge text-bg-primary">Norges Bank API</span>')

    def value_source(self, record):
        """Plain text value for CSV export"""
        return 'Manual Entry' if record.source == 'manual' else 'Norges Bank API'

    def render_status(self, record):
        if record.is_stale:
            return format_html('<span class="badge text-bg-danger"><i class="mdi mdi-alert"></i> Stale (>7 days)</span>')
        else:
            return format_html('<span class="badge text-bg-success"><i class="mdi mdi-check"></i> Current</span>')

    def value_status(self, record):
        """Plain text value for CSV export"""
        return 'Stale (>7 days)' if record.is_stale else 'Current'


class LicensePeriodTable(NetBoxTable):
    """Table for displaying license period history"""
    # pk column provided automatically by NetBoxTable
    license = tables.Column(linkify=True, verbose_name='License')
    period_start = tables.DateColumn(format='d/m/Y', verbose_name='Period Start')
    period_end = tables.DateColumn(format='d/m/Y', verbose_name='Period End')
    status = tables.Column(empty_values=(), verbose_name='Status', orderable=False)
    seats_purchased = tables.Column(verbose_name='Seats')
    utilization = tables.Column(empty_values=(), verbose_name='Utilization', orderable=False)
    price = tables.Column(verbose_name='Price', empty_values=())
    invoice_reference = tables.Column(verbose_name='Invoice #')

    class Meta(NetBoxTable.Meta):
        model = LicensePeriod
        fields = (
            'pk', 'id', 'license', 'period_start', 'period_end', 'status',
            'seats_purchased', 'utilization', 'price', 'currency',
            'payment_method', 'invoice_reference',
            'created', 'last_updated', 'actions'
        )
        default_columns = (
            'pk', 'license', 'period_start', 'period_end', 'status',
            'seats_purchased', 'utilization', 'price'
        )

    def render_utilization(self, record):
        """Show utilization percentage for this renewal period"""
        if record.seats_purchased == 0:
            return "—"

        percentage = (record.seats_utilized / record.seats_purchased) * 100

        if percentage >= 90:
            color = 'success'
        elif percentage >= 70:
            color = 'info'
        elif percentage >= 50:
            color = 'warning'
        else:
            color = 'danger'

        return format_html(
            '<span class="badge text-bg-{}">{}</span>',
            color,
            f"{percentage:.1f}%"
        )

    def value_utilization(self, record):
        """Plain text value for CSV export"""
        if record.seats_purchased == 0:
            return "0%"
        percentage = (record.seats_utilized / record.seats_purchased) * 100
        return f"{percentage:.1f}%"

    def render_status(self, record):
        """Show active/expired/pending status badge"""
        from django.utils import timezone
        today = timezone.now().date()

        if record.period_start > today:
            # Period hasn't started yet
            return format_html('<span class="badge text-bg-info">Pending</span>')
        elif record.period_end and record.period_end < today:
            # Period has ended
            return format_html('<span class="badge text-bg-danger">Expired</span>')
        else:
            # Currently active
            return format_html('<span class="badge text-bg-success">Active</span>')

    def render_price(self, record):
        """Format price with currency based on pricing mode"""
        from .choices import PricingModeChoices
        if record.pricing_mode == PricingModeChoices.PER_SEAT:
            return f"{record.per_seat_price:.2f} {record.currency}/seat"
        else:
            return f"{record.total_price:.2f} {record.currency} total"

