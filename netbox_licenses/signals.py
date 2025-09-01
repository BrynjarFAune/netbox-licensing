from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import LicenseInstance


@receiver([post_save, post_delete], sender=LicenseInstance)
def update_consumed_licenses(sender, instance, **kwargs):
    """
    Automatically update consumed_licenses when instances are added/removed
    
    This signal handler ensures that the License.consumed_licenses field
    is always accurate and reflects the current number of LicenseInstance
    objects assigned to each license.
    """
    if instance.license:
        license = instance.license
        # Count all instances for this license
        license.consumed_licenses = license.instances.count()
        # Use update_fields to avoid triggering other signals
        license.save(update_fields=['consumed_licenses'])