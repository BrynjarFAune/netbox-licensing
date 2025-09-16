from netbox.views import generic
from django.views import View
from django.shortcuts import render
from netbox.views import generic
from . import tables, filtersets, models, forms
from django.db.models import Count, Q, F, Sum
from django.contrib import messages
from django.http import HttpResponseBadRequest
from utilities.forms.fields import DynamicModelChoiceField
from django.utils import timezone
from datetime import timedelta
from dcim.models import Manufacturer


# Dashboard view
class LicenseDashboardView(View):
    """Comprehensive dashboard showing license overview with charts and statistics"""
    template_name = "netbox_licenses/dashboard.html"

    def get(self, request):
        # Get all licenses
        licenses = models.License.objects.all()
        instances = models.LicenseInstance.objects.all()

        # Calculate expiration status for pie chart
        today = timezone.now().date()
        expired = 0
        expiring_soon = 0  # Within 30 days
        expiring_medium = 0  # Within 90 days
        healthy = 0  # More than 90 days or no end date

        for instance in instances:
            if instance.end_date:
                days_until = (instance.end_date - today).days
                if days_until < 0:
                    expired += 1
                elif days_until <= 30:
                    expiring_soon += 1
                elif days_until <= 90:
                    expiring_medium += 1
                else:
                    healthy += 1
            else:
                healthy += 1  # No end date = healthy

        # Vendor summary statistics
        vendor_stats = []
        vendors = Manufacturer.objects.filter(licenses__isnull=False).distinct()

        for vendor in vendors:
            vendor_licenses = licenses.filter(vendor=vendor)
            total_licenses = sum(l.total_licenses for l in vendor_licenses)
            consumed_licenses = sum(l.consumed_licenses for l in vendor_licenses)
            available_licenses = total_licenses - consumed_licenses

            # Calculate total price in NOK
            total_price_nok = 0
            for license in vendor_licenses:
                if license.currency == 'NOK':
                    total_price_nok += float(license.price) * license.total_licenses
                else:
                    # For non-NOK, we need instance prices
                    for instance in license.instances.all():
                        if instance.nok_price_override:
                            total_price_nok += float(instance.nok_price_override)
                        elif license.currency == 'NOK':
                            total_price_nok += float(license.price)

            vendor_stats.append({
                'vendor': vendor.name,
                'vendor_id': vendor.id,
                'license_count': vendor_licenses.count(),
                'total_licenses': total_licenses,
                'consumed_licenses': consumed_licenses,
                'available_licenses': available_licenses,
                'total_price_nok': total_price_nok,
                'utilization_percentage': (consumed_licenses / total_licenses * 100) if total_licenses > 0 else 0
            })

        # Sort vendor stats by total licenses descending
        vendor_stats.sort(key=lambda x: x['total_licenses'], reverse=True)

        # Overall statistics
        total_licenses_count = sum(l.total_licenses for l in licenses)
        total_consumed = sum(l.consumed_licenses for l in licenses)
        total_available = total_licenses_count - total_consumed

        # Calculate total value in NOK
        total_value_nok = sum(stat['total_price_nok'] for stat in vendor_stats)

        context = {
            # Pie chart data for expiration status
            'expiration_chart_data': {
                'expired': expired,
                'expiring_soon': expiring_soon,
                'expiring_medium': expiring_medium,
                'healthy': healthy,
            },

            # Vendor statistics table
            'vendor_stats': vendor_stats,

            # Overall summary cards
            'summary': {
                'total_licenses': total_licenses_count,
                'total_consumed': total_consumed,
                'total_available': total_available,
                'total_value_nok': total_value_nok,
                'unique_vendors': len(vendor_stats),
                'unique_licenses': licenses.count(),
                'total_instances': instances.count(),
                'overall_utilization': (total_consumed / total_licenses_count * 100) if total_licenses_count > 0 else 0,
            }
        }

        return render(request, self.template_name, context)


