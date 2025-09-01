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
from .choices import LicenseStatusChoices, CurrencyChoices


class License(NetBoxModel):
    name = models.CharField(
        max_length=50
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
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.CHOICES,
        default=CurrencyChoices.NOK,
        help_text="Currency for the license price"
    )
    
    # NEW ENHANCEMENT FIELDS
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="Vendor-specific identifier (SKU ID, subscription ID, license key, etc.)"
    )
    
    total_licenses = models.PositiveIntegerField(
        default=1,
        help_text="Total available license slots purchased"
    )
    
    consumed_licenses = models.PositiveIntegerField(
        default=0,
        help_text="Currently assigned/consumed licenses"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Vendor-specific data (service plans, features, API limits, etc.)"
    )
    
    # LEGACY FIELD - keeping for backward compatibility
    total_instances = models.PositiveIntegerField(default=0)
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.vendor.name})"

    # NEW COMPUTED PROPERTIES
    @property
    def available_licenses(self):
        """Calculate remaining available licenses"""
        return self.total_licenses - self.consumed_licenses
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_licenses == 0:
            return 0
        return (self.consumed_licenses / self.total_licenses) * 100
    
    # EXISTING PROPERTIES
    @cached_property
    def total_cost(self):
        """Total cost of all instances in NOK"""
        return sum(i.price_in_nok for i in self.instances.all())
    
    @property 
    def price_display(self):
        """Returns formatted price with currency symbol"""
        return f"{self.price} {self.currency}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:license', args=[self.pk])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["name", "vendor", "tenant"], name="unique_license_key")
        ]
        indexes = [
            models.Index(fields=['external_id']),
            models.Index(fields=['vendor', 'external_id']),
            models.Index(fields=['consumed_licenses', 'total_licenses']),
        ]
    
    def clean(self):
        """Validate license data"""
        from django.core.exceptions import ValidationError
        super().clean()
        
        if self.total_licenses < 0:
            raise ValidationError("Total licenses cannot be negative")
        
        if self.consumed_licenses < 0:
            raise ValidationError("Consumed licenses cannot be negative")

class LicenseInstance(NetBoxModel):
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='instances'
    )

    assigned_object_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    assigned_object_id = models.PositiveIntegerField(null=True, blank=True)
    assigned_object = GenericForeignKey("assigned_object_type", "assigned_object_id")

    price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    currency_override = models.CharField(
        max_length=3,
        choices=CurrencyChoices.CHOICES,
        null=True,
        blank=True,
        help_text="Override currency for this specific instance"
    )
    nok_price_override = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override price in NOK for currency conversion calculations"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.license.name} (#{self.id})"

    @property
    def effective_currency(self):
        """Returns the currency used for this instance"""
        return self.currency_override or self.license.currency
    
    @property
    def effective_price(self):
        """Returns the price in the instance's effective currency"""
        from decimal import Decimal
        price = self.price_override or self.license.price
        return Decimal(str(price)) if price is not None else Decimal('0.0')
    
    @property
    def effective_conversion_rate(self):
        """Returns the conversion rate to NOK, calculated on demand"""
        from decimal import Decimal
        if self.effective_currency == CurrencyChoices.NOK:
            return Decimal('1.0')
        
        # Calculate conversion rate from NOK price override and foreign price
        nok_price = self.nok_price_override
        foreign_price = self.effective_price
        
        if nok_price and foreign_price and foreign_price > 0:
            try:
                return Decimal(str(nok_price)) / Decimal(str(foreign_price))
            except (ValueError, TypeError, ZeroDivisionError):
                pass
        
        return Decimal('1.0')  # Default fallback
    
    @property
    def price_in_nok(self):
        """Returns the price in NOK - either direct NOK price or converted from override"""
        from decimal import Decimal
        
        # If we have a NOK price override, use it directly
        if self.nok_price_override:
            return Decimal(str(self.nok_price_override))
        
        # If currency is NOK, use the effective price directly
        if self.effective_currency == CurrencyChoices.NOK:
            return self.effective_price
        
        # For non-NOK currencies, calculate from conversion rate
        try:
            price = self.effective_price
            rate = self.effective_conversion_rate
            return price * rate
        except (ValueError, TypeError, AttributeError):
            return Decimal('0.0')

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
    
    # NEW HELPER METHODS FOR ASSIGNMENT DISPLAY
    def get_assignment_display(self):
        """Return human-readable assignment info"""
        if not self.assigned_object:
            return "Unassigned"
        
        if self.assigned_object_type.model == 'user':
            return f"User: {self.assigned_object.username}"
        elif self.assigned_object_type.model == 'device':
            return f"Device: {self.assigned_object.name}"
        elif self.assigned_object_type.model == 'contact':
            return f"Contact: {self.assigned_object.name}"
        elif self.assigned_object_type.model == 'virtualmachine':
            return f"VM: {self.assigned_object.name}"
        elif self.assigned_object_type.model == 'tenant':
            return f"Tenant: {self.assigned_object.name}"
        elif self.assigned_object_type.model == 'service':
            return f"Service: {self.assigned_object.name}"
        else:
            return f"{self.assigned_object_type.model.title()}: {str(self.assigned_object)}"
    
    @property
    def assignment_type(self):
        """Return assignment type for filtering"""
        return self.assigned_object_type.model if self.assigned_object_type else None

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:licenseinstance', args=[self.pk])

    def save(self, *args, **kwargs):
        # Only set default assignment type if none is set and there's an assigned object ID
        if not self.assigned_object_type_id and self.assigned_object_id and self.license:
            self.assigned_object_type = self.license.assignment_type

        # Don't auto-set price_override anymore - let it remain None to use license price
        super().save(*args, **kwargs)
