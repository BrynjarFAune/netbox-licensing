from rest_framework import serializers

from django.contrib.contenttypes.models import ContentType
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from tenancy.api.serializers import ContactSerializer, TenantSerializer
from dcim.api.serializers import ManufacturerSerializer
from ..models import License, LicenseInstance, LicensePeriod, CurrencyConversionRate

class NestedLicenseSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:license-detail'
    )

    class Meta:
        model = License
        fields = ('id', 'url', 'display', 'name', 'price', 'assignment_types')
        brief_fields = ('id', 'url' ,'display', 'vendor', 'price')

class NestedLicenseInstanceSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseinstance-detail'
    )

    class Meta:
        model = LicenseInstance
        fields = ('id', 'url', 'display', 'name', 'effective_price')
        brief_fields = ('id', 'url', 'display', 'license', 'assigned_object')

class LicenseSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:license-detail'
    )
    # Computed fields for utilization tracking
    available_licenses = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()
    instance_count = serializers.SerializerMethodField(read_only=True)

    vendor = ManufacturerSerializer(nested=True)
    tenant = TenantSerializer(nested=True)

    def get_instance_count(self, obj):
        return obj.instances.count()

    def validate_total_licenses(self, value):
        """Validate total_licenses cannot be reduced below consumed licenses"""
        if self.instance and self.instance.pk:
            consumed = self.instance.instances.count()
            if value < consumed:
                raise serializers.ValidationError(
                    f"Cannot reduce total licenses to {value}. "
                    f"There are currently {consumed} licenses in use. "
                    f"Please remove {consumed - value} license instances first."
                )
        return value

    class Meta:
        model = License
        fields = (
            'id', 'url', 'display', 'name', 'vendor', 'tenant', 'assignment_types',
            'price', 'currency', 'price_display',
            # NEW ENHANCEMENT FIELDS
            'external_id', 'total_licenses', 'consumed_licenses', 'available_licenses',
            'utilization_percentage', 'metadata',
            # EXISTING FIELDS
            'comments', 'tags', 'custom_fields', 'created', 'last_updated', 'instance_count'
        )

class LicenseInstanceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseinstance-detail'
    )

    assigned_object_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all())
    assigned_object_id = serializers.IntegerField(required=False, allow_null=True)
    license = serializers.PrimaryKeyRelatedField(queryset=License.objects.all())
    effective_price = serializers.SerializerMethodField(read_only=True)
    effective_currency = serializers.SerializerMethodField(read_only=True)
    price_in_nok = serializers.SerializerMethodField(read_only=True)
    conversion_rate_to_nok = serializers.SerializerMethodField(read_only=True)

    def get_effective_price(self, obj):
        try:
            return float(obj.instance_price_nok)
        except (ValueError, TypeError, AttributeError):
            return 0.0
    
    def get_effective_currency(self, obj):
        try:
            return obj.license.currency
        except (AttributeError):
            return 'NOK'

    def get_price_in_nok(self, obj):
        try:
            return float(obj.instance_price_nok)
        except (ValueError, TypeError, AttributeError):
            return 0.0

    def get_conversion_rate_to_nok(self, obj):
        # Return 1.0 as we don't have conversion rate tracking
        return 1.0

    class Meta:
        model = LicenseInstance
        fields = (
            'id', 'url', 'display_url', 'display', 'assigned_object_type', 'assigned_object_id', 'license',
            'effective_price', 'effective_currency', 'price_in_nok', 'conversion_rate_to_nok',
            'start_date', 'end_date', 'comments', 'tags',
            'custom_fields', 'created', 'last_updated', 'custom_field_data'
        )


class LicensePeriodSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseperiod-detail'
    )

    license = serializers.PrimaryKeyRelatedField(queryset=License.objects.all())

    # Computed fields
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()

    class Meta:
        model = LicensePeriod
        fields = (
            'id', 'url', 'display', 'license',
            'period_start', 'period_end',
            'price', 'currency', 'payment_method',
            'seats_purchased', 'seats_utilized',
            'invoice_reference', 'invoice_url',
            'is_active', 'days_remaining', 'utilization_percentage',
            'comments', 'tags', 'custom_fields', 'created', 'last_updated'
        )


class CurrencyConversionRateSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:currencyconversionrate-detail'
    )

    # Computed fields
    is_stale = serializers.ReadOnlyField()
    can_sync = serializers.ReadOnlyField()

    class Meta:
        model = CurrencyConversionRate
        fields = (
            'id', 'url', 'display', 'currency_code', 'rate_to_nok',
            'source', 'last_updated', 'notes', 'is_stale', 'can_sync',
            'tags', 'custom_fields', 'created'
        )

