from django.urls import reverse
from django.contrib.postgres.fields import ArrayField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property
from django.utils import timezone
from datetime import timedelta
from django.db import models
from netbox.models import NetBoxModel
from tenancy.models import Contact, Tenant
from dcim.models import Manufacturer
from .choices import LicenseStatusChoices


class License(NetBoxModel):
    name = models.CharField(
        max_length=30
    )
    vendor = models.ForeignKey(
        to=Manufacturer,
        on_delete=models.PROTECT,
        related_name='licenses'
    )
    tenant = models.ForeignKey(
        to=Tenant,
        on_delete=models.PROTECT,
        related_name='licenses'
    )
    assignment_type = models.ForeignKey(
        ContentType,
        limit_choices_to={
            "model__in": ["contact", "device", "virtualmachine", "tenant", "service"]
        },
        on_delete=models.PROTECT,
        help_text="What object type will the license be assigned to"
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.vendor.name})"

    @cached_property
    def total_cost(self):
        return sum(i.effective_price for i in self.instances.all())

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:license', args=[self.pk])

    class Meta:
        constraints = [
        models.UniqueConstraint(fields=["name", "vendor", "tenant"], name="unique_license_key")
    ]

class LicenseInstance(NetBoxModel):
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='instances'
    )

    assigned_object_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    assigned_object_id = models.PositiveIntegerField()
    assigned_object = GenericForeignKey("assigned_object_type", "assigned_object_id")

    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.license.name} (#{self.id})"

    @property
    def effective_price(self):
        return self.price_override or self.license.price

    @property
    def derived_status(self):
        today = timezone.now().date()

        if self.start_date and self.start_date > today:
            return LicenseStatusChoices.PENDING

        if self.end_date:
            if self.end_date < today:
                return LicenseStatusChoices.EXPIRED
            elif self.end_date <= today + timedelta(days=30):
                return LicenseStatusChoices.WARNING

        return LicenseStatusChoices.ACTIVE

    @property
    def get_derived_status_class(self):
        return LicenseStatusChoices.CSS_CLASSES.get(self.derived_status, 'default')

    @property
    def is_available(self):
        return self.assigned_object is None and self.derived_status != LicenseStatusChoices.EXPIRED

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:licenseinstance', args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.assigned_object_type_id and self.license:
            self.assigned_object_type = self.license.assignment_type

        if self.price_override is None and not self.pk:
            self.price_override = self.license.price

        super().save(*args, **kwargs)
