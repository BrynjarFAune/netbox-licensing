from netbox.views import generic
from . import tables, filtersets, models, forms
from django.db.models import Count
from django.contrib import messages


# License views
class LicenseListView(generic.ObjectListView):
    queryset = models.License.objects.prefetch_related('vendor', 'tenant', 'instances')
    table = tables.LicenseTable

class LicenseView(generic.ObjectView):
    queryset = models.License.objects.prefetch_related('instances', 'instances__assigned_user')

    def get_extra_context(self, request, instance):
        return {
            'instance_count': instance.instances.count(),
            'total_cost': instance.total_cost,
            "instance_table": tables.LicenseInstanceTable(
                instance.instances.all(),
                user=request.user
            )
        }

class LicenseAddView(generic.ObjectEditView):
    queryset = models.License.objects.all()
    form = forms.LicenseAddForm

    def form_valid(self, form):
        print(f"ALL FORM FIELDS: {list(form.fields.keys())}")  # See what fields exist
        print(f"FORM DATA: {form.data}")  # Raw form data
        messages.info(self.request, f"Form data: {form.cleaned_data}")
        response = super().form_valid(form)
        quantity = form.cleaned_data.get("quantity") or 0
        messages.info(self.request, f"Quantity: {quantity}")
        if quantity > 0:
            messages.success(self.request, f"Creating {quantity} instances")
            models.LicenseInstance.objects.bulk_create([
                models.LicenseInstance(license=self.object) for _ in range(quantity)
            ])
            print("Created instances")
        return response

class LicenseEditView(generic.ObjectEditView):
    queryset = models.License.objects.all()
    form = forms.LicenseForm


class LicenseDeleteView(generic.ObjectDeleteView):
    queryset = models.License.objects.all()


# LicenseInstance views
class LicenseInstanceListView(generic.ObjectListView):
    queryset = models.LicenseInstance.objects.prefetch_related('license', 'assigned_user')
    table = tables.LicenseInstanceTable
    filterset = filtersets.LicenseInstanceFilterSet
    filterset_form = filtersets.LicenseInstanceFilterForm


class LicenseInstanceView(generic.ObjectView):
    queryset = models.LicenseInstance.objects.prefetch_related('license', 'assigned_user')


class LicenseInstanceEditView(generic.ObjectEditView):
    queryset = models.LicenseInstance.objects.all()
    form = forms.LicenseInstanceForm

    def get_initial(self):
        initial = super().get_initial()
        license_id = self.request.GET.get("license")
        if license_id:
            try:
                initial["license"] = models.License.objects.get(pk=license_id)
            except models.License.DoesNotExist:
                pass
        return initial


class LicenseInstanceDeleteView(generic.ObjectDeleteView):
    queryset = models.LicenseInstance.objects.all()