# License views
class LicenseListView(generic.ObjectListView):
    queryset = models.License.objects.prefetch_related('vendor', 'tenant', 'instances')
    table = tables.LicenseTable
    filterset = filtersets.LicenseFilterSet
    filterset_form = filtersets.LicenseFilterForm

class LicenseView(generic.ObjectView):
    queryset = models.License.objects.prefetch_related('instances', 'instances__assigned_object')

    def get_extra_context(self, request, instance):
        return {
            'instance_count': instance.instances.count(),
            'total_cost': instance.total_cost,
            # NEW UTILIZATION CONTEXT
            'utilization_percentage': instance.utilization_percentage,
            'available_licenses': instance.available_licenses,
            'is_underutilized': instance.utilization_percentage < 80,
            'is_overallocated': instance.consumed_licenses > instance.total_licenses,
            "instance_table": tables.LicenseInstanceTable(
                instance.instances.all(),
                user=request.user
            )
        }

class LicenseAddView(generic.ObjectEditView):
    queryset = models.License.objects.all()
    form = forms.LicenseAddForm

    def form_valid(self, form):
        response = super().form_valid(form)
        quantity = form.cleaned_data.get("quantity") or 0
        if quantity > 0:
            messages.success(self.request, f"Creating {quantity} instances")
            models.LicenseInstance.objects.bulk_create([
                models.LicenseInstance(license=self.object) for _ in range(quantity)
            ])
        return response

class LicenseEditView(generic.ObjectEditView):
    queryset = models.License.objects.all()
    form = forms.LicenseForm

class LicenseDeleteView(generic.ObjectDeleteView):
    queryset = models.License.objects.all()

class LicenseBulkDeleteView(generic.BulkDeleteView):
    queryset = models.License.objects.all()
    table = tables.LicenseTable

# LicenseInstance views
class LicenseInstanceListView(generic.ObjectListView):
    queryset = models.LicenseInstance.objects.prefetch_related('license', 'assigned_object')
    table = tables.LicenseInstanceTable
    filterset = filtersets.LicenseInstanceFilterSet
    filterset_form = filtersets.LicenseInstanceFilterForm

class LicenseInstanceView(generic.ObjectView):
    queryset = models.LicenseInstance.objects.prefetch_related('license', 'assigned_object')

class LicenseInstanceEditView(generic.ObjectEditView):
    queryset = models.LicenseInstance.objects.all()
    form = forms.LicenseInstanceForm
    template_name = "netbox_licenses/licenseinstance_form.html"

    def get_form_kwargs(self):
        """Ensure form gets proper initial data"""
        kwargs = super().get_form_kwargs()

        # For new instances, check if license is provided in URL
        if not self.object or not self.object.pk:
            license_id = self.request.GET.get('license')
            if license_id:
                kwargs['initial'] = kwargs.get('initial', {})
                kwargs['initial']['license'] = license_id

        return kwargs

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)

        license_obj = None
        model_name = None
        verbose_name = None

        # Get license from various sources
        license_id = (
            request.POST.get("license") or 
            request.GET.get("license") or 
            getattr(instance, "license_id", None)
        )

        if license_id:
            try:
                license_obj = models.License.objects.get(pk=license_id)
            except models.License.DoesNotExist:
                pass

        if license_obj and license_obj.assignment_type:
            model_class = license_obj.assignment_type.model_class()
            model_name = license_obj.assignment_type.model
            verbose_name = model_class._meta.verbose_name.title()

        context.update({
            "license_obj": license_obj,
            "model_name": model_name,
            "verbose_name": verbose_name,
        })

        return context

class LicenseInstanceDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseInstance.objects.all()

