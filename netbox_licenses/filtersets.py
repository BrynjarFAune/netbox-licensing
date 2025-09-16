import django_filters
from django.db import models
from netbox.filtersets import NetBoxModelFilterSet
from netbox.forms import NetBoxModelFilterSetForm
from django import forms
from .models import LicenseInstance, License, LicenseStatusChoices
from tenancy.models import Contact
from dcim.models import Manufacturer


class LicenseFilterSet(NetBoxModelFilterSet):
    vendor = django_filters.ModelMultipleChoiceFilter(queryset=Manufacturer.objects.all())
    external_id = django_filters.CharFilter(lookup_expr='icontains')
    has_external_id = django_filters.BooleanFilter(method='filter_has_external_id')
    underutilized = django_filters.BooleanFilter(method='filter_underutilized')
    overallocated = django_filters.BooleanFilter(method='filter_overallocated')
    total_licenses__gte = django_filters.NumberFilter(field_name='total_licenses', lookup_expr='gte')
    consumed_licenses__gte = django_filters.NumberFilter(field_name='consumed_licenses', lookup_expr='gte')
    
    class Meta:
        model = License
        fields = ('id', 'name', 'vendor', 'external_id', 'total_licenses', 'consumed_licenses')
    
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


class LicenseInstanceFilterSet(NetBoxModelFilterSet):
    start_date__gte = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    end_date__lte = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')

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
        fields = ('id', 'license', 'start_date', 'end_date', 'start_date__gte', 'end_date__lte', 'derived_status', 'expiry_status')

    def search(self, queryset, name, value):
        return queryset.filter(description_icontains=value)

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
    start_date__gte = forms.DateField(
        required=False,
        label="Start date (after)",
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    end_date__lte = forms.DateField(
        required=False,
        label="End date (Before)",
        widget=forms.DateInput(attrs={'type': 'date'}),
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
    
    class Meta:
        model = License
        fields = []
