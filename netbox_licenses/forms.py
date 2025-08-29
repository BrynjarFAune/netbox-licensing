from netbox.forms import NetBoxModelForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField, ContentTypeChoiceField
from django.forms import DateInput, NumberInput, IntegerField, DateField, ModelChoiceField, HiddenInput, CharField, ChoiceField, DecimalField
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

    class Meta:
        model = License
        fields = ('name', 'vendor', 'tenant', 'assignment_type', 'price', 'currency', 'comments', 'tags')

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

    # This is the field the user interacts with
    assigned_object_selector = DynamicModelChoiceField(
        queryset=Contact.objects.none(),  # Will be populated based on license
        required=False,
        label="Assigned Object",
        help_text="Select an object to assign this license to"
    )
    
    # Currency override fields
    currency_override = ChoiceField(
        choices=[('', 'Use License Currency')] + CurrencyChoices.CHOICES,
        required=False,
        label="Currency Override",
        help_text="Override the currency for this instance"
    )
    
    # Input mode selection
    price_input_mode = ChoiceField(
        choices=[
            ('conversion_rate', 'Enter Conversion Rate'),
            ('nok_price', 'Enter NOK Price Directly')
        ],
        initial='conversion_rate',
        required=False,
        label="Price Input Mode",
        help_text="Choose how to specify the currency conversion"
    )
    
    conversion_rate_to_nok = DecimalField(
        max_digits=10,
        decimal_places=6,
        required=False,
        label="Conversion Rate to NOK",
        help_text="Exchange rate to convert from selected currency to NOK"
    )
    
    nok_price_direct = DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label="Price in NOK",
        help_text="Direct price in Norwegian Kroner"
    )

    class Meta:
        model = LicenseInstance
        fields = (
            'license', 'assigned_object_selector',
            'price_override', 'currency_override', 'price_input_mode', 'conversion_rate_to_nok', 'nok_price_direct',
            'start_date', 'end_date', 'comments', 'tags'
        )
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
            'end_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Determine the license from various sources
        license_obj = self._get_license_object()

        if license_obj and license_obj.assignment_type:
            self._setup_assignment_fields(license_obj)
        else:
            # No license selected or license has no assignment type
            self.fields['assigned_object_selector'].widget.attrs['disabled'] = True
            self.fields['assigned_object_selector'].help_text = "Select a license first to choose an assigned object"
        
        # Setup currency conversion fields
        self._setup_currency_fields()
        
        # Add JavaScript classes for currency conversion
        self.fields['currency_override'].widget.attrs.update({
            'class': 'currency-selector'
        })
        self.fields['price_input_mode'].widget.attrs.update({
            'class': 'price-input-mode-selector'
        })
        self.fields['price_override'].widget.attrs.update({
            'class': 'price-field',
            'step': '0.01'
        })
        self.fields['conversion_rate_to_nok'].widget.attrs.update({
            'class': 'conversion-rate-field',
            'step': '0.000001'
        })
        self.fields['nok_price_direct'].widget.attrs.update({
            'class': 'nok-price-field',
            'step': '0.01'
        })

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

    def _setup_currency_fields(self):
        """Setup currency conversion fields based on existing instance"""
        if self.instance and self.instance.pk:
            # Populate currency override fields for existing instances
            if self.instance.currency_override:
                self.fields['currency_override'].initial = self.instance.currency_override
            if self.instance.conversion_rate_to_nok:
                self.fields['conversion_rate_to_nok'].initial = self.instance.conversion_rate_to_nok
                self.fields['price_input_mode'].initial = 'conversion_rate'
            else:
                # If no conversion rate, assume NOK direct input
                self.fields['price_input_mode'].initial = 'nok_price'
                self.fields['nok_price_direct'].initial = self.instance.price_in_nok

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data:
            return cleaned_data

        license = cleaned_data.get('license')
        selector = cleaned_data.get('assigned_object_selector')

        if not license:
            # This should be caught by the required validation, but just in case
            return cleaned_data

        # Validate that if a selector is provided, it matches the license's assignment type
        if selector:
            expected_ct = license.assignment_type
            actual_ct = ContentType.objects.get_for_model(selector)

            if expected_ct.pk != actual_ct.pk:
                self.add_error('assigned_object_selector', 
                               f"Selected object must be of type {expected_ct.model}, not {actual_ct.model}")

        # Validate currency conversion fields
        currency_override = cleaned_data.get('currency_override')
        conversion_rate = cleaned_data.get('conversion_rate_to_nok')
        nok_price_direct = cleaned_data.get('nok_price_direct')
        price_input_mode = cleaned_data.get('price_input_mode')
        price_override = cleaned_data.get('price_override')
        
        if currency_override and currency_override != CurrencyChoices.NOK:
            if price_input_mode == 'conversion_rate':
                if not conversion_rate:
                    self.add_error('conversion_rate_to_nok', 
                                  'Conversion rate is required when using conversion rate mode')
                elif conversion_rate <= 0:
                    self.add_error('conversion_rate_to_nok', 
                                  'Conversion rate must be greater than 0')
            elif price_input_mode == 'nok_price':
                if not nok_price_direct:
                    self.add_error('nok_price_direct', 
                                  'NOK price is required when using direct NOK input mode')
                elif nok_price_direct <= 0:
                    self.add_error('nok_price_direct', 
                                  'NOK price must be greater than 0')
                # Calculate conversion rate from NOK price and foreign currency price
                if price_override and price_override > 0:
                    cleaned_data['conversion_rate_to_nok'] = nok_price_direct / price_override

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

        if commit:
            instance.save()
            self.save_m2m()

        return instance
