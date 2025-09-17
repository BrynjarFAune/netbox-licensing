from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField, ContentTypeChoiceField
from django.forms import DateInput, NumberInput, IntegerField, DateField, ModelChoiceField, HiddenInput, CharField, ChoiceField, DecimalField, Textarea, BooleanField
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from .models import License, LicenseInstance
from .choices import CurrencyChoices
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
    assignment_type = ModelChoiceField(
        queryset=ContentType.objects.filter(model__in=[
            "contact", "device", "virtualmachine", "tenant", "service"
        ]),
        required=True,
        label="Assignable Object Type"
    )
    currency = ChoiceField(
        choices=CurrencyChoices.CHOICES,
        initial=CurrencyChoices.NOK,
        required=True,
        help_text="Currency for the license price"
    )
    
    # NEW ENHANCEMENT FIELDS
    external_id = CharField(
        max_length=255,
        required=False,
        label="External ID",
        help_text="Vendor-specific identifier (SKU ID, subscription ID, license key, etc.)"
    )
    
    total_licenses = IntegerField(
        min_value=1,
        initial=1,
        label="Total Licenses",
        help_text="Total available license slots purchased"
    )
    
    metadata = CharField(
        required=False,
        widget=Textarea(attrs={'rows': 4, 'placeholder': 'Enter JSON metadata for vendor-specific data'}),
        help_text="Vendor-specific data in JSON format (service plans, features, API limits, etc.)"
    )

    class Meta:
        model = License
        fields = (
            'name', 'vendor', 'tenant', 'assignment_type', 'price', 'currency',
            'billing_cycle', 'auto_renew',
            'external_id', 'total_licenses', 'metadata',
            'comments', 'tags'
        )

    def clean_total_licenses(self):
        """Validate total_licenses cannot be reduced below consumed licenses"""
        total_licenses = self.cleaned_data.get('total_licenses')

        if self.instance and self.instance.pk:
            # Existing license - check consumed instances
            consumed = self.instance.instances.count()
            if total_licenses < consumed:
                raise ValidationError(
                    f"Cannot reduce total licenses to {total_licenses}. "
                    f"There are currently {consumed} licenses in use. "
                    f"Please remove {consumed - total_licenses} license instances first."
                )

        return total_licenses

class LicenseAddForm(LicenseForm):
    pass

