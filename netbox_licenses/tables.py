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
    
    # ENHANCED UTILIZATION COLUMNS
    utilization = tables.Column(empty_values=(), verbose_name="Utilization", orderable=False)
    total_licenses = tables.Column(verbose_name="Total")
    consumed_licenses = tables.Column(verbose_name="Used")
    available_licenses = tables.Column(empty_values=(), verbose_name="Available")
    
    # EXISTING COLUMNS
    instance_count = tables.Column(empty_values=(), verbose_name="Instances")
    price = tables.Column(verbose_name="Price", empty_values=())
    currency = tables.Column(verbose_name="Currency")
    total_cost = tables.Column(empty_values=(), verbose_name="Total Cost (NOK)")
    assigned_count = tables.Column(empty_values=(), verbose_name="Assigned")
    warning_count = tables.Column(empty_values=(), verbose_name="Expiring Soon")

    class Meta(NetBoxTable.Meta):
        model = License
        fields = (
            "pk", "name", "vendor", "tenant", "external_id", 
            "utilization", "total_licenses", "consumed_licenses", "available_licenses",
            "price", "currency", "instance_count", "assigned_count", "warning_count", "total_cost",
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
        from django.utils.html import format_html
        percentage = record.utilization_percentage
        # Ensure we have a raw numeric value, not a SafeString
        percentage_value = float(str(percentage)) if percentage is not None else 0.0

        if percentage_value < 80:
            color_class = "success"  # Green
        elif percentage_value < 100:
            color_class = "warning"  # Orange
        else:
            color_class = "danger"   # Red

        return format_html(
            '<span class="badge text-bg-{}">{:.1f}%</span>',
            color_class, percentage_value
        )
    
    def render_available_licenses(self, record):
        available = record.available_licenses
        if available < 0:
            return format_html('<span class="text-danger">{}</span>', available)
        elif available == 0:
            return format_html('<span class="text-warning">{}</span>', available)
        else:
            return str(available)

    # EXISTING RENDERING METHODS
    def render_instance_count(self, record):
        return record.instances.count()

    def render_price(self, record):
        price_value = float(record.price) if record.price else 0
        return "{} {}".format(price_value, record.currency)

    def render_total_cost(self, record):
        cost_value = float(record.total_cost) if record.total_cost else 0
        return "{:.2f} NOK".format(cost_value)

    def render_assigned_count(self, record):
        return sum(1 for i in record.instances.all() if i.assigned_object is not None)

    def render_warning_count(self, record):
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        warning_date = today + timedelta(days=30)
        return record.instances.filter(
            end_date__lte=warning_date,
            end_date__gte=today
        ).count()

class LicenseInstanceTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    license = tables.Column(linkify=True)
    assigned_object = tables.Column(linkify=True, verbose_name="Assigned To")
    assignment_display = tables.Column(empty_values=(), verbose_name="Assignment Details", orderable=False)
    start_date = tables.DateColumn(format='d/m/Y')
    end_date = tables.DateColumn(format='d/m/Y')
    status = tables.Column(verbose_name="Status", orderable=False, accessor='derived_status')
    license_price = tables.Column(empty_values=(), verbose_name="License Price", accessor='license.price')
    license_currency = tables.Column(empty_values=(), verbose_name="Currency", accessor='license.currency')
    instance_price_nok = tables.Column(empty_values=(), verbose_name="Instance Price (NOK)")

    class Meta(NetBoxTable.Meta):
        model = LicenseInstance
        fields = (
            'pk', 'id', 'license', 'assigned_object', 'assignment_display', 'start_date', 'end_date', 'status',
            'license_price', 'license_currency', 'instance_price_nok', 'actions'
        )
        default_columns = (
            'pk', 'id', 'license', 'assignment_display', 'license_currency', 'instance_price_nok', 'status'
        )

    def render_assignment_display(self, record):
        return record.get_assignment_display()

    def render_license_price(self, record):
        price_value = float(record.license.price) if record.license.price else 0
        return "{} {}".format(price_value, record.license.currency)

    def render_license_currency(self, record):
        from .choices import CurrencyChoices
        return dict(CurrencyChoices.CHOICES).get(record.license.currency, record.license.currency)

    def render_instance_price_nok(self, record):
        price = record.instance_price_nok
        if price:
            # Ensure we have a raw numeric value, not a SafeString
            price_value = float(str(price))
            return "{:.2f} NOK".format(price_value)
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
