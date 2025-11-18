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
import json
from django.utils import timezone
from datetime import timedelta
from dcim.models import Manufacturer


# Dashboard views
class LicenseDashboardView(View):
    """Operational dashboard for capacity planning and license allocation"""
    template_name = "netbox_licenses/dashboard.html"

    def get(self, request):
        from decimal import Decimal
        from netbox_licenses.models import CurrencyConversionRate, PluginConfiguration
        import json

        # Get configurable thresholds from database
        try:
            config = PluginConfiguration.get_config()
        except Exception:
            # Fallback to defaults if config doesn't exist
            config = PluginConfiguration()

        licenses = models.License.objects.prefetch_related('instances', 'vendor').all()
        today = timezone.now().date()

        # === UTILIZATION OVERVIEW ===
        total_licenses_count = 0
        total_utilized = 0

        for license in licenses:
            total_licenses_count += license.total_licenses
            total_utilized += license.consumed_licenses

        utilization_percent = (total_utilized / total_licenses_count * 100) if total_licenses_count > 0 else 0

        # === LICENSE CAPACITY CHART DATA (Top 15 by total seats) ===
        license_chart_data = []
        active_licenses_list = [l for l in licenses if l.is_active]

        # Sort by total seats and take top 15
        sorted_licenses = sorted(active_licenses_list, key=lambda x: x.total_licenses, reverse=True)[:15]

        for license in sorted_licenses:
            license_chart_data.append({
                'name': license.name,
                'used': license.consumed_licenses,
                'free': license.available_licenses,
                'total': license.total_licenses,
                'utilization': license.utilization_percentage
            })

        # === LICENSES WITH AVAILABLE CAPACITY ===
        available_capacity = []
        for license in licenses:
            if license.available_licenses > 0 and license.is_active:
                available_capacity.append({
                    'license': license,
                    'available_seats': license.available_licenses,
                    'utilization_percentage': license.utilization_percentage,
                    'payment_method': license.payment_method,
                })

        # Sort by available seats (most available first)
        available_capacity.sort(key=lambda x: x['available_seats'], reverse=True)
        top_available = available_capacity[:10]

        # === NEARLY FULL LICENSES (>90% utilized) ===
        nearly_full = []
        for license in licenses:
            if license.is_active and license.utilization_percentage >= 90 and license.available_licenses >= 0:
                nearly_full.append({
                    'license': license,
                    'available_seats': license.available_licenses,
                    'utilization_percentage': license.utilization_percentage,
                })

        # Sort by available seats (fewest first = most urgent)
        nearly_full.sort(key=lambda x: x['available_seats'])

        # === LICENSE STATUS (Period-based) ===
        active_licenses = []
        inactive_licenses = []

        for license in licenses:
            active_period = license.get_active_period()

            license_info = {
                'license': license,
                'available_seats': license.available_licenses,
                'utilization_percentage': license.utilization_percentage,
                'payment_method': license.payment_method,
                'current_period_end': license.current_period_end,
            }

            # Calculate days until period ends
            if active_period and active_period.period_end:
                license_info['days_remaining'] = active_period.days_remaining

            if license.is_active:
                active_licenses.append(license_info)
            else:
                inactive_licenses.append(license_info)

        # Sort active by utilization (lowest first = most capacity)
        active_licenses.sort(key=lambda x: x.get('utilization_percentage', 0))

        context = {
            # Overview metrics
            'total_licenses': total_licenses_count,
            'total_utilized': total_utilized,
            'total_available': total_licenses_count - total_utilized,
            'utilization_percent': utilization_percent,

            # Chart data
            'license_chart_data': license_chart_data,
            'license_chart_json': json.dumps(license_chart_data),

            # Capacity lists
            'top_available': top_available,
            'nearly_full': nearly_full,
            'active_licenses': active_licenses,
            'inactive_licenses': inactive_licenses,

            # Utilization thresholds for coloring
            'utilization_excellent': config.utilization_excellent_threshold,
            'utilization_good': config.utilization_good_threshold,
            'utilization_moderate': config.utilization_moderate_threshold,
        }

        return render(request, self.template_name, context)


