from netbox.plugins import PluginTemplateExtension
from .models import LicenseInstance
from .tables import LicenseInstanceTable
from .choices import LicenseStatusChoices
from django.db.models import Sum
from decimal import Decimal

class ContactLicenseInstance(PluginTemplateExtension):
    models = ['tenancy.contact']

    def right_page(self):
        instances = LicenseInstance.objects.filter(assigned_user=self.context['object'])
        if not instances.exists():
            return ""

        total_cost = sum(instance.effective_price or Decimal('0') for instance in instances)
        expiring_soon_count = sum(1 for instance in instances if instance.derived_status == LicenseStatusChoices.WARNING)
        expired_count = sum(1 for instance in instances if instance.derived_status == LicenseStatusChoices.EXPIRED)

        table = LicenseInstanceTable(instances, user=self.context['request'].user)

        return self.render("netbox_licenses/contact_licenses.html", extra_context={
            "table": table,
            "total_cost": total_cost,
            "expiring_soon_count": expiring_soon_count,
            "expired_count": expired_count,
        })

template_extensions = [ContactLicenseInstance]
