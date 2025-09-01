import django_filters
from django.db import models
from netbox.filtersets import NetBoxModelFilterSet
from netbox.forms import NetBoxModelFilterSetForm
from django import forms
from .models import LicenseInstance, License, LicenseStatusChoices
from tenancy.models import Contact
from dcim.models import Manufacturer


class LicenseFilterSet(NetBoxModelFilterSet):
    vendor = django_filters.ModelChoiceFilter(queryset=Manufacturer.objects.all())
    external_id = django_filters.CharFilter(lookup_expr='icontains')
    has_external_id = django_filters.BooleanFilter(method='filter_has_external_id')
    underutilized = django_filters.BooleanFilter(method='filter_underutilized')
    overallocated = django_filters.BooleanFilter(method='filter_overallocated')
    
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

    class Meta:
        model = LicenseInstance
        fields = ('id', 'license', 'start_date', 'end_date', 'start_date__gte', 'end_date__lte', 'derived_status')

    def search(self, queryset, name, value):
        return queryset.filter(description_icontains=value)

    def filter_derived_status(self, queryset, name, values):
        return queryset.filter(
            pk__in=[obj.pk for obj in queryset if obj.derived_status in values]
        )

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

    class Meta:
        model = LicenseInstance
        fields = []
