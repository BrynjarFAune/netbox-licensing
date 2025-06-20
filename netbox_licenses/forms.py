from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField
from django.forms import DateInput, NumberInput, IntegerField, DateField
from .models import License, LicenseInstance
from tenancy.models import Contact, Tenant
from dcim.models import Manufacturer

class LicenseForm(NetBoxModelForm):
    comments = CommentField()
    vendor = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=True
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=True
    )

    class Meta:
        model = License
        fields = ('name', 'vendor', 'tenant', 'price', 'comments', 'tags')

class LicenseAddForm(LicenseForm):
    quantity = IntegerField(
        required=False,
        label="Quantity",
        min_value=0,
        help_text="Number of instances to create"
    )

class LicenseInstanceForm(NetBoxModelForm):
    comments = CommentField()
    license = DynamicModelChoiceField(
        queryset=License.objects.all(),
        required=True
    )
    assigned_user = DynamicModelChoiceField(
        queryset=Contact.objects.all(),
        required=False
    )

    class Meta:
        model = LicenseInstance
        fields = ('license', 'assigned_user', 'price_override', 'start_date', 'end_date', 'comments', 'tags')
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
            'end_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'license' in self.fields:
            self.fields['license'].queryset = License.objects.all()
        if 'assigned_user' in self.fields:
            self.fields['assigned_user'].queryset = Contact.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data is None:
            return cleaned_data
        
        start = cleaned_data.get('start_date')
