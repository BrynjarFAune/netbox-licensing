from netbox.plugins import PluginTemplateExtension
from .models import LicenseInstance
from .tables import LicenseInstanceTable
from .choices import LicenseStatusChoices
from django.contrib.contenttypes.models import ContentType
from django.db.models import Sum
from decimal import Decimal

class ObjectLicenseInstance(PluginTemplateExtension):
    models = ['tenancy.contact', 'dcim.device', 'virtualization.virtualmachine', 'tenancy.tenant']

    def full_width_page(self):
        obj = self.context['object']
        ct = ContentType.objects.get_for_model(obj)

        instances = LicenseInstance.objects.filter(
            assigned_object_type=ct,
            assigned_object_id=obj.pk
        )

        if not instances.exists():
            return ""

        total_cost = sum(i.effective_price or Decimal('0') for i in instances)
        expiring_soon = sum(1 for i in instances if i.derived_status == LicenseStatusChoices.WARNING)
        expired = sum(1 for i in instances if i.derived_status == LicenseStatusChoices.EXPIRED)

        table = LicenseInstanceTable(instances, user=self.context['request'].user)

        return self.render("netbox_licenses/object_licenses.html", extra_context={
            "table": table,
            "total_cost": total_cost,
            "expiring_soon_count": expiring_soon,
            "expired_count": expired,
        })

template_extensions = [ObjectLicenseInstance]