class AssignedObjectFieldView(View):
    def get(self, request):
        license_id = request.GET.get("license")
        if not license_id:
            return HttpResponseBadRequest("Missing license ID")

        try:
            license_obj = models.License.objects.select_related('assignment_type').get(pk=license_id)
        except models.License.DoesNotExist:
            return HttpResponseBadRequest("Invalid license ID")

        # Create a temporary instance to get the right form initialization
        temp_instance = models.LicenseInstance(license=license_obj)

        # Initialize form with the license data
        form = forms.LicenseInstanceForm(
            data={'license': license_obj.pk},
            instance=temp_instance
        )

        # Get the assignment type info
        model_class = license_obj.assignment_type.model_class()
        verbose_name = model_class._meta.verbose_name.title() if model_class else "Object"

        return render(
            request,
            "netbox_licenses/assigned_object_field.html",
            {
                "form": form,
                "model_name": license_obj.assignment_type.model,
                "verbose_name": verbose_name,
            },
        )

class LicenseInstanceBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseInstance.objects.all()
    table = tables.LicenseInstanceTable

# Utilization Reporting Views
class UtilizationReportView(View):
    """Comprehensive utilization report for license optimization"""
    template_name = "netbox_licenses/utilization_report.html"
    
    def get(self, request):
        # Get all licenses with utilization metrics
        licenses = models.License.objects.prefetch_related('vendor', 'tenant', 'instances')
        
        # Calculate summary statistics
        total_licenses = licenses.count()
        underutilized = licenses.filter(consumed_licenses__lt=F('total_licenses')).count()
        overallocated = licenses.filter(consumed_licenses__gt=F('total_licenses')).count()
        fully_utilized = licenses.filter(consumed_licenses=F('total_licenses')).count()
        
        # Get top underutilized licenses (potential cost savings)
        top_underutilized = licenses.filter(
            consumed_licenses__lt=F('total_licenses'),
            total_licenses__gt=0
        ).extra(
            select={
                'waste_percentage': '(total_licenses - consumed_licenses) * 100.0 / total_licenses',
                'potential_savings': '(total_licenses - consumed_licenses) * price'
            }
        ).order_by('-waste_percentage')[:10]
        
        # Get overallocated licenses (compliance risks)
        overallocated_licenses = licenses.filter(
            consumed_licenses__gt=F('total_licenses')
        ).extra(
            select={'excess_percentage': '(consumed_licenses - total_licenses) * 100.0 / total_licenses'}
        ).order_by('-excess_percentage')
        
        # Calculate cost impact
        total_license_value = sum(license.total_cost or 0 for license in licenses)
        potential_savings = sum(
            (license.total_licenses - license.consumed_licenses) * (license.price or 0) 
            for license in top_underutilized
        )
        
        context = {
            'total_licenses': total_licenses,
            'underutilized_count': underutilized,
            'overallocated_count': overallocated,
            'fully_utilized_count': fully_utilized,
            'top_underutilized': top_underutilized,
            'overallocated_licenses': overallocated_licenses,
            'total_license_value': total_license_value,
            'potential_savings': potential_savings,
            'licenses_table': tables.LicenseTable(licenses, user=request.user),
        }
        
        return render(request, self.template_name, context)

class VendorUtilizationView(View):
    """Vendor-specific utilization analysis"""
    template_name = "netbox_licenses/vendor_utilization.html"
    
    def get(self, request):
        # Get vendor utilization statistics
        vendor_stats = []
        vendors = models.License.objects.values_list('vendor', flat=True).distinct()
        
        for vendor_id in vendors:
            if vendor_id:
                vendor_licenses = models.License.objects.filter(vendor_id=vendor_id)
                vendor_name = vendor_licenses.first().vendor.name if vendor_licenses.exists() else 'Unknown'
                
                total_licenses = sum(license.total_licenses for license in vendor_licenses)
                consumed_licenses = sum(license.consumed_licenses for license in vendor_licenses)
                utilization = (consumed_licenses / total_licenses * 100) if total_licenses > 0 else 0
                total_cost = sum(license.total_cost or 0 for license in vendor_licenses)
                
                vendor_stats.append({
                    'vendor_id': vendor_id,
                    'vendor_name': vendor_name,
                    'license_count': vendor_licenses.count(),
                    'total_licenses': total_licenses,
                    'consumed_licenses': consumed_licenses,
                    'utilization_percentage': utilization,
                    'total_cost': total_cost,
                    'available_licenses': total_licenses - consumed_licenses,
                })
        
        # Sort by utilization percentage
        vendor_stats.sort(key=lambda x: x['utilization_percentage'], reverse=True)
        
        context = {
            'vendor_stats': vendor_stats,
            'total_vendors': len(vendor_stats),
        }
        
        return render(request, self.template_name, context)


