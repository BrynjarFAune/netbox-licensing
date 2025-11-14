import django_filters
from django.db import models
from netbox.filtersets import NetBoxModelFilterSet
from netbox.forms import NetBoxModelFilterSetForm
from django import forms
from .models import LicenseInstance, License, LicensePeriod, LicenseStatusChoices, CurrencyConversionRate
from .choices import PaymentMethodChoices
from tenancy.models import Contact, Tenant
from dcim.models import Manufacturer


class LicenseFilterSet(NetBoxModelFilterSet):
    vendor = django_filters.ModelMultipleChoiceFilter(queryset=Manufacturer.objects.all())
    tenant = django_filters.ModelMultipleChoiceFilter(queryset=Tenant.objects.all())
    external_id = django_filters.CharFilter(lookup_expr='icontains')
    has_external_id = django_filters.BooleanFilter(method='filter_has_external_id')
    underutilized = django_filters.BooleanFilter(method='filter_underutilized')
    overallocated = django_filters.BooleanFilter(method='filter_overallocated')
    total_licenses__gte = django_filters.NumberFilter(field_name='total_licenses', lookup_expr='gte')
    consumed_licenses__gte = django_filters.NumberFilter(field_name='consumed_licenses', lookup_expr='gte')

    # New filters for payment method and responsibility
    payment_method = django_filters.MultipleChoiceFilter(
        choices=PaymentMethodChoices,
        label='Payment Method'
    )
    responsible_contact = django_filters.ModelMultipleChoiceFilter(
        queryset=Contact.objects.all(),
        label='Responsible Contact'
    )
    has_responsible_contact = django_filters.BooleanFilter(
        method='filter_has_responsible_contact',
        label='Has Responsible Contact'
    )

    # Period-based date filters
    active_from = django_filters.DateFilter(
        method='filter_active_from',
        label='Active From'
    )
    active_to = django_filters.DateFilter(
        method='filter_active_to',
        label='Active To'
    )
    license_status = django_filters.ChoiceFilter(
        choices=[
            ('active', 'Active'),
            ('expiring_soon', 'Expiring Soon'),
            ('inactive', 'Inactive'),
        ],
        method='filter_license_status',
        label='License Status'
    )

    class Meta:
        model = License
        fields = ('id', 'name', 'vendor', 'tenant', 'external_id', 'total_licenses',
                  'consumed_licenses', 'payment_method', 'responsible_contact',
                  'active_from', 'active_to', 'license_status')
    
    def filter_has_external_id(self, queryset, name, value):
        if value:
            return queryset.exclude(external_id__isnull=True).exclude(external_id='')
        return queryset.filter(models.Q(external_id__isnull=True) | models.Q(external_id=''))
    
    def filter_underutilized(self, queryset, name, value):
        if value:
            return queryset.filter(consumed_licenses__lt=models.F('total_licenses'))
        return queryset
    
    def filter_overallocated(self, queryset, name, value):
        if value:
            return queryset.filter(consumed_licenses__gt=models.F('total_licenses'))
        return queryset

    def filter_has_responsible_contact(self, queryset, name, value):
        if value:
            return queryset.filter(responsible_contact__isnull=False)
        return queryset.filter(responsible_contact__isnull=True)

    def filter_active_from(self, queryset, name, value):
        """Filter licenses active from this date onwards (period overlaps with value or later)"""
        return queryset.filter(
            models.Q(periods__period_end__gte=value) | models.Q(periods__period_end__isnull=True)
        ).distinct()

    def filter_active_to(self, queryset, name, value):
        """Filter licenses active up to this date (period overlaps with value or earlier)"""
        return queryset.filter(
            periods__period_start__lte=value
        ).distinct()

    def filter_license_status(self, queryset, name, value):
        """Filter licenses by their current status"""
        return queryset.filter(
            pk__in=[obj.pk for obj in queryset if obj.license_status == value]
        )


class LicenseInstanceFilterSet(NetBoxModelFilterSet):
    # Date range filters
    active_from = django_filters.DateFilter(
        method='filter_active_from',
        label='Active From'
    )
    active_to = django_filters.DateFilter(
        method='filter_active_to',
        label='Active To'
    )

    derived_status = django_filters.MultipleChoiceFilter(
        choices=LicenseStatusChoices,
        method='filter_derived_status',
        label='Status',
    )

    expiry_status = django_filters.ChoiceFilter(
        choices=[
            ('expired', 'Expired'),
            ('expiring_soon', 'Expiring Soon (≤30d)'),
            ('expiring_medium', 'Expiring (≤90d)'),
            ('healthy', 'Healthy (>90d)'),
            ('no_end_date', 'No End Date'),
        ],
        method='filter_expiry_status',
        label='Expiry Status',
    )

    class Meta:
        model = LicenseInstance
        fields = ('id', 'license', 'active_from', 'active_to', 'derived_status', 'expiry_status')

    def search(self, queryset, name, value):
        return queryset.filter(description_icontains=value)

    def filter_active_from(self, queryset, name, value):
        """Filter instances active from this date onwards"""
        return queryset.filter(
            models.Q(end_date__gte=value) | models.Q(end_date__isnull=True)
        )

    def filter_active_to(self, queryset, name, value):
        """Filter instances active up to this date"""
        return queryset.filter(start_date__lte=value)

    def filter_derived_status(self, queryset, name, values):
        return queryset.filter(
            pk__in=[obj.pk for obj in queryset if obj.derived_status in values]
        )

    def filter_expiry_status(self, queryset, name, value):
        from datetime import datetime, timedelta

        today = datetime.now().date()

        if value == 'expired':
            return queryset.filter(end_date__lt=today)
        elif value == 'expiring_soon':
            return queryset.filter(end_date__gte=today, end_date__lte=today + timedelta(days=30))
        elif value == 'expiring_medium':
            return queryset.filter(end_date__gt=today + timedelta(days=30), end_date__lte=today + timedelta(days=90))
        elif value == 'healthy':
            return queryset.filter(end_date__gt=today + timedelta(days=90))
        elif value == 'no_end_date':
            return queryset.filter(end_date__isnull=True)

        return queryset

