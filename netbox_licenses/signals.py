from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Q
from .models import LicenseInstance


@receiver([post_save, post_delete], sender=LicenseInstance)
def update_consumed_licenses(sender, instance, **kwargs):
    """
    Automatically update consumed_licenses when instances are added/removed

    This signal handler ensures that the License.consumed_licenses field
    is always accurate and reflects the current number of ACTIVE LicenseInstance
    objects (those without end_date or with end_date in the future).
    """
    if instance.license:
        license = instance.license
        # Count only active instances (no end_date or end_date in future)
        today = timezone.now().date()
        license.consumed_licenses = license.instances.filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).count()
        # Use update_fields to avoid triggering other signals
        license.save(update_fields=['consumed_licenses'])