# Phase 3: Advanced Analytics and Trend Analysis Views
class LicenseAnalyticsView(View):
    """Advanced license analytics dashboard with trends"""
    template_name = "netbox_licenses/license_analytics.html"
    
    def get(self, request):
        from .services import AnalyticsService
        from datetime import timedelta
        
        # Get time range from query params (default: 30 days)
        days = int(request.GET.get('days', 30))
        
        licenses = models.License.objects.prefetch_related('analytics', 'vendor')
        analytics_data = []
        
        for license in licenses[:20]:  # Top 20 for performance
            trend_data = {
                'license': license,
                'utilization_trend': AnalyticsService.get_trend_analysis(license, 'utilization', days),
                'cost_trend': AnalyticsService.get_trend_analysis(license, 'cost', days),
                'efficiency_trend': AnalyticsService.get_trend_analysis(license, 'efficiency', days),
                'recent_metrics': license.analytics.filter(
                    timestamp__gte=timezone.now() - timedelta(days=days)
                )[:10]
            }
            analytics_data.append(trend_data)
        
        # Get optimization recommendations
        recommendations = AnalyticsService.get_cost_optimization_recommendations()
        
        context = {
            'analytics_data': analytics_data,
            'recommendations': recommendations[:10],  # Top 10
            'days_analyzed': days,
            'total_licenses': licenses.count(),
            'total_potential_savings': sum(r['potential_savings'] for r in recommendations),
        }
        
        return render(request, self.template_name, context)


class ComplianceMonitoringView(View):
    """Real-time compliance monitoring dashboard"""
    template_name = "netbox_licenses/compliance_monitoring.html"
    
    def get(self, request):
        from .models import LicenseAlert
        
        # Get active alerts by type and severity
        active_alerts = LicenseAlert.objects.filter(status='active').select_related('license', 'license__vendor')
        
        alert_summary = {
            'critical': active_alerts.filter(severity='critical').count(),
            'high': active_alerts.filter(severity='high').count(),
            'medium': active_alerts.filter(severity='medium').count(),
            'low': active_alerts.filter(severity='low').count(),
        }
        
        # Group alerts by type
        alerts_by_type = {}
        for alert_type, display_name in LicenseAlert.ALERT_TYPES:
            alerts_by_type[alert_type] = {
                'display_name': display_name,
                'count': active_alerts.filter(alert_type=alert_type).count(),
                'alerts': active_alerts.filter(alert_type=alert_type)[:5]  # Top 5 per type
            }
        
        # Get overallocated and underutilized licenses
        overallocated = models.License.objects.filter(
            consumed_licenses__gt=F('total_licenses')
        )
        
        underutilized = models.License.objects.filter(
            consumed_licenses__lt=F('total_licenses') * 70 / 100,
            total_licenses__gt=0
        )
        
        context = {
            'alert_summary': alert_summary,
            'alerts_by_type': alerts_by_type,
            'recent_alerts': active_alerts.order_by('-triggered_at')[:10],
            'overallocated_licenses': overallocated,
            'underutilized_licenses': underutilized,
            'total_active_alerts': active_alerts.count(),
        }
        
        return render(request, self.template_name, context)


