from rest_framework import serializers

from django.contrib.contenttypes.models import ContentType
from netbox.api.serializers import NetBoxModelSerializer, WritableNestedSerializer
from tenancy.api.serializers import ContactSerializer, TenantSerializer
from dcim.api.serializers import ManufacturerSerializer
from ..models import License, LicenseInstance

class NestedLicenseSerializer(WritableNestedSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:license-detail'
    )

    class Meta:
        model = License
        fields = ('id', 'url', 'display', 'name', 'price', 'assignment_type')
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
    instance_count = serializers.IntegerField(read_only=True)

    vendor = ManufacturerSerializer(nested=True)
    tenant = TenantSerializer(nested=True)

    class Meta:
        model = License
        fields = (
            'id', 'url', 'display', 'name', 'vendor', 'tenant', 'assignment_type', 'price', 'comments', 'tags', 'custom_fields', 'created', 'last_updated', 'instance_count'
        )

class LicenseInstanceSerializer(NetBoxModelSerializer):
    url = serializers.HyperlinkedIdentityField(
        view_name='plugins-api:netbox_licenses-api:licenseinstance-detail'
    )

    assigned_object_type = serializers.PrimaryKeyRelatedField(
            queryset=ContentType.objects.filter(model__in=[
            "contact", "device", "virtualmachine", "tenant"
        ])
    )
    assigned_object_id = serializers.IntegerField()
    license = NestedLicenseSerializer()
    effective_price = serializers.SerializerMethodField()

    def get_effective_price(self, obj):
        return obj.effective_price

    class Meta:
        model = LicenseInstance
        fields = (
            'id', 'url', 'display', 'license',
            'assigned_object_type', 'assigned_object_id',
            'assigned_object', 'effective_price',
            'start_date', 'end_date', 'comments',
            'created', 'last_updated', 'custom_fields', 'tags'
        )

