from django.urls import reverse
from django.contrib.postgres.fields import ArrayField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db import models
from netbox.models import NetBoxModel
from tenancy.models import Contact, Tenant
from dcim.models import Manufacturer
from .choices import LicenseStatusChoices, CurrencyChoices, PaymentMethodChoices, PricingModeChoices


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
        to=ContentType,
        on_delete=models.PROTECT,
        related_name='licenses_by_type',
        help_text="What object type can be assigned to this license"
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
        blank=True,
        help_text="How frequently this license is billed (optional - for reference only)"
    )

    # Contract dates removed - defined by LicensePeriods instead

    auto_renew = models.BooleanField(
        default=False,
        help_text="Automatically renew instances when they expire (deprecated - use payment_method instead)"
    )

    # PAYMENT METHOD FIELDS
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethodChoices.CHOICES,
        default=PaymentMethodChoices.INVOICE,
        help_text="How this license is paid for"
    )

    payment_portal_url = models.URLField(
        blank=True,
        null=True,
        max_length=500,
        help_text="URL to payment portal or subscription management page"
    )

    # RESPONSIBILITY TRACKING
    responsible_contact = models.ForeignKey(
        to=Contact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='responsible_for_licenses',
        help_text="Person responsible for maintaining this license (payments, renewals, compliance)"
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

    # SUBSCRIPTION COST PROPERTIES (based on active period)
    @property
    def active_period_total_price(self):
        """Get total price from active period (or 0 if no active period)"""
        active_period = self.get_active_period()
        if not active_period:
            return Decimal('0.00')
        return active_period.total_price

    @property
    def active_period_per_seat_price(self):
        """Get per-seat price from active period (or 0 if no active period)"""
        active_period = self.get_active_period()
        if not active_period:
            return Decimal('0.00')
        return active_period.per_seat_price

    @property
    def active_period_currency(self):
        """Get currency code from active period (or NOK if no active period)"""
        active_period = self.get_active_period()
        if not active_period:
            return 'NOK'
        # currency is now a ForeignKey to CurrencyConversionRate
        return active_period.currency.currency_code if active_period.currency else 'NOK'

    @property
    def monthly_equivalent_price(self):
        """
        Get per-seat price from active period.
        Note: This doesn't normalize to monthly - just returns per-seat price.
        Use period dates for actual billing calculations.
        """
        return float(self.active_period_per_seat_price)

    @property
    def total_monthly_commitment_nok(self):
        """Total monthly commitment converted to NOK"""
        per_seat_monthly = self.monthly_equivalent_price
        if per_seat_monthly == 0:
            return Decimal('0.00')

        total_monthly = Decimal(str(per_seat_monthly)) * self.total_licenses

        # Convert to NOK
        currency = self.active_period_currency
        if currency == 'NOK':
            return total_monthly

        rate = CurrencyConversionRate.get_rate_to_nok(currency)
        if rate is None:
            return Decimal('0.00')
        return total_monthly * rate

    @property
    def total_yearly_commitment_nok(self):
        """Total yearly commitment converted to NOK"""
        return self.total_monthly_commitment_nok * 12

    def get_active_period(self):
        """Get the period covering today (if any)"""
        from django.db.models import Q
        today = timezone.now().date()
        # Period is active if: started and (not ended yet OR perpetual/null end date)
        return self.periods.filter(
            Q(period_start__lte=today) &
            (Q(period_end__gte=today) | Q(period_end__isnull=True))
        ).first()

    @property
    def is_active(self):
        """License is active if there's a period covering today"""
        return self.get_active_period() is not None

    @property
    def license_status(self):
        """
        Calculate license status based on periods.
        Returns: 'active', 'expiring_soon', 'inactive'
        """
        today = timezone.now().date()
        active_period = self.get_active_period()

        if not active_period:
            return 'inactive'

        days_remaining = active_period.days_remaining

        # Perpetual licenses are always just 'active'
        if days_remaining is None:
            return 'active'

        # Get thresholds from config
        try:
            from .models import PluginConfiguration
            config = PluginConfiguration.get_config()
            warning_days = config.renewal_warning_days
        except Exception:
            warning_days = 30  # Fallback

        if days_remaining <= warning_days:
            return 'expiring_soon'

        return 'active'

    @property
    def current_period_end(self):
        """End date of current active period (None if expired)"""
        period = self.get_active_period()
        return period.period_end if period else None

    @property
    def next_period_start(self):
        """When the next period should start (after current expires)"""
        current = self.get_active_period()
        if current:
            from datetime import timedelta
            return current.period_end + timedelta(days=1)

        # No active period - next should start today
        return timezone.now().date()

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

        # Note: Pricing is now handled by LicensePeriod model, not License

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
    assigned_object_id = models.PositiveIntegerField()
    assigned_object = GenericForeignKey("assigned_object_type", "assigned_object_id")

    start_date = models.DateField(default=timezone.now, help_text="When this user/device was assigned the license")
    end_date = models.DateField(null=True, blank=True, help_text="When this assignment ended (null = still active)")

    comments = models.TextField(blank=True)

    def __str__(self):
        return f"{self.license.name} (#{self.id})"

    @property
    def license_currency(self):
        """Returns the currency from the parent license's active period"""
        return self.license.active_period_currency

    @property
    def license_price(self):
        """Returns the per-seat price from the parent license's active period"""
        from decimal import Decimal
        return self.license.active_period_per_seat_price

    @property
    def instance_price_nok(self):
        """Returns the NOK price for this instance from the license"""
        from decimal import Decimal

        # If the license is already in NOK, use its price
        if self.license_currency == 'NOK':
            return self.license_price

        # Use database rates
        rate = CurrencyConversionRate.get_rate_to_nok(self.license_currency)
        if rate is None:
            return Decimal('0.0')
        return self.license_price * rate

    @property
    def display_price(self):
        """Returns a formatted price display string"""
        return f"{self.license_price} {self.license_currency}"

    @property
    def is_active(self):
        """Check if this assignment is currently active"""
        today = timezone.now().date()

        # Not started yet
        if self.start_date and self.start_date > today:
            return False

        # Already ended
        if self.end_date and self.end_date < today:
            return False

        # Active if started and not ended
        return True

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
        else:
            return str(self.assigned_object)

    @property
    def assigned_object_str(self):
        """Return string representation for sorting"""
        if not self.assigned_object:
            return "zzz_unassigned"  # Sort unassigned items to the bottom
        if self.assigned_object_type.model == 'service':
            return f"Service: {self.assigned_object.name}"
        else:
            return f"{self.assigned_object_type.model.title()}: {str(self.assigned_object)}"
    
    @property
    def assignment_type(self):
        """Return assignment type for filtering"""
        return self.assigned_object_type.model if self.assigned_object_type else None

    # ASSIGNMENT LIFECYCLE PROPERTIES
    @property
    def days_until_expiry(self):
        """Days until this assignment expires (None if no end date)"""
        if not self.end_date:
            return None

        today = timezone.now().date()
        return (self.end_date - today).days

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:licenseinstance', args=[self.pk])

    def clean(self):
        """Validate license instance data"""
        from django.core.exceptions import ValidationError
        super().clean()

        # Allow overallocation - just track it, don't block it
        # The license's get_availability_status() will show "overallocated"

    def save(self, *args, **kwargs):
        # Validate data before saving
        self.full_clean()

        super().save(*args, **kwargs)


# Phase 3: Business Logic & Integration Models

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


class CurrencyConversionRate(NetBoxModel):
    """
    Store currency conversion rates to NOK for license cost calculations.
    All currencies convert to NOK as the base currency.
    Supports both API-synced rates (Norges Bank) and manual overrides.
    """

    SOURCE_CHOICES = [
        ('api', 'Norges Bank API'),
        ('manual', 'Manual Entry'),
    ]

    currency_code = models.CharField(
        max_length=3,
        unique=True,
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )
    description = models.CharField(
        max_length=100,
        blank=True,
        help_text="Full currency name (e.g., 'United States Dollar', 'Euro')"
    )
    rate_to_nok = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Conversion rate: 1 [currency] = X NOK"
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='api',
        help_text="Source of this rate"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Last time this rate was updated"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this currency"
    )

    class Meta:
        ordering = ['currency_code']
        indexes = [
            models.Index(fields=['currency_code']),
            models.Index(fields=['source', '-last_updated']),
        ]

    def __str__(self):
        if self.description:
            return f"{self.currency_code} ({self.description}) → NOK: {float(self.rate_to_nok):.2f}"
        return f"{self.currency_code} → NOK: {float(self.rate_to_nok):.2f}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:currencyconversionrate', args=[self.pk])

    @classmethod
    def get_rate_to_nok(cls, currency_code, auto_sync=True):
        """
        Get conversion rate to NOK for the given currency.
        Auto-syncs stale API-sourced rates on-demand.

        Args:
            currency_code: Currency code (e.g., 'USD', 'EUR')
            auto_sync: If True, syncs stale API-sourced rates automatically

        Returns:
            Decimal rate to NOK, or None if currency not found
        """
        if currency_code == 'NOK':
            return Decimal('1.0')

        try:
            rate = cls.objects.get(currency_code=currency_code)

            # Auto-sync if stale and API-sourced
            if auto_sync and rate.source == 'api' and rate.is_stale:
                try:
                    from .services.currency_service import sync_currency_rate
                    sync_currency_rate(rate)
                except Exception:
                    # If sync fails, still return existing rate (graceful degradation)
                    pass

            return rate.rate_to_nok
        except cls.DoesNotExist:
            return None

    @classmethod
    def get_available_currencies(cls):
        """Get list of all available currency codes including NOK"""
        currencies = list(cls.objects.values_list('currency_code', flat=True))
        if 'NOK' not in currencies:
            currencies.insert(0, 'NOK')
        return currencies

    @property
    def is_stale(self):
        """Check if rate is older than configured stale threshold"""
        try:
            config = PluginConfiguration.get_config()
            stale_days = config.currency_stale_days
        except Exception:
            stale_days = 7  # Fallback default
        return (timezone.now() - self.last_updated).days > stale_days

    @property
    def can_sync(self):
        """Check if this currency can be synced (is from API source)"""
        return self.source == 'api'

    def clean(self):
        """Validate rate data"""
        from django.core.exceptions import ValidationError
        super().clean()

        if self.from_currency == self.to_currency:
            raise ValidationError("Source and target currency cannot be the same")

        if self.rate <= 0:
            raise ValidationError("Conversion rate must be greater than zero")


