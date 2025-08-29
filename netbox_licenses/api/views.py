from netbox.api.viewsets import NetBoxModelViewSet
from django.db.models import Count
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response

from .. import filtersets, models
from .serializers import LicenseSerializer, LicenseInstanceSerializer

class LicenseViewSet(NetBoxModelViewSet):
    queryset = models.License.objects.prefetch_related(
        'tags', 'tenant', 'vendor'
    ).annotate(
        instance_count=Count('instances')
    ).order_by('name')
    serializer_class = LicenseSerializer

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError as e:
            if 'unique_license_key' in str(e):
                return Response(
                    {'error': 'A license with this name, vendor, and tenant already exists.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {'error': 'Database constraint violation. Please check your data.'},
                status=status.HTTP_400_BAD_REQUEST
            )

class LicenseInstanceViewSet(NetBoxModelViewSet):
    queryset = models.LicenseInstance.objects.prefetch_related(
        'license', 'assigned_object', 'tags'
    ).order_by('license__name', 'id')
    serializer_class = LicenseInstanceSerializer
    filterset_class = filtersets.LicenseInstanceFilterSet
