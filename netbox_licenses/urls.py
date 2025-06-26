from django.urls import path
from netbox.views.generic import ObjectChangeLogView
from . import models, views

urlpatterns = [
    # Licenses
    path('licenses/', views.LicenseListView.as_view(), name='license_list'),
    path('licenses/add/', views.LicenseAddView.as_view(), name='license_add'),
    path('licenses/<int:pk>/', views.LicenseView.as_view(), name='license'),
    path('licenses/<int:pk>/edit/', views.LicenseEditView.as_view(), name='license_edit'),
    path('licenses/<int:pk>/delete/', views.LicenseDeleteView.as_view(), name='license_delete'),
    path('licenses/<int:pk>/changelog', ObjectChangeLogView.as_view(), name='license_changelog', kwargs={
        'model': models.License
    }),

    # License Instances
    path('license-instances/', views.LicenseInstanceListView.as_view(), name='licenseinstance_list'),
    path('license-instances/add/', views.LicenseInstanceEditView.as_view(), name='licenseinstance_add'),
    path('license-instances/<int:pk>/', views.LicenseInstanceView.as_view(), name='licenseinstance'),
    path('license-instances/<int:pk>/edit/', views.LicenseInstanceEditView.as_view(), name='licenseinstance_edit'),
    path('license-instances/<int:pk>/delete/', views.LicenseInstanceDeleteView.as_view(), name='licenseinstance_delete'),
    path('license-instances/<int:pk>/changelog', ObjectChangeLogView.as_view(), name='licenseinstance_changelog', kwargs={
        'model': models.LicenseInstance
    }),
    path('license-instances/delete/', views.LicenseInstanceBulkDeleteView.as_view(), name="licenseinstance_bulk_delete"),

    path('ajax/assigned-object/', views.AssignedObjectFieldView.as_view(), name='assigned-object-field'),
]
