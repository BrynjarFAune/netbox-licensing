from netbox.views import generic
from django.views import View
from django.shortcuts import render
from netbox.views import generic
from . import tables, filtersets, models, forms
from django.db.models import Count, Q, F
from django.contrib import messages
from django.http import HttpResponseBadRequest
from utilities.forms.fields import DynamicModelChoiceField


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
            select={'waste_percentage': '(total_licenses - consumed_licenses) * 100.0 / total_licenses'}
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