class LicenseInstanceForm(NetBoxModelForm):
    comments = CommentField()
    license = DynamicModelChoiceField(
        queryset=License.objects.all(),
        required=True
    )

    # This is the field the user interacts with
    assigned_object_selector = DynamicModelChoiceField(
        queryset=Contact.objects.none(),  # Will be populated based on license
        required=True,
        label="Assigned Object",
        help_text="Select an object to assign this license to (required)"
    )

    # Simplified: Only NOK price for this instance
    nok_price_override = DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="Instance Price (NOK)",
        help_text="Override the price for this specific instance in Norwegian Kroner"
    )

    # Simple auto-renew checkbox
    auto_renew = BooleanField(
        required=False,
        label="Auto-Renew",
        help_text="Enable auto-renew for this license instance"
    )

    class Meta:
        model = LicenseInstance
        fields = (
            'license', 'assigned_object_selector',
            'nok_price_override', 'auto_renew',
            'start_date', 'end_date', 'comments', 'tags'
        )
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
            'end_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Mark license as required (it is required at the model level)
        self.fields['license'].required = True

        # Determine the license from various sources
        license_obj = self._get_license_object()

        if license_obj and license_obj.assignment_type:
            self._setup_assignment_fields(license_obj)
        else:
            # No license selected or license has no assignment type
            self.fields['assigned_object_selector'].widget.attrs['disabled'] = True
            self.fields['assigned_object_selector'].help_text = "Select a license first to choose an assigned object"

        # Add helpful display of license currency and price
        if license_obj:
            currency_display = dict(CurrencyChoices.CHOICES).get(license_obj.currency, license_obj.currency)
            self.fields['nok_price_override'].help_text = (
                f"License base price: {license_obj.price} {currency_display}. "
                f"Enter NOK price for this specific instance (leave blank to use default)."
            )

            # Show license default in help text and set checkbox to effective value
            auto_renew_default = "enabled" if license_obj.auto_renew else "disabled"
            self.fields['auto_renew'].help_text = (
                f"License default: <strong>{auto_renew_default}</strong>. "
                f"Check to enable auto-renew for this instance."
            )

            # Set checkbox to show the effective auto-renew value
            if self.instance and self.instance.pk:
                # For existing instances, show the actual effective value
                self.fields['auto_renew'].initial = self.instance.effective_auto_renew
            else:
                # For new instances, default to the license setting
                self.fields['auto_renew'].initial = license_obj.auto_renew
        else:
            # No license selected
            self.fields['auto_renew'].help_text = (
                "Select a license first to see its default auto-renew setting."
            )

    def _get_license_object(self):
        """Get the license object from form data, initial data, or existing instance"""
        license_id = None

        # Try to get license from form data (POST/GET)
        if hasattr(self, 'data') and self.data:
            license_id = self.data.get('license')

        # Try to get from initial data (URL parameters, etc.)
        if not license_id and self.initial:
            license_id = self.initial.get('license')

        # Try to get from existing instance
        if not license_id and self.instance and self.instance.pk and hasattr(self.instance, 'license'):
            license_id = self.instance.license.pk if self.instance.license else None

        if license_id:
            try:
                return License.objects.select_related('assignment_type').get(pk=license_id)
            except (License.DoesNotExist, ValueError):
                pass

        return None


    def _setup_assignment_fields(self, license_obj):
        """Setup the assignment fields based on the license's assignment type"""
        ct = license_obj.assignment_type
        model_class = ct.model_class()

        if not model_class:
            return

        # Update the selector field
        self.fields['assigned_object_selector'].queryset = model_class.objects.all()
        self.fields['assigned_object_selector'].label = f"Assigned {model_class._meta.verbose_name.title()}"

        # If editing an existing instance, populate the selector
        if (self.instance and self.instance.pk and 
            self.instance.assigned_object_type_id == ct.pk and 
                self.instance.assigned_object_id):
            try:
                assigned_obj = model_class.objects.get(pk=self.instance.assigned_object_id)
                self.fields['assigned_object_selector'].initial = assigned_obj.pk
            except model_class.DoesNotExist:
                # Object no longer exists, clear the assignment
                pass

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data:
            return cleaned_data

        license = cleaned_data.get('license')
        selector = cleaned_data.get('assigned_object_selector')

        if not license:
            # This should be caught by the required validation, but just in case
            return cleaned_data
        
        # Check license availability for new instances
        if not self.instance.pk:  # New instance
            current_instances = license.instances.count()
            available_licenses = license.total_licenses - current_instances
            
            if available_licenses <= 0:
                self.add_error('license', 
                    f"No available licenses. License has {license.total_licenses} total slots "
                    f"with {current_instances} already consumed.")

        # Validate that if a selector is provided, it matches the license's assignment type
        if selector:
            expected_ct = license.assignment_type
            actual_ct = ContentType.objects.get_for_model(selector)

            if expected_ct.pk != actual_ct.pk:
                self.add_error('assigned_object_selector', 
                               f"Selected object must be of type {expected_ct.model}, not {actual_ct.model}")

        # Validate NOK price override
        nok_price_override = cleaned_data.get('nok_price_override')

        if nok_price_override is not None and nok_price_override <= 0:
            self.add_error('nok_price_override',
                          'NOK price must be greater than 0')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set the assignment fields based on the form data
        if hasattr(self, 'cleaned_data'):
            license = self.cleaned_data.get('license')
            selector = self.cleaned_data.get('assigned_object_selector')

            if license:
                # Always set the content type from the license
                instance.assigned_object_type = license.assignment_type
                # Set the object ID from the selector (can be None)
                instance.assigned_object_id = selector.pk if selector else None

                # Handle auto_renew checkbox logic
                license_default = license.auto_renew
                form_value = self.cleaned_data.get('auto_renew', False)

                if form_value == license_default:
                    # User didn't override - use license default
                    instance.auto_renew = None
                else:
                    # User overrode the default
                    instance.auto_renew = form_value

        if commit:
            instance.save()
            self.save_m2m()

        return instance