class CostReportView(View):
    """Financial dashboard showing cost metrics, waste, and savings opportunities"""
    template_name = "netbox_licenses/cost_report.html"

    def get(self, request):
        from decimal import Decimal
        from netbox_licenses.models import CurrencyConversionRate, PluginConfiguration

        # Get configurable thresholds from database
        try:
            config = PluginConfiguration.get_config()
            expiring_soon_days = config.dashboard_expiring_soon_days
            recently_expired_days = config.dashboard_recently_expired_days
        except Exception:
            # Fallback to defaults if config doesn't exist
            expiring_soon_days = 90
            recently_expired_days = 30

        # Get all licenses with related data
        licenses = models.License.objects.prefetch_related('instances', 'vendor').all()
        instances = models.LicenseInstance.objects.select_related('license', 'license__vendor').all()
        today = timezone.now().date()

        # === HERO METRICS ===
        total_cost_nok = Decimal('0.00')
        unused_cost_nok = Decimal('0.00')
        total_licenses_count = 0
        total_utilized = 0

        for license in licenses:
            # Skip cost calculation for FREE_TRIAL licenses
            from .choices import PaymentMethodChoices
            if license.payment_method != PaymentMethodChoices.FREE_TRIAL:
                # Use active period pricing
                per_seat_price = Decimal(str(license.active_period_per_seat_price))
                currency = license.active_period_currency
                rate = CurrencyConversionRate.get_rate_to_nok(currency)
                if rate is None:
                    rate = Decimal('1.00')
                else:
                    rate = Decimal(str(rate))

                license_cost_nok = per_seat_price * rate * license.total_licenses
                total_cost_nok += license_cost_nok

                # Calculate unused cost
                unused = license.available_licenses
                if unused > 0:
                    unused_cost_nok += per_seat_price * rate * unused

            total_licenses_count += license.total_licenses
            total_utilized += license.consumed_licenses

        utilization_percent = (total_utilized / total_licenses_count * 100) if total_licenses_count > 0 else 0

        # === VENDOR COST DISTRIBUTION ===
        vendor_stats = []
        vendors = Manufacturer.objects.filter(licenses__isnull=False).distinct()

        for vendor in vendors:
            vendor_licenses = licenses.filter(vendor=vendor)
            vendor_total = 0
            vendor_consumed = 0
            vendor_cost_nok = Decimal('0.00')

            for license in vendor_licenses:
                vendor_total += license.total_licenses
                vendor_consumed += license.consumed_licenses

                # Skip cost calculation for FREE_TRIAL licenses
                from .choices import PaymentMethodChoices
                if license.payment_method != PaymentMethodChoices.FREE_TRIAL:
                    per_seat_price = Decimal(str(license.active_period_per_seat_price))
                    currency = license.active_period_currency
                    rate = CurrencyConversionRate.get_rate_to_nok(currency)
                    if rate is None:
                        rate = Decimal('1.00')
                    else:
                        rate = Decimal(str(rate))

                    vendor_cost_nok += per_seat_price * rate * license.total_licenses

            vendor_stats.append({
                'vendor': vendor.name,
                'vendor_id': vendor.id,
                'license_count': vendor_licenses.count(),
                'total_licenses': vendor_total,
                'consumed_licenses': vendor_consumed,
                'total_cost_nok': float(vendor_cost_nok),
                'utilization_percentage': (vendor_consumed / vendor_total * 100) if vendor_total > 0 else 0
            })

        # Sort by cost descending
        vendor_stats.sort(key=lambda x: x['total_cost_nok'], reverse=True)

        # Calculate percentages for pie chart
        for stat in vendor_stats:
            stat['cost_percentage'] = (stat['total_cost_nok'] / float(total_cost_nok) * 100) if total_cost_nok > 0 else 0

        # === TOP UNDERUTILIZED LICENSES ===
        underutilized = []
        for license in licenses:
            # Skip FREE_TRIAL and PREPAID licenses from underutilization tracking
            # (no ongoing cost savings opportunity)
            from .choices import PaymentMethodChoices
            if (license.payment_method not in [PaymentMethodChoices.FREE_TRIAL, PaymentMethodChoices.PREPAID]
                and license.available_licenses > 0 and license.total_licenses > 0):
                waste_pct = (license.available_licenses / license.total_licenses) * 100

                per_seat_price = Decimal(str(license.active_period_per_seat_price))
                currency = license.active_period_currency
                rate = CurrencyConversionRate.get_rate_to_nok(currency)
                if rate is None:
                    rate = Decimal('1.00')
                else:
                    rate = Decimal(str(rate))

                wasted_cost = per_seat_price * rate * license.available_licenses

                underutilized.append({
                    'license': license,
                    'waste_percentage': waste_pct,
                    'wasted_cost_nok': float(wasted_cost),
                    'unused_seats': license.available_licenses
                })

        # Top 5 worst offenders
        underutilized.sort(key=lambda x: x['wasted_cost_nok'], reverse=True)
        top_underutilized = underutilized[:5]

        # === LICENSE STATUS (Period-based) ===
        # Licenses that need action based on their period status
        licenses_needing_action = []
        active_licenses = []

        for license in licenses:
            active_period = license.get_active_period()

            license_info = {
                'license': license,
                'active_period': active_period,
                'is_active': license.is_active,
                'status': license.license_status,
                'available_seats': license.available_licenses,
                'responsible_contact': license.responsible_contact,
                'current_period_end': license.current_period_end,
                'payment_method': license.payment_method,
                'utilization_percentage': license.utilization_percentage,
            }

            # Calculate days until action needed
            if active_period and active_period.period_end:
                days_remaining = active_period.days_remaining
                license_info['days_remaining'] = days_remaining

                # Check if action needed soon
                if 0 <= days_remaining <= expiring_soon_days:
                    license_info['action_reason'] = 'period_expiring'
                    licenses_needing_action.append(license_info)

            elif not active_period:
                # No active period - expired or never had one
                license_info['action_reason'] = 'no_active_period'
                license_info['days_remaining'] = None
                licenses_needing_action.append(license_info)

            # If no responsible contact, flag it
            if not license.responsible_contact:
                if license_info not in licenses_needing_action:
                    license_info['action_reason'] = 'no_responsible_contact'
                    licenses_needing_action.append(license_info)

            # Add to active list if currently active
            if license.is_active:
                active_licenses.append(license_info)

        # Sort by urgency
        licenses_needing_action.sort(key=lambda x: x.get('days_remaining', float('inf')) if x.get('days_remaining') is not None else float('inf'))
        active_licenses.sort(key=lambda x: x.get('days_remaining', float('inf')) if x.get('days_remaining') is not None else float('inf'))

        context = {
            # Hero metrics
            'total_cost_nok': float(total_cost_nok),
            'unused_cost_nok': float(unused_cost_nok),
            'total_licenses': total_licenses_count,
            'total_utilized': total_utilized,
            'utilization_percent': utilization_percent,

            # Vendor distribution
            'vendor_stats': vendor_stats,
            'vendor_stats_json': json.dumps([{
                'vendor': v['vendor'],
                'cost': v['total_cost_nok'],
                'percentage': v['cost_percentage']
            } for v in vendor_stats]),

            # Top underutilized
            'top_underutilized': top_underutilized,

            # Period-based license status
            'licenses_needing_action': licenses_needing_action,
            'active_licenses': active_licenses,
            'expiring_soon_days': expiring_soon_days,

            # Utilization thresholds for availability coloring
            'utilization_excellent': config.utilization_excellent_threshold,
            'utilization_good': config.utilization_good_threshold,
            'utilization_moderate': config.utilization_moderate_threshold,
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
        # Get active period for pricing context
        active_period = instance.get_active_period()

        # Get all periods for this license
        license_periods = models.LicensePeriod.objects.filter(license=instance).order_by('-period_start')

        return {
            'instance_count': instance.instances.count(),
            'active_period': active_period,
            # UTILIZATION CONTEXT
            'utilization_percentage': instance.utilization_percentage,
            'available_licenses': instance.available_licenses,
            'is_underutilized': instance.utilization_percentage < 80,
            'is_overallocated': instance.consumed_licenses > instance.total_licenses,
            "instance_table": tables.LicenseInstanceTable(
                instance.instances.all(),
                user=request.user
            ),
            'license_periods': license_periods,
            'license_periods_table': tables.LicensePeriodTable(license_periods)
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

    def get_return_url(self, request, obj):
        return obj.get_absolute_url()

class LicenseDeleteView(generic.ObjectDeleteView):
    queryset = models.License.objects.all()

class LicenseBulkDeleteView(generic.BulkDeleteView):
    queryset = models.License.objects.all()
    table = tables.LicenseTable


class LicenseBulkEditView(generic.BulkEditView):
    """Bulk edit view for licenses"""
    queryset = models.License.objects.all()
    filterset = filtersets.LicenseFilterSet
    table = tables.LicenseTable
    form = forms.LicenseBulkEditForm


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

    def get_return_url(self, request, obj):
        # Return to the license instance list by default
        return reverse('plugins:netbox_licenses:licenseinstance_list')

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
            assignment_type = license_obj.assignment_type
            model_class = assignment_type.model_class()
            model_name = assignment_type.model
            verbose_name = model_class._meta.verbose_name.title() if model_class else "Object"

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
        object_type_id = request.GET.get("assigned_object_type")

        if not license_id:
            return HttpResponseBadRequest("Missing license ID")

        try:
            license_obj = models.License.objects.select_related('assignment_type').get(pk=license_id)
        except models.License.DoesNotExist:
            return HttpResponseBadRequest("Invalid license ID")

        # Create a temporary instance to get the right form initialization
        temp_instance = models.LicenseInstance(license=license_obj)

        # Initialize form with the license and object type data
        form_data = {'license': license_obj.pk}
        if object_type_id:
            form_data['assigned_object_type'] = object_type_id

        form = forms.LicenseInstanceForm(
            data=form_data,
            instance=temp_instance
        )

        # Get the assignment type info - use selected type or first type
        selected_type = None
        if object_type_id:
            try:
                from django.contrib.contenttypes.models import ContentType
                selected_type = ContentType.objects.get(pk=object_type_id)
            except (ContentType.DoesNotExist, ValueError):
                pass

        if not selected_type:
            selected_type = license_obj.assignment_type

        if selected_type:
            model_class = selected_type.model_class()
            verbose_name = model_class._meta.verbose_name.title() if model_class else "Object"
            model_name = selected_type.model
        else:
            verbose_name = "Object"
            model_name = "object"

        return render(
            request,
            "netbox_licenses/assigned_object_field.html",
            {
                "form": form,
                "model_name": model_name,
                "verbose_name": verbose_name,
            },
        )

class LicenseInstanceBulkEditView(generic.BulkEditView):
    """Bulk edit view for license instances"""
    queryset = models.LicenseInstance.objects.all()
    filterset = filtersets.LicenseInstanceFilterSet
    table = tables.LicenseInstanceTable
    form = forms.LicenseInstanceBulkEditForm


class LicenseInstanceBulkDeleteView(generic.BulkDeleteView):
    queryset = models.LicenseInstance.objects.all()
    table = tables.LicenseInstanceTable


# License Renewal Views
class LicensePeriodListView(generic.ObjectListView):
    """List view for license periods"""
    queryset = models.LicensePeriod.objects.prefetch_related('license', 'license__vendor')
    table = tables.LicensePeriodTable
    filterset = filtersets.LicensePeriodFilterSet
    filterset_form = filtersets.LicensePeriodFilterForm


class LicensePeriodView(generic.ObjectView):
    """Detail view for a single license period"""
    queryset = models.LicensePeriod.objects.prefetch_related('license', 'license__vendor')


class LicensePeriodEditView(generic.ObjectEditView):
    """Edit view for license periods"""
    queryset = models.LicensePeriod.objects.all()
    form = forms.LicensePeriodForm
    template_name = 'netbox_licenses/licenseperiod_edit.html'

    def get_extra_context(self, request, instance):
        context = super().get_extra_context(request, instance)
        # Add existing currencies for autocomplete
        context['existing_currencies'] = models.CurrencyConversionRate.objects.all().order_by('currency_code')
        return context

    def alter_object(self, obj, request, args, kwargs):
        """Pre-populate license from URL parameter"""
        if not obj.pk and 'license' in request.GET:
            try:
                license_id = int(request.GET['license'])
                obj.license = models.License.objects.get(pk=license_id)
            except (ValueError, models.License.DoesNotExist):
                pass
        return obj

    def get_initial(self):
        """Pass license ID to form for auto-fill"""
        initial = super().get_initial()
        if 'license' in self.request.GET:
            try:
                initial['license'] = int(self.request.GET['license'])
            except (ValueError, TypeError):
                pass
        return initial

    def get_extra_context(self, request, instance):
        # Add context for immutability warning if editing existing period
        if instance.pk:
            messages.warning(
                request,
                "Warning: Periods are immutable after creation. "
                "Only admins can delete periods. Any edits will fail."
            )
        return {}


class LicensePeriodDeleteView(generic.ObjectDeleteView):
    """Delete view for license periods (admin only)"""
    queryset = models.LicensePeriod.objects.all()


class LicensePeriodBulkDeleteView(generic.BulkDeleteView):
    """Bulk delete view for license periods"""
    queryset = models.LicensePeriod.objects.all()
    table = tables.LicensePeriodTable


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
        
        # Calculate cost impact using active period pricing
        total_license_value = sum(float(license.active_period_total_price or 0) for license in licenses)
        potential_savings = sum(
            (license.total_licenses - license.consumed_licenses) * float(license.active_period_per_seat_price or 0)
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

            # Calculate based on total licensed capacity using active period pricing
            # This shows the full investment including unutilized slots
            license_per_seat_price = license.active_period_per_seat_price
            total_license_value = license_per_seat_price * license.total_licenses

            # Add to total system cost (full investment)
            license_cost = total_license_value

            # However, if there are instances with custom pricing, factor those in
            custom_pricing_adjustment = Decimal('0')
            for instance in license.instances.all():
                if instance.nok_price_override:
                    # Replace the base license price with custom price for this instance
                    custom_pricing_adjustment += Decimal(str(instance.nok_price_override)) - license_per_seat_price

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

            # Calculate full license investment using active period pricing
            license_per_seat_price = license.active_period_per_seat_price
            total_invested_value = license_per_seat_price * license.total_licenses

            # Calculate actual usage value (only consumed slots)
            actual_usage_value = Decimal('0')
            for instance in license.instances.all():
                instance_price = instance.nok_price_override or license_per_seat_price
                actual_usage_value += Decimal(str(instance_price))

            # Calculate wasted money (unutilized slots)
            unutilized_slots = license.total_licenses - consumed
            wasted_value = license_per_seat_price * unutilized_slots

            utilization_percentage = 0
            if license.total_licenses > 0:
                utilization_percentage = (consumed / license.total_licenses) * 100

            license_details.append({
                'id': license.id,
                'name': license.name,
                'vendor': license.vendor,
                'currency': license.active_period_currency,
                'price': license.active_period_per_seat_price,
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


# Import webhook views from webhooks.py
from .webhooks import VendorWebhookView, VendorSyncStatusView


class LicenseBulkAddInstancesView(View):
    """Step 1: Select quantity for bulk creation"""
    template_name = 'netbox_licenses/license_bulk_quantity_select.html'

    def get(self, request, pk):
        license = get_object_or_404(models.License, pk=pk)
        form = forms.QuantitySelectionForm(license=license)

        return render(request, self.template_name, {
            'license': license,
            'form': form,
        })

    def post(self, request, pk):
        license = get_object_or_404(models.License, pk=pk)
        form = forms.QuantitySelectionForm(license=license, data=request.POST)

        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            return redirect('plugins:netbox_licenses:license_bulk_add_instances_form',
                          pk=license.pk, quantity=quantity)

        return render(request, self.template_name, {
            'license': license,
            'form': form,
        })

class LicenseBulkAddInstancesFormView(View):
    """Step 2: Show form with static assignment fields"""
    template_name = 'netbox_licenses/license_bulk_add_instances_form.html'

    def get(self, request, pk, quantity):
        license = get_object_or_404(models.License, pk=pk)

        # Validate quantity
        if quantity > license.available_licenses:
            messages.error(request, f"Cannot create {quantity} instances. Only {license.available_licenses} slots available.")
            return redirect('plugins:netbox_licenses:license_bulk_add_instances', pk=license.pk)

        form = forms.BulkLicenseInstanceForm(license=license, quantity=quantity)

        return render(request, self.template_name, {
            'license': license,
            'form': form,
            'quantity': quantity,
        })

    def post(self, request, pk, quantity):
        license = get_object_or_404(models.License, pk=pk)
        form = forms.BulkLicenseInstanceForm(license=license, quantity=quantity, data=request.POST)

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
            'quantity': quantity,
        })


# Currency Conversion Rate Views
class CurrencyConversionRateListView(generic.ObjectListView):
    """List view for currency conversion rates"""
    queryset = models.CurrencyConversionRate.objects.all()
    table = tables.CurrencyConversionRateTable
    filterset = filtersets.CurrencyConversionRateFilterSet
    filterset_form = forms.CurrencyConversionRateFilterForm


class CurrencyConversionRateView(generic.ObjectView):
    """Detail view for a currency conversion rate"""
    queryset = models.CurrencyConversionRate.objects.all()


class CurrencyConversionRateEditView(generic.ObjectEditView):
    """Edit view for currency conversion rates (manual only)"""
    queryset = models.CurrencyConversionRate.objects.all()
    form = forms.CurrencyConversionRateManualForm


class CurrencyConversionRateAddAPIView(View):
    """Add currency by fetching from Norges Bank API"""

    def get(self, request):
        form = forms.CurrencyConversionRateAPIForm()
        return render(request, 'netbox_licenses/currencyconversionrate_add_api.html', {
            'form': form,
        })

    def post(self, request):
        import json
        from django.http import JsonResponse
        from netbox_licenses.services.currency_service import create_currency_from_api, NorgesBankAPIError
        from django.core.exceptions import ValidationError

        # Handle AJAX request from period form
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                currency_code = data.get('currency_code', '').upper()

                if not currency_code or len(currency_code) != 3:
                    return JsonResponse({'error': 'Invalid currency code'}, status=400)

                # Use the currency service function directly
                currency = create_currency_from_api(currency_code)
                return JsonResponse({
                    'success': True,
                    'currency_code': currency.currency_code,
                    'rate_to_nok': str(currency.rate_to_nok)
                })

            except ValidationError as e:
                return JsonResponse({'error': str(e)}, status=400)
            except NorgesBankAPIError as e:
                return JsonResponse({'error': str(e)}, status=400)
            except Exception as e:
                return JsonResponse({'error': f'Error: {str(e)}'}, status=500)

        # Handle regular form submission
        form = forms.CurrencyConversionRateAPIForm(request.POST)

        if form.is_valid():
            try:
                currency = form.save()
                messages.success(
                    request,
                    f"Successfully added {currency.currency_code} with rate {currency.rate_to_nok} NOK from Norges Bank API."
                )
                return redirect('plugins:netbox_licenses:currencyconversionrate', pk=currency.pk)
            except Exception as e:
                from netbox_licenses.services.currency_service import NorgesBankAPIError
                if isinstance(e, NorgesBankAPIError):
                    messages.error(request, f"API Error: {e}")
                else:
                    messages.error(request, f"Error: {e}")
                # Redirect back to currency list on error
                return redirect('plugins:netbox_licenses:currencyconversionrate_list')

        return render(request, 'netbox_licenses/currencyconversionrate_add_api.html', {
            'form': form,
        })


class CurrencyConversionRateDeleteView(generic.ObjectDeleteView):
    """Delete view for currency conversion rates"""
    queryset = models.CurrencyConversionRate.objects.all()


class CurrencyConversionRateBulkDeleteView(generic.BulkDeleteView):
    """Bulk delete view for currency conversion rates"""
    queryset = models.CurrencyConversionRate.objects.all()
    table = tables.CurrencyConversionRateTable


class CurrencyConversionRateSyncView(View):
    """Sync a single currency rate from Norges Bank API"""

    def post(self, request, pk):
        currency = get_object_or_404(models.CurrencyConversionRate, pk=pk)

        if currency.source != 'api':
            messages.warning(request, f"Cannot sync {currency.currency_code}: source is 'Manual Entry', not API.")
            return redirect('plugins:netbox_licenses:currencyconversionrate', pk=pk)

        try:
            from netbox_licenses.services.currency_service import sync_currency_rate
            sync_currency_rate(currency)
            messages.success(request, f"Successfully synced {currency.currency_code} rate: {currency.rate_to_nok} NOK")
        except Exception as e:
            messages.error(request, f"Failed to sync {currency.currency_code}: {e}")

        return redirect('plugins:netbox_licenses:currencyconversionrate', pk=pk)


class CurrencyConversionRateBulkSyncView(View):
    """Sync all API-sourced currency rates - no template needed, just execute and redirect"""

    def get(self, request):
        # Execute sync directly on GET (button click)
        try:
            from netbox_licenses.services.currency_service import sync_all_currency_rates
            results = sync_all_currency_rates()

            success_count = len(results['success'])
            failed_count = len(results['failed'])

            if success_count > 0:
                messages.success(request, f"Successfully synced {success_count} currency rate(s).")
            if failed_count > 0:
                failed_currencies = ', '.join([f['currency'] for f in results['failed']])
                messages.error(request, f"Failed to sync {failed_count} currency rate(s): {failed_currencies}")

            if success_count == 0 and failed_count == 0:
                messages.info(request, "No API-sourced currencies found to sync.")

        except Exception as e:
            messages.error(request, f"Error during bulk sync: {e}")

        return redirect('plugins:netbox_licenses:currencyconversionrate_list')


# Configuration views
class PluginConfigurationView(View):
    """View and edit plugin configuration"""

    def get(self, request):
        config = models.PluginConfiguration.get_config()
        form = forms.PluginConfigurationForm(instance=config)

        return render(request, 'netbox_licenses/config.html', {
            'config': config,
            'form': form,
        })

    def post(self, request):
        config = models.PluginConfiguration.get_config()
        form = forms.PluginConfigurationForm(request.POST, instance=config)

        if form.is_valid():
            form.save()
            messages.success(request, "Configuration updated successfully")
            return redirect('plugins:netbox_licenses:config')
        else:
            messages.error(request, "Error updating configuration. Please check the form.")

        return render(request, 'netbox_licenses/config.html', {
            'config': config,
            'form': form,
        })
