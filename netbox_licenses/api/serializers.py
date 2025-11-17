from rest_framework import serializers

from django.contrib.contenttypes.models import ContentType
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from tenancy.api.serializers import ContactSerializer, TenantSerializer
from dcim.api.serializers import ManufacturerSerializer
from ..models import License, LicenseInstance, LicensePeriod, CurrencyConversionRate

class NestedCurrencyConversionRateSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:currencyconversionrate-detail'
    )

    class Meta:
        model = CurrencyConversionRate
        fields = ('id', 'url', 'display', 'currency_code', 'rate_to_nok')
        brief_fields = ('id', 'url', 'display', 'currency_code')

class NestedLicenseSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:license-detail'
    )

    class Meta:
        model = License
        fields = ('id', 'url', 'display', 'name', 'assignment_types')
        brief_fields = ('id', 'url' ,'display', 'vendor')

class NestedLicenseInstanceSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseinstance-detail'
    )

    class Meta:
        model = LicenseInstance
        fields = ('id', 'url', 'display')
        brief_fields = ('id', 'url', 'display')

class LicenseSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:license-detail'
    )
    # Computed fields for utilization tracking
    available_licenses = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()
    instance_count = serializers.SerializerMethodField(read_only=True)
    is_active = serializers.ReadOnlyField()
    license_status = serializers.ReadOnlyField()

    # Nested serializers
    vendor = ManufacturerSerializer(nested=True)
    tenant = TenantSerializer(nested=True, allow_null=True, required=False)
    responsible_contact = ContactSerializer(nested=True, allow_null=True, required=False)

    # Computed period fields (from active period)
    active_period_per_seat_price = serializers.ReadOnlyField()
    active_period_total_price = serializers.ReadOnlyField()
    active_period_currency = serializers.ReadOnlyField()

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
            # Utilization fields
            'external_id', 'total_licenses', 'consumed_licenses', 'available_licenses',
            'utilization_percentage', 'metadata',
            # Lifecycle fields
            'billing_cycle', 'is_active', 'license_status',
            # Payment fields
            'payment_method', 'payment_portal_url', 'responsible_contact',
            # Active period pricing (computed)
            'active_period_per_seat_price', 'active_period_total_price', 'active_period_currency',
            # Standard fields
            'comments', 'tags', 'custom_fields', 'created', 'last_updated', 'instance_count'
        )

class LicenseInstanceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseinstance-detail'
    )

    # GenericForeignKey fields for assignment
    assigned_object_type = serializers.PrimaryKeyRelatedField(queryset=ContentType.objects.all())
    assigned_object_id = serializers.IntegerField(required=False, allow_null=True)
    assigned_object = serializers.SerializerMethodField(read_only=True)

    # Related objects
    license = NestedLicenseSerializer(nested=True)

    # Computed pricing fields (from model properties)
    license_price = serializers.ReadOnlyField()
    license_currency = serializers.ReadOnlyField()
    instance_price_nok = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    derived_status = serializers.ReadOnlyField()

    def get_assigned_object(self, obj):
        if obj.assigned_object:
            return {
                'type': obj.assigned_object_type.model,
                'id': obj.assigned_object_id,
                'display': str(obj.assigned_object)
            }
        return None

    class Meta:
        model = LicenseInstance
        fields = (
            'id', 'url', 'display',
            'license', 'assigned_object_type', 'assigned_object_id', 'assigned_object',
            'start_date', 'end_date', 'is_active', 'derived_status',
            'license_price', 'license_currency', 'instance_price_nok',
            'comments', 'tags', 'custom_fields', 'created', 'last_updated'
        )


class LicensePeriodSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseperiod-detail'
    )

    license = serializers.PrimaryKeyRelatedField(queryset=License.objects.all())

    # Accept currency_code string for writes, return nested object for reads
    currency = serializers.SlugRelatedField(
        slug_field='currency_code',
        queryset=CurrencyConversionRate.objects.all()
    )

    # Computed fields
    is_active = serializers.ReadOnlyField()
    days_remaining = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()
    current_seats_utilized = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    per_seat_price = serializers.ReadOnlyField()

    class Meta:
        model = LicensePeriod
        fields = (
            'id', 'url', 'display', 'license',
            'period_start', 'period_end',
            'pricing_mode', 'price', 'currency', 'price_nok', 'conversion_rate',
            'payment_method', 'seats_purchased', 'seats_utilized', 'current_seats_utilized',
            'total_price', 'per_seat_price',
            'invoice_reference', 'invoice_url', 'invoice_file',
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

