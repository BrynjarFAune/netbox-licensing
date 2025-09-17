import django_tables2 as tables

from netbox.tables import NetBoxTable, ChoiceFieldColumn
from .models import License, LicenseInstance
from .choices import LicenseStatusChoices

class LicenseTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    name = tables.Column(linkify=True)
    vendor = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    external_id = tables.Column(verbose_name="External ID", empty_values=())
    
    # UTILIZATION COLUMNS
    utilization = tables.Column(empty_values=(), verbose_name="Utilization %", orderable=False)
    total_licenses = tables.Column(verbose_name="Total")
    consumed_licenses = tables.Column(verbose_name="Used")
    available_licenses = tables.Column(empty_values=(), verbose_name="Available")

    # COST COLUMNS
    price = tables.Column(verbose_name="Unit Price", empty_values=())
    currency = tables.Column(verbose_name="Currency")
    total_cost = tables.Column(empty_values=(), verbose_name="Total Cost (NOK)")

    class Meta(NetBoxTable.Meta):
        model = License
        fields = (
            "pk", "name", "vendor", "tenant", "external_id",
            "utilization", "total_licenses", "consumed_licenses", "available_licenses",
            "price", "currency", "total_cost",
            "tags", "created", "last_updated", "actions"
        )
        default_columns = (
            "pk", "name", "vendor", "external_id", "utilization", "total_licenses", 
            "consumed_licenses", "available_licenses", "price", "currency"
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
        cost_value = float(str(record.total_cost)) if record.total_cost else 0
        return "{:.2f} NOK".format(cost_value)

class LicenseInstanceTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    license = tables.Column(linkify=True)
    assigned_object = tables.Column(linkify=True, verbose_name="Assigned To")
    start_date = tables.DateColumn(format='d/m/Y')
    end_date = tables.DateColumn(format='d/m/Y')
    status = tables.Column(verbose_name="Status", orderable=False, accessor='derived_status')
    auto_renew_status = tables.Column(empty_values=(), verbose_name="Auto-Renew", orderable=False)
    instance_price_nok = tables.Column(empty_values=(), verbose_name="Price (NOK)")

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
        from django.utils.html import format_html

        if record.auto_renew is None:
            # Using license default
            license_default = record.license.auto_renew if record.license else False
            default_text = "Yes" if license_default else "No"
            return format_html(
                '<span class="badge text-bg-secondary">Default ({})</span>',
                default_text
            )
        elif record.auto_renew:
            return format_html('<span class="badge text-bg-success">Yes</span>')
        else:
            return format_html('<span class="badge text-bg-warning">No</span>')


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