class LicenseInstanceFilterForm(NetBoxModelFilterSetForm):
    model = LicenseInstance

    license = forms.ModelMultipleChoiceField(
        queryset=License.objects.all(),
        required=False
    )
    derived_status = forms.MultipleChoiceField(
        choices=LicenseStatusChoices,
        required=False,
        label="Status"
    )
    # Date range filters
    active_from = forms.DateField(
        required=False,
        label="Active From",
        help_text="Show instances active from this date onwards",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    active_to = forms.DateField(
        required=False,
        label="Active To",
        help_text="Show instances active up to this date",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    expiry_status = forms.ChoiceField(
        choices=[
            ('', '-------'),
            ('expired', 'Expired'),
            ('expiring_soon', 'Expiring Soon (≤30d)'),
            ('expiring_medium', 'Expiring (≤90d)'),
            ('healthy', 'Healthy (>90d)'),
            ('no_end_date', 'No End Date'),
        ],
        required=False,
        label="Expiry Status",
    )

    class Meta:
        model = LicenseInstance
        fields = []


class LicenseFilterForm(NetBoxModelFilterSetForm):
    model = License
    
    vendor = forms.ModelMultipleChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False
    )
    external_id = forms.CharField(
        required=False,
        label="External ID Contains",
        help_text="Search for licenses containing this external ID"
    )
    has_external_id = forms.NullBooleanField(
        required=False,
        label="Has External ID",
        help_text="Filter licenses with or without external IDs"
    )
    underutilized = forms.BooleanField(
        required=False,
        label="Underutilized",
        help_text="Show licenses with usage below total capacity"
    )
    overallocated = forms.BooleanField(
        required=False,
        label="Overallocated", 
        help_text="Show licenses with usage exceeding total capacity"
    )
    total_licenses__gte = forms.IntegerField(
        required=False,
        label="Min Total Licenses",
        help_text="Minimum number of total licenses"
    )
    consumed_licenses__gte = forms.IntegerField(
        required=False,
        label="Min Consumed Licenses",
        help_text="Minimum number of consumed licenses"
    )

    # Period-based date filters
    active_from = forms.DateField(
        required=False,
        label="Active From",
        help_text="Show licenses active from this date onwards",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    active_to = forms.DateField(
        required=False,
        label="Active To",
        help_text="Show licenses active up to this date",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    license_status = forms.ChoiceField(
        choices=[
            ('', '-------'),
            ('active', 'Active'),
            ('expiring_soon', 'Expiring Soon'),
            ('inactive', 'Inactive'),
        ],
        required=False,
        label="License Status",
        help_text="Filter by current license status"
    )

    class Meta:
        model = License


class LicensePeriodFilterSet(NetBoxModelFilterSet):
    """FilterSet for license periods"""

    license = django_filters.ModelMultipleChoiceFilter(
        queryset=License.objects.all(),
        label='License'
    )

    status = django_filters.ChoiceFilter(
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('pending', 'Pending'),
        ],
        method='filter_status',
        label='Period Status'
    )

    period_start = django_filters.DateFilter()
    period_start__gte = django_filters.DateFilter(
        field_name='period_start',
        lookup_expr='gte'
    )
    period_start__lte = django_filters.DateFilter(
        field_name='period_start',
        lookup_expr='lte'
    )
    period_end = django_filters.DateFilter()
    period_end__gte = django_filters.DateFilter(
        field_name='period_end',
        lookup_expr='gte'
    )
    period_end__lte = django_filters.DateFilter(
        field_name='period_end',
        lookup_expr='lte'
    )

    class Meta:
        model = LicensePeriod
        fields = ('id', 'license', 'period_start', 'period_end', 'status')

    def filter_status(self, queryset, name, value):
        """Filter periods by active/expired/pending status"""
        from django.utils import timezone
        today = timezone.now().date()

        if value == 'active':
            # Currently active: started but not ended
            return queryset.filter(period_start__lte=today).exclude(period_end__lt=today)
        elif value == 'expired':
            # Expired: period_end is in the past
            return queryset.filter(period_end__lt=today)
        elif value == 'pending':
            # Pending: period_start is in the future
            return queryset.filter(period_start__gt=today)

        return queryset


class CurrencyConversionRateFilterSet(NetBoxModelFilterSet):
    """FilterSet for currency conversion rates"""

    currency_code = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Currency Code'
    )
    source = django_filters.MultipleChoiceFilter(
        choices=CurrencyConversionRate.SOURCE_CHOICES
    )
    last_updated = django_filters.DateTimeFilter()
    last_updated__gte = django_filters.DateTimeFilter(
        field_name='last_updated',
        lookup_expr='gte'
    )
    last_updated__lte = django_filters.DateTimeFilter(
        field_name='last_updated',
        lookup_expr='lte'
    )

    class Meta:
        model = CurrencyConversionRate
        fields = []