class PluginConfiguration(models.Model):
    """
    Singleton model for storing plugin configuration.
    Only one instance should exist.
    Internal model - not exposed via API.
    """
    # License utilization thresholds
    # Goal: 100% utilization is optimal
    utilization_excellent_threshold = models.IntegerField(
        default=90,
        help_text="Excellent utilization (green badge) - licenses are well utilized"
    )
    utilization_good_threshold = models.IntegerField(
        default=70,
        help_text="Good utilization (blue badge) - acceptable usage"
    )
    utilization_moderate_threshold = models.IntegerField(
        default=50,
        help_text="Moderate utilization (yellow badge) - approaching underutilization"
    )
    # Below moderate threshold = poor/underutilized (red badge)

    # Currency sync settings
    currency_sync_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic on-demand currency rate synchronization"
    )
    currency_stale_days = models.IntegerField(
        default=7,
        help_text="Days before a currency rate is considered stale and triggers auto-sync"
    )

    # Renewal warning settings
    renewal_warning_days = models.IntegerField(
        default=90,
        help_text="Days before expiry to show renewal warnings"
    )
    renewal_critical_days = models.IntegerField(
        default=30,
        help_text="Days before expiry to show critical renewal alerts"
    )

    # Dashboard display settings
    dashboard_expiring_soon_days = models.IntegerField(
        default=90,
        help_text="Show instances expiring within this many days on dashboard"
    )
    dashboard_recently_expired_days = models.IntegerField(
        default=30,
        help_text="Show instances expired within this many days on dashboard"
    )

    class Meta:
        verbose_name = "Plugin Configuration"
        verbose_name_plural = "Plugin Configuration"

    def __str__(self):
        return "License Management Configuration"

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:config')

    @classmethod
    def get_config(cls):
        """Get or create the singleton configuration instance"""
        config, created = cls.objects.get_or_create(pk=1)
        return config

    def clean(self):
        """Validate configuration values"""
        from django.core.exceptions import ValidationError
        super().clean()

        # Ensure thresholds are in valid ranges
        if not 0 <= self.utilization_excellent_threshold <= 100:
            raise ValidationError("Excellent threshold must be between 0 and 100")
        if not 0 <= self.utilization_good_threshold <= 100:
            raise ValidationError("Good threshold must be between 0 and 100")
        if not 0 <= self.utilization_moderate_threshold <= 100:
            raise ValidationError("Moderate threshold must be between 0 and 100")

        # Ensure thresholds are in descending order
        if self.utilization_excellent_threshold <= self.utilization_good_threshold:
            raise ValidationError("Excellent threshold must be higher than good threshold")
        if self.utilization_good_threshold <= self.utilization_moderate_threshold:
            raise ValidationError("Good threshold must be higher than moderate threshold")

        # Validate renewal days
        if self.renewal_critical_days > self.renewal_warning_days:
            raise ValidationError("Critical renewal warning must be less than warning days")


