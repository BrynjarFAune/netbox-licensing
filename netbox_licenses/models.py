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
        help_text="Currently assigned/consumed licenses (automatically calculated from instances)"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Vendor-specific data (service plans, features, API limits, etc.)"
    )

    # SUBSCRIPTION LIFECYCLE FIELDS
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('one_time', 'One-time Purchase'),
        ('custom', 'Custom Period')
    ]

    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default='monthly',
        help_text="How frequently this license is billed"
    )

    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew instances when they expire"
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
    
    def can_create_instance(self):
        """Check if a new instance can be created without exceeding total licenses"""
        return self.available_licenses > 0
    
    def get_availability_status(self):
        """Get human-readable availability status"""
        if self.available_licenses == 0:
            return "fully_allocated"
        elif self.available_licenses < 0:
            return "overallocated"
        elif self.utilization_percentage >= 90:
            return "nearly_full"
        else:
            return "available"

    # SUBSCRIPTION COST PROPERTIES
    @property
    def monthly_equivalent_price(self):
        """Normalize all pricing to monthly for comparison"""
        if not self.price:
            return 0

        if self.billing_cycle == 'monthly':
            return float(self.price)
        elif self.billing_cycle == 'quarterly':
            return float(self.price) / 3
        elif self.billing_cycle == 'yearly':
            return float(self.price) / 12
        elif self.billing_cycle == 'one_time':
            return 0  # No recurring cost
        else:  # custom
            return float(self.price)  # Assume monthly for custom

    @property
    def annual_equivalent_price(self):
        """Annual cost per license slot"""
        return self.monthly_equivalent_price * 12

    @property
    def total_monthly_consumed_cost(self):
        """Total monthly recurring cost for consumed licenses only"""
        return self.monthly_equivalent_price * self.consumed_licenses

    @property
    def total_annual_consumed_cost(self):
        """Total annual cost for consumed licenses only"""
        return self.annual_equivalent_price * self.consumed_licenses

    @property
    def total_monthly_commitment(self):
        """Total monthly commitment for all license slots (purchased capacity)"""
        return self.monthly_equivalent_price * self.total_licenses

    @property
    def total_yearly_commitment(self):
        """Total yearly commitment for all license slots (purchased capacity)"""
        return self.annual_equivalent_price * self.total_licenses

    # EXISTING PROPERTIES
    @cached_property
    def total_cost(self):
        """Total cost of all instances in NOK"""
        return sum(i.instance_price_nok for i in self.instances.all())
    
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

        # consumed_licenses should be managed by signals, not manually edited
        # But we can validate if it's being set incorrectly
        actual_consumed = self.instances.count() if self.pk else 0
        if hasattr(self, '_state') and not self._state.adding and self.consumed_licenses != actual_consumed:
            # Auto-correct instead of raising error - this is managed by signals
            self.consumed_licenses = actual_consumed

        # CRITICAL: Prevent reducing total_licenses below consumed_licenses
        if self.pk and self.total_licenses < actual_consumed:
            raise ValidationError(
                f"Cannot reduce total licenses to {self.total_licenses}. "
                f"There are currently {actual_consumed} licenses in use. "
                f"Please remove {actual_consumed - self.total_licenses} license instances first."
            )

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

    # Auto-renew setting - can override license default
    auto_renew = models.BooleanField(
        default=None,
        null=True,
        blank=True,
        help_text="Override auto-renew setting for this instance (leave blank to use license default)"
    )

    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.license.name} (#{self.id})"

    @property
    def license_currency(self):
        """Returns the currency from the parent license"""
        return self.license.currency

    @property
    def license_price(self):
        """Returns the base price from the parent license"""
        from decimal import Decimal
        return Decimal(str(self.license.price)) if self.license.price is not None else Decimal('0.0')

    @property
    def instance_price_nok(self):
        """Returns the NOK price for this instance - either override or license default"""
        from decimal import Decimal

        # If we have a NOK price override for this instance, use it
        if self.nok_price_override:
            return Decimal(str(self.nok_price_override))

        # If the license is already in NOK, use its price
        if self.license_currency == CurrencyChoices.NOK:
            return self.license_price

        # For other currencies, we'd need a conversion rate
        # Since we're simplifying, instances must specify NOK price if license isn't in NOK
        return Decimal('0.0')

    @property
    def display_price(self):
        """Returns a formatted price display string"""
        if self.nok_price_override:
            return f"{self.nok_price_override} NOK (instance override)"
        elif self.license_currency == CurrencyChoices.NOK:
            return f"{self.license_price} NOK"
        else:
            currency_display = dict(CurrencyChoices.CHOICES).get(self.license_currency, self.license_currency)
            return f"{self.license_price} {currency_display} (NOK price required)"

    @property
    def effective_auto_renew(self):
        """Returns the effective auto-renew setting - instance override or license default"""
        if self.auto_renew is not None:
            return self.auto_renew
        return self.license.auto_renew if self.license else False

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

    # SUBSCRIPTION LIFECYCLE PROPERTIES
    @property
    def renewal_status(self):
        """Smart status considering auto-renew and billing cycles"""
        from django.utils import timezone

        if self.license.auto_renew:
            if not self.end_date:
                return 'perpetual'
            return 'auto_renewing'

        # Manual renewal logic
        if not self.end_date:
            return 'no_expiry'

        today = timezone.now().date()
        days_until = (self.end_date - today).days

        if days_until < 0:
            return 'expired'
        elif days_until <= 7:
            return 'critical'
        elif days_until <= 30:
            return 'warning'
        else:
            return 'active'

    @property
    def monthly_cost_contribution(self):
        """How much this instance contributes to monthly costs"""
        # Use NOK price override if available, otherwise use license monthly equivalent
        if self.nok_price_override:
            return float(self.nok_price_override)
        return self.license.monthly_equivalent_price

    @property
    def is_auto_renewing(self):
        """Check if this instance auto-renews"""
        return self.license.auto_renew

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:licenseinstance', args=[self.pk])

    def clean(self):
        """Validate license instance allocation"""
        from django.core.exceptions import ValidationError
        super().clean()
        
        if self.license:
            # Check if creating a new instance would exceed total licenses
            current_count = self.license.instances.count()
            
            # If this is a new instance (no pk), increment the count
            if not self.pk:
                current_count += 1
            
            if current_count > self.license.total_licenses:
                raise ValidationError(
                    f"Cannot create license instance. This would exceed the total "
                    f"available licenses ({self.license.total_licenses}). "
                    f"Current instances: {self.license.instances.count()}"
                )

    def save(self, *args, **kwargs):
        # Only set default assignment type if none is set and there's an assigned object ID
        if not self.assigned_object_type_id and self.assigned_object_id and self.license:
            self.assigned_object_type = self.license.assignment_type

        # Smart end date calculation based on license billing cycle
        if self.start_date and not self.end_date and self.license:
            self._calculate_end_date()

        # Validate allocation limits before saving
        self.full_clean()

        # Don't auto-set price_override anymore - let it remain None to use license price
        super().save(*args, **kwargs)

    def _calculate_end_date(self):
        """Calculate end date based on license billing cycle"""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta

        cycle = self.license.billing_cycle

        if cycle == 'monthly':
            # Add 1 month using relativedelta for accurate month calculation
            self.end_date = self.start_date + relativedelta(months=1) - timedelta(days=1)
        elif cycle == 'quarterly':
            # Add 3 months
            self.end_date = self.start_date + relativedelta(months=3) - timedelta(days=1)
        elif cycle == 'yearly':
            # Add 1 year
            self.end_date = self.start_date + relativedelta(years=1) - timedelta(days=1)
        elif cycle == 'one_time':
            # No expiry for one-time purchases
            self.end_date = None
        else:  # custom
            # Default to 1 month for custom cycles
            self.end_date = self.start_date + relativedelta(months=1) - timedelta(days=1)


# Phase 3: Business Logic & Integration Models

class LicenseRenewal(NetBoxModel):
    """Track license renewal processes and approvals"""
    
    RENEWAL_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='renewals'
    )
    renewal_date = models.DateField(
        help_text="Date when license needs to be renewed"
    )
    new_end_date = models.DateField(
        null=True, blank=True,
        help_text="New expiration date after renewal"
    )
    status = models.CharField(
        max_length=20,
        choices=RENEWAL_STATUS_CHOICES,
        default='pending'
    )
    
    # Approval workflow
    requested_by = models.CharField(max_length=100, blank=True)
    approved_by = models.CharField(max_length=100, blank=True)
    approval_date = models.DateTimeField(null=True, blank=True)
    
    # Cost information
    renewal_cost = models.DecimalField(
        max_digits=12, decimal_places=2,
        null=True, blank=True
    )
    currency = models.CharField(
        max_length=3,
        choices=CurrencyChoices.CHOICES,
        default=CurrencyChoices.NOK
    )
    
    # Budget tracking
    budget_approved = models.BooleanField(default=False)
    budget_code = models.CharField(max_length=50, blank=True)
    
    # Workflow metadata
    workflow_data = models.JSONField(
        default=dict, blank=True,
        help_text="Workflow-specific data and approval history"
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-renewal_date']
    
    def __str__(self):
        return f"{self.license.name} renewal ({self.renewal_date})"
    
    @property
    def is_overdue(self):
        """Check if renewal is overdue"""
        return self.renewal_date < timezone.now().date() and self.status != 'completed'
    
    @property
    def days_until_renewal(self):
        """Days until renewal is due"""
        return (self.renewal_date - timezone.now().date()).days


class VendorIntegration(NetBoxModel):
    """Vendor API integration configurations"""
    
    INTEGRATION_TYPES = [
        ('microsoft365', 'Microsoft 365 Graph API'),
        ('generic_api', 'Generic REST API'),
        ('webhook', 'Webhook Integration'),
        ('csv_import', 'CSV Import'),
        ('ldap', 'LDAP/Active Directory'),
    ]
    
    SYNC_SCHEDULES = [
        ('hourly', 'Every Hour'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('manual', 'Manual Only'),
    ]
    
    vendor = models.ForeignKey(
        to=Manufacturer,
        on_delete=models.CASCADE,
        related_name='integrations'
    )
    integration_type = models.CharField(
        max_length=50,
        choices=INTEGRATION_TYPES
    )
    
    # API Configuration
    api_endpoint = models.URLField(blank=True)
    api_credentials = models.JSONField(
        default=dict, blank=True,
        help_text="Encrypted API credentials and configuration"
    )
    
    # Sync Configuration
    sync_schedule = models.CharField(
        max_length=20,
        choices=SYNC_SCHEDULES,
        default='daily'
    )
    last_sync = models.DateTimeField(null=True, blank=True)
    next_sync = models.DateTimeField(null=True, blank=True)
    
    # Status and health
    is_active = models.BooleanField(default=True)
    sync_errors = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    
    # Mapping configuration
    field_mappings = models.JSONField(
        default=dict, blank=True,
        help_text="Field mapping configuration between vendor and NetBox"
    )
    
    def __str__(self):
        return f"{self.vendor.name} - {self.get_integration_type_display()}"
    
    @property
    def sync_health(self):
        """Return sync health status"""
        if not self.is_active:
            return 'disabled'
        elif self.sync_errors > 5:
            return 'error'
        elif self.sync_errors > 0:
            return 'warning'
        else:
            return 'healthy'


class LicenseAnalytics(models.Model):
    """Store license analytics and metrics for trend analysis"""
    
    METRIC_TYPES = [
        ('utilization', 'Utilization Percentage'),
        ('cost', 'Total Cost'),
        ('instances', 'Instance Count'),
        ('available', 'Available Licenses'),
        ('consumed', 'Consumed Licenses'),
        ('efficiency', 'Cost Efficiency'),
    ]
    
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    metric_value = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Additional context
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Additional metric context and dimensions"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['license', 'metric_type', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.license.name} - {self.metric_type}: {self.metric_value}"


class LicenseAlert(NetBoxModel):
    """License alerts and notifications"""
    
    ALERT_TYPES = [
        ('expiring', 'License Expiring Soon'),
        ('expired', 'License Expired'),
        ('overallocated', 'License Overallocated'),
        ('underutilized', 'License Underutilized'),
        ('renewal_due', 'Renewal Due'),
        ('budget_exceeded', 'Budget Exceeded'),
        ('compliance_violation', 'Compliance Violation'),
        ('sync_error', 'Vendor Sync Error'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    ALERT_STATUS = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('suppressed', 'Suppressed'),
    ]
    
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    status = models.CharField(max_length=15, choices=ALERT_STATUS, default='active')
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Alert timing
    triggered_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Alert context
    alert_data = models.JSONField(
        default=dict, blank=True,
        help_text="Alert-specific data and context"
    )
    
    # Notification tracking
    notifications_sent = models.PositiveIntegerField(default=0)
    last_notification = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['status', '-triggered_at']),
            models.Index(fields=['alert_type', 'severity']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.license.name}"
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    @property
    def age_in_hours(self):
        """How long has this alert been active"""
        return (timezone.now() - self.triggered_at).total_seconds() / 3600


class CostAllocation(NetBoxModel):
    """License cost allocation to departments/projects"""
    
    ALLOCATION_TYPES = [
        ('department', 'Department'),
        ('project', 'Project'),
        ('cost_center', 'Cost Center'),
        ('business_unit', 'Business Unit'),
    ]
    
    license = models.ForeignKey(
        to=License,
        on_delete=models.CASCADE,
        related_name='cost_allocations'
    )
    allocation_type = models.CharField(max_length=20, choices=ALLOCATION_TYPES)
    allocation_target = models.CharField(
        max_length=100,
        help_text="Department/project/cost center identifier"
    )
    
    # Allocation percentages (should sum to 100% per license)
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Percentage of license cost allocated (0-100)"
    )
    
    # Time-based allocation
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    
    # Additional context
    allocation_rules = models.JSONField(
        default=dict, blank=True,
        help_text="Rules and criteria for this allocation"
    )
    
    class Meta:
        ordering = ['-effective_from']
        unique_together = ['license', 'allocation_target', 'effective_from']
    
    def __str__(self):
        return f"{self.license.name} -> {self.allocation_target} ({self.percentage}%)"
    
    @property
    def is_active(self):
        """Check if allocation is currently active"""
        today = timezone.now().date()
        return (self.effective_from <= today and 
                (self.effective_to is None or self.effective_to >= today))
