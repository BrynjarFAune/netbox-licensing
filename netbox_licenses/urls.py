from django.urls import path
from netbox.views.generic import ObjectChangeLogView
from . import models, views

urlpatterns = [
    # Dashboard
    path('', views.LicenseDashboardView.as_view(), name='dashboard'),

    # Licenses
    path('licenses/', views.LicenseListView.as_view(), name='license_list'),
    path('licenses/add/', views.LicenseAddView.as_view(), name='license_add'),
    path('licenses/<int:pk>/', views.LicenseView.as_view(), name='license'),
    path('licenses/<int:pk>/edit/', views.LicenseEditView.as_view(), name='license_edit'),
    path('licenses/<int:pk>/delete/', views.LicenseDeleteView.as_view(), name='license_delete'),
    path('licenses/<int:pk>/changelog', ObjectChangeLogView.as_view(), name='license_changelog', kwargs={
        'model': models.License
    }),
    path('licenses/<int:pk>/bulk-add-instances/', views.LicenseBulkAddInstancesView.as_view(), name='license_bulk_add_instances'),
    path('licenses/delete/', views.LicenseBulkDeleteView.as_view(), name='license_bulk_delete'),

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

    # Reporting views
    path('reports/utilization/', views.UtilizationReportView.as_view(), name='utilization_report'),
    path('reports/vendor-utilization/', views.VendorUtilizationView.as_view(), name='vendor_utilization'),
    
    # Phase 3: Advanced Analytics and Management Views
    path('analytics/', views.LicenseAnalyticsView.as_view(), name='license_analytics'),
    path('compliance/', views.ComplianceMonitoringView.as_view(), name='compliance_monitoring'),
    path('cost-allocation/', views.CostAllocationView.as_view(), name='cost_allocation'),
    path('assigned-object-costs/', views.AssignedObjectCostView.as_view(), name='assigned_object_costs'),
    path('renewals/', views.LicenseRenewalView.as_view(), name='license_renewals'),

    path('ajax/assigned-object/', views.AssignedObjectFieldView.as_view(), name='assigned-object-field'),
    
    # Phase 3: Vendor Integration Webhooks  
    path('webhooks/<slug:vendor_slug>/', views.VendorWebhookView.as_view(), name='vendor_webhook'),
    path('vendor-status/', views.VendorSyncStatusView.as_view(), name='vendor_sync_status'),
    path('vendor-status/<slug:vendor_slug>/', views.VendorSyncStatusView.as_view(), name='vendor_sync_status_detail'),
]