class LicensePeriod(NetBoxModel):
    """
    Tracks paid billing periods for licenses.
    Each period represents one paid/invoiced time span.
    Snapshot of license state during that period.
    Immutable once created - can only be deleted by admins.
    """
    license = models.ForeignKey(
        to='License',
        on_delete=models.CASCADE,
        related_name='periods',
        help_text="License this period belongs to"
    )

    # Period coverage dates
    period_start = models.DateField(
        help_text="When this paid period starts"
    )
    period_end = models.DateField(
        null=True,
        blank=True,
        help_text="When this paid period ends (leave blank for perpetual/free licenses)"
    )

    # Pricing configuration
    pricing_mode = models.CharField(
        max_length=20,
        choices=PricingModeChoices.CHOICES,
        default=PricingModeChoices.PER_SEAT,
        help_text="Whether price is total or per-seat"
    )

    # Native currency pricing (original/invoiced amount)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Native price for this period (as invoiced)"
    )
    currency = models.ForeignKey(
        to='CurrencyConversionRate',
        on_delete=models.PROTECT,
        related_name='license_periods',
        help_text="Native currency for this period",
        to_field='currency_code'
    )

    # NOK pricing (for internal cost tracking)
    price_nok = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price in NOK (auto-converted or manually set). Leave blank to auto-calculate."
    )
    conversion_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Conversion rate used (1 native currency = X NOK). Auto-filled if not set."
    )

    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethodChoices.CHOICES,
        help_text="How this period was paid (snapshot from license)"
    )
    seats_purchased = models.IntegerField(
        help_text="Total seats for this period (snapshot)"
    )
    seats_utilized = models.IntegerField(
        default=0,
        help_text="Seats in use when period was created (snapshot)"
    )

    # Invoice tracking (optional)
    invoice_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Invoice number or reference"
    )
    invoice_file = models.FileField(
        upload_to='license_invoices/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload invoice PDF or screenshot"
    )
    invoice_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Link to invoice in accounting system"
    )

    comments = models.TextField(blank=True)

    class Meta:
        ordering = ['-period_start']
        verbose_name = "License Period"
        verbose_name_plural = "License Periods"
        indexes = [
            models.Index(fields=['license', '-period_start']),
            models.Index(fields=['period_start', 'period_end']),
        ]

    def __str__(self):
        return self.name

    @property
    def name(self):
        """Generate a descriptive name for this period"""
        start = self.period_start.strftime('%d/%m/%Y')
        if self.period_end:
            end = self.period_end.strftime('%d/%m/%Y')
            return f"{self.license.name} ({start} - {end})"
        else:
            return f"{self.license.name} (from {start})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_licenses:licenseperiod', args=[self.pk])

    @property
    def current_seats_utilized(self):
        """
        Count instances that overlap with this period's date range.
        An instance overlaps if its date range intersects with the period.
        """
        if not self.license_id:
            return self.seats_utilized

        from django.db.models import Q
        from datetime import date

        # Get period end date (use far future for perpetual)
        period_end = self.period_end if self.period_end else date(9999, 12, 31)

        # Count instances where:
        # - instance starts before period ends AND
        # - instance ends after period starts (or is open-ended)
        overlapping_instances = self.license.instances.filter(
            Q(start_date__lt=period_end) &
            (Q(end_date__gte=self.period_start) | Q(end_date__isnull=True))
        ).count()

        return overlapping_instances

    @property
    def utilization_percentage(self):
        """Calculate utilization for this period (live for active, snapshot for expired)"""
        if self.seats_purchased == 0:
            return 0
        return (self.current_seats_utilized / self.seats_purchased) * 100

    @property
    def total_price(self):
        """Get total price for this period"""
        if self.pricing_mode == PricingModeChoices.TOTAL:
            return self.price
        else:  # PER_SEAT
            return self.price * self.seats_purchased

    @property
    def per_seat_price(self):
        """Get per-seat price for this period"""
        if self.pricing_mode == PricingModeChoices.PER_SEAT:
            return self.price
        else:  # TOTAL
            if self.seats_purchased == 0:
                return Decimal('0.00')
            return self.price / self.seats_purchased

    @property
    def per_seat_price_nok(self):
        """Get per-seat price in NOK"""
        if self.pricing_mode == PricingModeChoices.PER_SEAT:
            # price_nok already represents per-seat price
            return self.price_nok if self.price_nok else Decimal('0.00')
        else:  # TOTAL
            # price_nok is total, divide by seats to get per-seat
            if self.seats_purchased == 0:
                return Decimal('0.00')
            return self.price_nok / self.seats_purchased if self.price_nok else Decimal('0.00')

    @property
    def total_price_nok(self):
        """Get total price in NOK"""
        if not self.price_nok:
            return Decimal('0.00')

        if self.pricing_mode == PricingModeChoices.TOTAL:
            # price_nok already represents total price
            return self.price_nok
        else:  # PER_SEAT
            # price_nok is per-seat, multiply by seats to get total
            return self.price_nok * self.seats_purchased

    @property
    def is_active(self):
        """Check if this period covers today"""
        today = timezone.now().date()
        if self.period_end is None:
            # Perpetual license - active if started
            return self.period_start <= today
        return self.period_start <= today <= self.period_end

    @property
    def days_remaining(self):
        """Days until this period ends (negative if expired, None for perpetual)"""
        if self.period_end is None:
            return None  # Perpetual - never expires
        today = timezone.now().date()
        return (self.period_end - today).days

    def save(self, *args, **kwargs):
        """Enforce immutability for expired periods and auto-fill snapshot data"""
        # Only prevent editing expired periods (preserve historical accuracy)
        if self.pk and self.period_end and self.period_end < timezone.now().date():
            raise ValidationError(
                "Cannot edit expired periods to preserve historical accuracy. "
                "Create a new period or edit an active/future period instead."
            )

        # Auto-snapshot from license if creating new period
        if not self.pk and self.license_id:
            # Snapshot current consumption
            self.seats_utilized = self.license.consumed_licenses

            # Snapshot payment method if not set
            if not self.payment_method:
                self.payment_method = self.license.payment_method

        # Auto-calculate NOK price and conversion rate if not manually set
        if self.price and self.currency:
            if self.currency.currency_code == 'NOK':
                # Native currency is already NOK
                self.price_nok = self.price
                self.conversion_rate = Decimal('1.0')
            elif not self.price_nok:
                # Auto-convert to NOK using the currency's rate
                self.conversion_rate = self.currency.rate_to_nok
                self.price_nok = self.price * self.currency.rate_to_nok
            elif not self.conversion_rate and self.price_nok:
                # Manual NOK price set - calculate implied rate
                if self.price > 0:
                    self.conversion_rate = self.price_nok / self.price

        super().save(*args, **kwargs)

    def clean(self):
        """Validate period data"""
        from django.core.exceptions import ValidationError
        super().clean()

        # Validate period dates (only if period_end is set)
        if self.period_end and self.period_end <= self.period_start:
            raise ValidationError("Period end date must be after start date")

        # Check for overlapping periods for the same license
        if self.license_id:
            overlapping = LicensePeriod.objects.filter(license=self.license_id)

            # Exclude self if editing existing period
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            # Check for overlaps with simplified logic
            # Two periods overlap if one starts before the other ends
            # Allow adjacent periods where one ends the same day another starts
            for period in overlapping:
                # Get period end dates (use a far future date for perpetual periods)
                from datetime import date
                self_end = self.period_end if self.period_end else date(9999, 12, 31)
                period_end = period.period_end if period.period_end else date(9999, 12, 31)

                # Periods overlap if:
                # - self starts before period ends AND
                # - period starts before self ends AND
                # - they don't just touch (end_date == start_date is allowed)
                if (self.period_start < period_end and
                    period.period_start < self_end):
                    raise ValidationError(
                        f"Period overlaps with existing period: "
                        f"{period.period_start.strftime('%d/%m/%Y')} - "
                        f"{'Perpetual' if period.period_end is None else period.period_end.strftime('%d/%m/%Y')}. "
                        f"Periods can be adjacent (ending the same day another starts) but cannot overlap."
                    )

        # Validate seats
        if self.seats_purchased < 0:
            raise ValidationError("Seats purchased cannot be negative")
        if self.seats_utilized < 0:
            raise ValidationError("Seats utilized cannot be negative")
        if self.seats_utilized > self.seats_purchased:
            raise ValidationError("Seats utilized cannot exceed seats purchased")
