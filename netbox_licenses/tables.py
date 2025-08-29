import django_tables2 as tables

from netbox.tables import NetBoxTable, ChoiceFieldColumn
from .models import License, LicenseInstance
from .choices import LicenseStatusChoices

class LicenseTable(NetBoxTable):
    pk = tables.CheckBoxColumn()
    name = tables.Column(linkify=True)
    vendor = tables.Column(linkify=True)
    tenant = tables.Column(linkify=True)
    instance_count = tables.Column(empty_values=(), verbose_name="Instances")
    price = tables.Column(verbose_name="Price", empty_values=())
    currency = tables.Column(verbose_name="Currency")
    total_cost = tables.Column(empty_values=(), verbose_name="Total Cost (NOK)")
    assigned_count = tables.Column(empty_values=(), verbose_name="Assigned")
    warning_count = tables.Column(empty_values=(), verbose_name="Expiring Soon")

    class Meta(NetBoxTable.Meta):
        model = License
        fields = (
            "pk", "name", "vendor", "tenant", "price", "currency",
            "instance_count", "assigned_count", "warning_count", "total_cost",
            "tags", "created", "last_updated", "actions"
        )
        default_columns = (
            "pk", "name", "vendor", "tenant", "price", "currency", "instance_count", "total_cost"
        )

    def render_instance_count(self, record):
        return record.instances.count()

    def render_price(self, record):
        return f"{record.price} {record.currency}"
    
    def render_total_cost(self, record):
        return f"{record.total_cost:.2f} NOK"

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
    start_date = tables.DateColumn(format='d/m/Y')
    end_date = tables.DateColumn(format='d/m/Y')
    status = tables.Column(verbose_name="Status", orderable=False, accessor='derived_status')
    effective_price = tables.Column(empty_values=(), verbose_name="Price")
    effective_currency = tables.Column(empty_values=(), verbose_name="Currency")
    price_in_nok = tables.Column(empty_values=(), verbose_name="Price (NOK)")

    class Meta(NetBoxTable.Meta):
        model = LicenseInstance
        fields = (
            'pk', 'id', 'license', 'assigned_object', 'start_date', 'end_date', 'status', 
            'effective_price', 'effective_currency', 'price_in_nok', 'actions'
        )
        default_columns = (
            'pk', 'id', 'license', 'assigned_object', 'effective_price', 'effective_currency', 'price_in_nok', 'status'
        )

    def render_effective_price(self, record):
        return f"{record.effective_price} {record.effective_currency}"
    
    def render_effective_currency(self, record):
        return record.effective_currency
    
    def render_price_in_nok(self, record):
        return f"{record.price_in_nok:.2f} NOK"

    def render_status(self, record):
        from .choices import LicenseStatusChoices
        from django.utils.html import format_html

        status = record.derived_status

        return format_html(
            '<span class="badge text-bg-{}">{}</span>',
            LicenseStatusChoices.CSS_CLASSES.get(status, "secondary"),
            dict(LicenseStatusChoices.CHOICES).get(status, status)
        )
