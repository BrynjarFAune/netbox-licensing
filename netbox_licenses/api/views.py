from netbox.api.viewsets import NetBoxModelViewSet
from django.db.models import Count

from .. import filtersets, models
from .serializers import LicenseSerializer, LicenseInstanceSerializer

class LicenseViewSet(NetBoxModelViewSet):
    queryset = models.License.objects.prefetch_related(
        'tags', 'tenant', 'vendor'
    ).annotate(
        instance_count=Count('instances')
    ).order_by('name')
    serializer_class = LicenseSerializer

class LicenseInstanceViewSet(NetBoxModelViewSet):
    queryset = models.LicenseInstance.objects.prefetch_related(
        'license', 'assigned_object', 'tags'
    ).order_by('license__name', 'id')
    serializer_class = LicenseInstanceSerializer
    filterset_class = filtersets.LicenseInstanceFilterSet
