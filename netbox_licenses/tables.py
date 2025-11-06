import django_tables2 as tables
from django.utils.html import format_html

from netbox.tables import NetBoxTable, ChoiceFieldColumn
from .models import License, LicenseInstance, CurrencyConversionRate
from .choices import LicenseStatusChoices

class LicenseTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    name = tables.Column(linkify=True)
    vendor = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    external_id = tables.Column(verbose_name="External ID", empty_values=())
    
    # UTILIZATION COLUMNS
    utilization = tables.Column(empty_values=(), verbose_name="Utilization %", orderable=False)
    total_licenses = tables.Column(verbose_name="Capacity")
    consumed_licenses = tables.Column(verbose_name="Instances")
    available_licenses = tables.Column(empty_values=(), verbose_name="Available")

    # COST COLUMNS
    price = tables.Column(verbose_name="Unit Price", empty_values=())
    currency = tables.Column(verbose_name="Currency")
    total_cost = tables.Column(empty_values=(), verbose_name="Total Cost (NOK)")

    # PAYMENT AND RESPONSIBILITY COLUMNS
    payment_method = tables.Column(verbose_name="Payment Method")
    responsible_contact = tables.Column(linkify=True, verbose_name="Responsible")

    class Meta(NetBoxTable.Meta):
        model = License
        fields = (
            "pk", "name", "vendor", "tenant", "external_id",
            "utilization", "total_licenses", "consumed_licenses", "available_licenses",
            "price", "currency", "total_cost", "payment_method", "responsible_contact",
            "tags", "created", "last_updated", "actions"
        )
        default_columns = (
            "pk", "name", "vendor", "payment_method", "responsible_contact",
            "utilization", "total_licenses", "consumed_licenses", "available_licenses"
        )

    # NEW UTILIZATION RENDERING METHODS
    def render_external_id(self, record):
        return record.external_id or "—"
    
    def render_utilization(self, record):
        from netbox_licenses.templatetags.license_helpers import utilization_badge
        return utilization_badge(record.utilization_percentage)
    
    def render_available_licenses(self, record):
        from django.utils.html import format_html
        from netbox_licenses.templatetags.license_helpers import availability_color

        available = record.available_licenses
        color_class = availability_color(available)

        if available < 0:
            return format_html('<span class="{}"><i class="mdi mdi-alert"></i> {}</span>', color_class, available)
        else:
            return format_html('<span class="{}">{}</span>', color_class, available)

    def render_price(self, record):
        price_value = float(record.price) if record.price else 0
        return "{} {}".format(price_value, record.currency)

    def render_total_cost(self, record):
        """Calculate total cost as unit price × capacity in NOK"""
        total_nok = float(record.total_monthly_commitment_nok) if record.total_monthly_commitment_nok else 0
        return "{:,.2f} NOK".format(total_nok)

    def render_payment_method(self, record):
        from django.utils.html import format_html
        method = record.get_payment_method_display()
        if record.payment_method == 'card_auto':
            return format_html('<span class="badge text-bg-success">{}</span>', method)
        elif record.payment_method in ['invoice', 'card_manual']:
            return format_html('<span class="badge text-bg-warning">{}</span>', method)
        elif record.payment_method == 'free_trial':
            return format_html('<span class="badge text-bg-info">{}</span>', method)
        else:
            return format_html('<span class="badge text-bg-secondary">{}</span>', method)

    def render_responsible_contact(self, record):
        if record.responsible_contact:
            return record.responsible_contact
        return "—"

class LicenseInstanceTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    license = tables.Column(linkify=True)
    assigned_object = tables.Column(verbose_name="Assigned To", orderable=False)
    start_date = tables.DateColumn(format='d/m/Y')
    end_date = tables.DateColumn(format='d/m/Y')
    status = tables.Column(verbose_name="Status", orderable=False, accessor='derived_status')
    auto_renew_status = tables.Column(empty_values=(), verbose_name="Auto-Renew", orderable=False)
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
            'auto_renew_status', 'instance_price_nok', 'actions'
        )
        default_columns = (
            'pk', 'license', 'assigned_object', 'status', 'auto_renew_status', 'end_date'
        )

    def render_auto_renew_status(self, record):
        """Show payment method status from parent license"""
        if not record.license:
            return "—"

        payment_method = record.license.payment_method

        # Auto-charging payment methods
        if payment_method == 'card_auto':
            return format_html('<span class="badge text-bg-success">Auto-Charge</span>')
        elif payment_method in ['invoice', 'card_manual', 'bank_transfer', 'purchase_order']:
            return format_html('<span class="badge text-bg-warning">Manual</span>')
        elif payment_method == 'prepaid':
            return format_html('<span class="badge text-bg-info">Prepaid</span>')
        elif payment_method == 'free_trial':
            return format_html('<span class="badge text-bg-secondary">Trial</span>')
        else:
            return format_html('<span class="badge text-bg-secondary">{}</span>', payment_method)


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


class CurrencyConversionRateTable(NetBoxTable):
    """Table for displaying currency conversion rates"""

    pk = tables.CheckBoxColumn()
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

    def render_status(self, record):
        if record.is_stale:
            return format_html('<span class="badge text-bg-danger"><i class="mdi mdi-alert"></i> Stale (>7 days)</span>')
        else:
            return format_html('<span class="badge text-bg-success"><i class="mdi mdi-check"></i> Current</span>')
