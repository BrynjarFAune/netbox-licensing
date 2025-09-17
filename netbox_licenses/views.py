from netbox.views import generic
from django.views import View
from django.shortcuts import render
from netbox.views import generic
from . import tables, filtersets, models, forms
from django.shortcuts import get_object_or_404, redirect
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

        # Calculate subscription commitments
        total_monthly_commitment = sum(l.total_monthly_commitment for l in licenses)
        total_yearly_commitment = sum(l.total_yearly_commitment for l in licenses)
        auto_renewing_licenses = licenses.filter(auto_renew=True)
        auto_renewing_monthly = sum(l.monthly_equivalent_price * l.total_licenses for l in auto_renewing_licenses)

        # Simple MRR tracking - Monthly Recurring Revenue
        current_mrr = sum(l.total_monthly_consumed_cost for l in auto_renewing_licenses)
        potential_mrr = sum(l.total_monthly_commitment for l in auto_renewing_licenses)
        manual_monthly_cost = sum(l.total_monthly_consumed_cost for l in licenses.filter(auto_renew=False))

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
                # NEW: Subscription commitments
                'total_monthly_commitment': total_monthly_commitment,
                'total_yearly_commitment': total_yearly_commitment,
                'auto_renewing_monthly': auto_renewing_monthly,
                'auto_renewing_count': auto_renewing_licenses.count(),
                'manual_renewal_count': licenses.filter(auto_renew=False).count(),
                # Simple MRR metrics
                'current_mrr': current_mrr,
                'potential_mrr': potential_mrr,
                'manual_monthly_cost': manual_monthly_cost,
                'mrr_utilization': (current_mrr / potential_mrr * 100) if potential_mrr > 0 else 0,
            }
        }

        return render(request, self.template_name, context)