class CostAllocationView(View):
    """Cost allocation and chargeback dashboard"""
    template_name = "netbox_licenses/cost_allocation.html"
    
    def get(self, request):
        from .models import CostAllocation
        from .services import CostAllocationService
        from datetime import date
        
        # Get current month or specified month
        month_str = request.GET.get('month')
        if month_str:
            year, month = map(int, month_str.split('-'))
            target_month = date(year, month, 1)
        else:
            target_month = timezone.now().date().replace(day=1)
        
        # Get all active cost allocations
        active_allocations = CostAllocation.objects.filter(
            effective_from__lte=target_month,
            effective_to__gte=target_month
        ).select_related('license', 'license__vendor')
        
        # Group by allocation target (department/project)
        allocation_summary = {}
        for allocation in active_allocations:
            target = allocation.allocation_target
            if target not in allocation_summary:
                allocation_summary[target] = {
                    'allocation_type': allocation.get_allocation_type_display(),
                    'total_cost': 0,
                    'licenses': [],
                    'allocation_count': 0
                }
            
            license_cost = (allocation.license.total_cost or 0) * (allocation.percentage / 100)
            allocation_summary[target]['total_cost'] += license_cost
            allocation_summary[target]['licenses'].append({
                'license': allocation.license,
                'percentage': allocation.percentage,
                'allocated_cost': license_cost
            })
            allocation_summary[target]['allocation_count'] += 1
        
        # Sort by total cost
        sorted_allocations = sorted(
            allocation_summary.items(),
            key=lambda x: x[1]['total_cost'],
            reverse=True
        )
        
        # Calculate totals
        total_allocated_cost = sum(item[1]['total_cost'] for item in sorted_allocations)
        total_licenses = models.License.objects.count()
        allocated_licenses = len(set(alloc.license for alloc in active_allocations))
        unallocated_licenses = total_licenses - allocated_licenses
        
        context = {
            'allocation_summary': sorted_allocations,
            'target_month': target_month,
            'total_allocated_cost': total_allocated_cost,
            'total_licenses': total_licenses,
            'allocated_licenses': allocated_licenses,
            'unallocated_licenses': unallocated_licenses,
            'recent_allocations': active_allocations.order_by('-created')[:10],
        }
        
        return render(request, self.template_name, context)


class LicenseRenewalView(View):
    """License renewal management dashboard"""
    template_name = "netbox_licenses/license_renewals.html"
    
    def get(self, request):
        from .models import LicenseRenewal
        
        renewals = LicenseRenewal.objects.select_related('license', 'license__vendor').all()
        
        # Group renewals by status
        renewals_by_status = {}
        for status, display_name in LicenseRenewal.RENEWAL_STATUS_CHOICES:
            renewals_by_status[status] = {
                'display_name': display_name,
                'renewals': renewals.filter(status=status).order_by('renewal_date'),
                'count': renewals.filter(status=status).count()
            }
        
        # Get upcoming renewals (next 60 days)
        upcoming_date = timezone.now().date() + timedelta(days=60)
        upcoming_renewals = renewals.filter(
            renewal_date__lte=upcoming_date,
            status__in=['pending', 'approved']
        ).order_by('renewal_date')
        
        # Get overdue renewals
        overdue_renewals = renewals.filter(
            renewal_date__lt=timezone.now().date(),
            status__in=['pending', 'approved']
        )
        
        # Calculate renewal costs
        total_pending_cost = sum(
            renewal.renewal_cost or 0 
            for renewal in renewals.filter(status='pending')
        )
        
        context = {
            'renewals_by_status': renewals_by_status,
            'upcoming_renewals': upcoming_renewals,
            'overdue_renewals': overdue_renewals,
            'total_pending_cost': total_pending_cost,
            'total_renewals': renewals.count(),
        }
        
        return render(request, self.template_name, context)


# Import webhook views from webhooks.py
from .webhooks import VendorWebhookView, VendorSyncStatusView