# Assigned Object Cost Attribution View
class AssignedObjectCostView(View):
    """Show license costs attributed to specific objects (devices, contacts, etc.)"""
    template_name = "netbox_licenses/assigned_object_costs.html"

    def get(self, request):
        # Get all license instances grouped by assigned object
        instances = models.LicenseInstance.objects.select_related(
            'license', 'license__vendor', 'assigned_object_type'
        ).filter(assigned_object_id__isnull=False)

        # Group by content type and object
        object_costs = {}
        for instance in instances:
            content_type = instance.assigned_object_type
            object_id = instance.assigned_object_id

            if content_type.id not in object_costs:
                object_costs[content_type.id] = {
                    'content_type': content_type,
                    'objects': {}
                }

            if object_id not in object_costs[content_type.id]['objects']:
                # Get the actual object
                try:
                    obj = content_type.get_object_for_this_type(pk=object_id)
                    object_costs[content_type.id]['objects'][object_id] = {
                        'object': obj,
                        'instances': [],
                        'total_monthly_cost': 0,
                        'license_count': 0
                    }
                except:
                    continue  # Skip if object no longer exists

            obj_data = object_costs[content_type.id]['objects'][object_id]
            obj_data['instances'].append(instance)
            obj_data['license_count'] += 1

            # Calculate monthly cost for this instance
            monthly_cost = instance.license.monthly_equivalent_price
            if instance.nok_price_override:
                # Convert NOK price to monthly equivalent if needed
                if instance.license.billing_cycle == 'yearly':
                    monthly_cost = float(instance.nok_price_override) / 12
                elif instance.license.billing_cycle == 'quarterly':
                    monthly_cost = float(instance.nok_price_override) / 3
                else:
                    monthly_cost = float(instance.nok_price_override)

            obj_data['total_monthly_cost'] += monthly_cost

        # Convert to list and sort by cost
        cost_attribution = []
        for content_type_data in object_costs.values():
            for obj_data in content_type_data['objects'].values():
                cost_attribution.append({
                    'content_type': content_type_data['content_type'],
                    'object': obj_data['object'],
                    'license_count': obj_data['license_count'],
                    'total_monthly_cost': obj_data['total_monthly_cost'],
                    'total_yearly_cost': obj_data['total_monthly_cost'] * 12,
                    'instances': obj_data['instances']
                })

        # Sort by monthly cost descending
        cost_attribution.sort(key=lambda x: x['total_monthly_cost'], reverse=True)

        context = {
            'cost_attribution': cost_attribution,
            'summary': {
                'total_objects': len(cost_attribution),
                'total_monthly_cost': sum(x['total_monthly_cost'] for x in cost_attribution),
                'total_yearly_cost': sum(x['total_yearly_cost'] for x in cost_attribution),
                'total_licenses': sum(x['license_count'] for x in cost_attribution),
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
            select={
                'excess_percentage': '(consumed_licenses - total_licenses) * 100.0 / total_licenses',
                'excess_licenses': 'consumed_licenses - total_licenses'
            }
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
        from decimal import Decimal
        from collections import defaultdict

        # Get all licenses with their instances
        licenses = models.License.objects.select_related('vendor').prefetch_related('instances')
        all_instances = models.LicenseInstance.objects.select_related('license', 'license__vendor')

        # Calculate vendor costs
        vendor_stats = defaultdict(lambda: {
            'vendor_id': 0,
            'vendor_name': '',
            'license_count': 0,
            'instance_count': 0,
            'total_cost': Decimal('0'),
            'percentage': 0,
        })

        total_system_cost = Decimal('0')

        for license in licenses:
            vendor = license.vendor
            vendor_key = vendor.name if vendor else 'Unknown'

            # Calculate license cost - total potential value vs actual usage
            instance_count = license.instances.count()
            license_cost = Decimal('0')

            # Calculate based on total licensed capacity, not just used instances
            # This shows the full investment including unutilized slots
            license_price = license.price or Decimal('0')
            total_license_value = Decimal(str(license_price)) * license.total_licenses

            # Add to total system cost (full investment)
            license_cost = total_license_value

            # However, if there are instances with custom pricing, factor those in
            custom_pricing_adjustment = Decimal('0')
            for instance in license.instances.all():
                if instance.nok_price_override:
                    # Replace the base license price with custom price for this instance
                    custom_pricing_adjustment += Decimal(str(instance.nok_price_override)) - Decimal(str(license_price))

            license_cost += custom_pricing_adjustment

            # Update vendor stats
            vendor_stats[vendor_key]['vendor_id'] = vendor.id if vendor else 0
            vendor_stats[vendor_key]['vendor_name'] = vendor_key
            vendor_stats[vendor_key]['license_count'] += 1
            vendor_stats[vendor_key]['instance_count'] += instance_count
            vendor_stats[vendor_key]['total_cost'] += license_cost
            total_system_cost += license_cost

        # Calculate percentages
        for vendor_data in vendor_stats.values():
            if total_system_cost > 0:
                vendor_data['percentage'] = float((vendor_data['total_cost'] / total_system_cost) * 100)

        # Sort by total cost
        vendor_costs = sorted(vendor_stats.values(), key=lambda x: x['total_cost'], reverse=True)

        # Calculate license details with costs and utilization
        license_details = []
        for license in licenses:
            consumed = license.instances.count()

            # Calculate full license investment (all purchased slots)
            license_price = license.price or Decimal('0')
            total_invested_value = Decimal(str(license_price)) * license.total_licenses

            # Calculate actual usage value (only consumed slots)
            actual_usage_value = Decimal('0')
            for instance in license.instances.all():
                instance_price = instance.nok_price_override or license_price
                actual_usage_value += Decimal(str(instance_price))

            # Calculate wasted money (unutilized slots)
            unutilized_slots = license.total_licenses - consumed
            wasted_value = Decimal(str(license_price)) * unutilized_slots

            utilization_percentage = 0
            if license.total_licenses > 0:
                utilization_percentage = (consumed / license.total_licenses) * 100

            license_details.append({
                'id': license.id,
                'name': license.name,
                'vendor': license.vendor,
                'currency': license.currency,
                'price': license.price,
                'total_licenses': license.total_licenses,
                'consumed_licenses': consumed,
                'total_value_nok': total_invested_value,  # Full investment
                'actual_usage_value': actual_usage_value,  # Only used slots
                'wasted_value': wasted_value,  # Money wasted on unused slots
                'utilization_percentage': utilization_percentage,
            })

        # Sort by total value
        license_details.sort(key=lambda x: x['total_value_nok'], reverse=True)

        # Calculate summary
        active_instances = all_instances.count()
        avg_cost_per_instance = float(total_system_cost / active_instances) if active_instances > 0 else 0
        vendor_count = len([v for v in vendor_costs if v['total_cost'] > 0])

        summary = {
            'total_value_nok': float(total_system_cost),
            'active_instances': active_instances,
            'avg_cost_per_instance': avg_cost_per_instance,
            'vendor_count': vendor_count,
        }

        # Generate optimization recommendations
        optimization_recommendations = []
        underutilized = [l for l in license_details if l['utilization_percentage'] < 70]
        if underutilized:
            optimization_recommendations.append(
                f"Consider reducing or reassigning {len(underutilized)} underutilized licenses"
            )

        overallocated = [l for l in license_details if l['utilization_percentage'] > 100]
        if overallocated:
            optimization_recommendations.append(
                f"Purchase additional slots for {len(overallocated)} overallocated licenses"
            )

        context = {
            'vendor_costs': vendor_costs,
            'license_details': license_details,
            'summary': summary,
            'optimization_recommendations': optimization_recommendations,
        }

        return render(request, self.template_name, context)


class LicenseRenewalView(View):
    """License renewal management dashboard"""
    template_name = "netbox_licenses/license_renewals.html"

    def get(self, request):
        from datetime import datetime, timedelta

        # Get all instances with end dates
        instances_with_dates = models.LicenseInstance.objects.filter(
            end_date__isnull=False
        ).select_related('license', 'license__vendor').prefetch_related(
            'assigned_object_type', 'assigned_object'
        )

        today = datetime.now().date()

        # Separate auto-renew and manual renewal instances
        manual_renewal_instances = []
        auto_renewal_instances = []

        for instance in instances_with_dates:
            if instance.end_date:
                days_until = (instance.end_date - today).days
                instance.days_until_expiry = days_until
                instance.display_price_nok = instance.nok_price_override or instance.license.price or 0
            else:
                instance.days_until_expiry = None
                instance.display_price_nok = instance.license.price or 0

            # Separate based on effective auto-renew setting (instance override or license default)
            if instance.effective_auto_renew:
                auto_renewal_instances.append(instance)
            else:
                manual_renewal_instances.append(instance)

        # Sort both lists by expiry date (earliest first)
        manual_renewal_instances.sort(key=lambda x: x.end_date if x.end_date else datetime.max.date())
        auto_renewal_instances.sort(key=lambda x: x.end_date if x.end_date else datetime.max.date())

        # Calculate summary statistics for MANUAL renewals only
        manual_expired = sum(1 for i in manual_renewal_instances if i.days_until_expiry is not None and i.days_until_expiry < 0)
        manual_expiring_soon = sum(1 for i in manual_renewal_instances if i.days_until_expiry is not None and 0 <= i.days_until_expiry <= 30)
        manual_expiring_medium = sum(1 for i in manual_renewal_instances if i.days_until_expiry is not None and 31 <= i.days_until_expiry <= 90)

        # Calculate statistics for AUTO renewals (for informational purposes)
        auto_expired = sum(1 for i in auto_renewal_instances if i.days_until_expiry is not None and i.days_until_expiry < 0)
        auto_expiring_soon = sum(1 for i in auto_renewal_instances if i.days_until_expiry is not None and 0 <= i.days_until_expiry <= 30)
        auto_expiring_medium = sum(1 for i in auto_renewal_instances if i.days_until_expiry is not None and 31 <= i.days_until_expiry <= 90)

        # Calculate total renewal values (NOK)
        manual_renewal_value = sum(float(i.display_price_nok or 0) for i in manual_renewal_instances)
        auto_renewal_value = sum(float(i.display_price_nok or 0) for i in auto_renewal_instances)

        summary = {
            # Manual renewal stats (action required)
            'manual_expired': manual_expired,
            'manual_expiring_soon': manual_expiring_soon,
            'manual_expiring_medium': manual_expiring_medium,
            'manual_renewal_value': manual_renewal_value,
            'manual_total_count': len(manual_renewal_instances),

            # Auto renewal stats (informational)
            'auto_expired': auto_expired,
            'auto_expiring_soon': auto_expiring_soon,
            'auto_expiring_medium': auto_expiring_medium,
            'auto_renewal_value': auto_renewal_value,
            'auto_total_count': len(auto_renewal_instances),

            # Combined totals
            'total_instances': len(instances_with_dates),
            'total_renewal_value': manual_renewal_value + auto_renewal_value,
        }

        context = {
            'manual_renewal_instances': manual_renewal_instances,
            'auto_renewal_instances': auto_renewal_instances,
            'summary': summary,
        }

        return render(request, self.template_name, context)


# Import webhook views from webhooks.py
from .webhooks import VendorWebhookView, VendorSyncStatusView


class LicenseBulkAddInstancesView(View):
    """Bulk creation of license instances"""
    template_name = 'netbox_licenses/license_bulk_add_instances.html'

    def get(self, request, pk):
        license = get_object_or_404(models.License, pk=pk)
        form = forms.BulkLicenseInstanceForm(license=license)

        return render(request, self.template_name, {
            'license': license,
            'form': form,
        })

    def post(self, request, pk):
        license = get_object_or_404(models.License, pk=pk)
        form = forms.BulkLicenseInstanceForm(license=license, data=request.POST)

        if form.is_valid():
            try:
                instances = form.save()
                messages.success(
                    request,
                    f"Successfully created {len(instances)} license instances for {license.name}"
                )
                return redirect('plugins:netbox_licenses:license', pk=license.pk)
            except Exception as e:
                messages.error(request, f"Error creating instances: {str(e)}")

        return render(request, self.template_name, {
            'license': license,
            'form': form,
        })
