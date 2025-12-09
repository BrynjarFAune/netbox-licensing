from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField, ContentTypeChoiceField, ContentTypeMultipleChoiceField, DynamicModelMultipleChoiceField
from utilities.forms.widgets import APISelect, HTMXSelect
from django import forms
from django.forms import DateInput, NumberInput, IntegerField, DateField, ModelChoiceField, HiddenInput, CharField, ChoiceField, DecimalField, Textarea, BooleanField, URLField
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from extras.models import Tag
from .models import License, LicenseInstance, LicensePeriod, CurrencyConversionRate, PluginConfiguration
from .choices import CurrencyChoices, PaymentMethodChoices, PricingModeChoices
from tenancy.models import Contact, Tenant
from dcim.models import Manufacturer

class LicenseForm(NetBoxModelForm):
    comments = CommentField()
    vendor = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=True,
        quick_add=True
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=True,
        quick_add=True
    )
    assignment_type = ContentTypeChoiceField(
        queryset=ContentType.objects.all(),
        required=True,
        label="Assignable Object Type",
        help_text="Select which object type can be assigned to this license (e.g., device, VM)"
    )
    
    total_licenses = IntegerField(
        required=False,
        min_value=0,
        label="Seats",
        help_text="Total available license seats purchased (leave blank if undefined/not applicable)"
    )
    
    metadata = CharField(
        required=False,
        widget=Textarea(attrs={'rows': 4, 'placeholder': 'Enter JSON metadata for vendor-specific data'}),
        help_text="Vendor-specific data in JSON format (service plans, features, API limits, etc.)"
    )

    # NEW PAYMENT AND RESPONSIBILITY FIELDS
    payment_method = ChoiceField(
        choices=PaymentMethodChoices.CHOICES,
        initial=PaymentMethodChoices.INVOICE,
        label="Payment Method",
        help_text="How this license is paid for"
    )

    payment_portal_url = URLField(
        required=False,
        max_length=500,
        label="Payment Portal URL",
        help_text="URL to payment portal or subscription management page"
    )

    # Removed: responsible_contact - now managed via ContactAssignment
    # Contacts are assigned through NetBox's standard contact assignment UI

    tags = DynamicModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        quick_add=True
    )

    class Meta:
        model = License
        fields = (
            'name', 'vendor', 'tenant', 'assignment_type',
            'billing_cycle', 'payment_method', 'payment_portal_url',
            'total_licenses', 'metadata',
            'comments', 'tags'
        )

    def clean_total_licenses(self):
        """Validate total_licenses cannot be reduced below consumed licenses"""
        total_licenses = self.cleaned_data.get('total_licenses')

        # Allow None for undefined capacity licenses
        if total_licenses is None:
            return None

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

    assigned_object_selector = DynamicModelChoiceField(
        queryset=Contact.objects.none(),  # Will be updated based on license and type
        required=True,
        label="Assigned Object",
        help_text="Search and select the specific object to assign"
    )

    # INDIVIDUAL INSTANCE PRICING (optional - shown only for undefined capacity licenses)
    individual_price = DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.01'}),
        label="Monthly Price",
        help_text="Monthly subscription price for this instance (e.g., $20/month for Claude Pro)"
    )

    individual_currency = CharField(
        required=False,
        max_length=3,
        label="Currency",
        help_text="Currency code (e.g., USD, EUR, NOK)",
        widget=forms.TextInput(attrs={
            'placeholder': 'NOK',
            'maxlength': '3',
            'style': 'text-transform: uppercase;',
        })
    )

    billing_start = DateField(
        required=False,
        widget=DateInput(attrs={'type': 'date'}),
        label="Billing Start",
        help_text="When billing starts for this instance"
    )

    billing_end = DateField(
        required=False,
        widget=DateInput(attrs={'type': 'date'}),
        label="Billing End",
        help_text="When billing ends (leave blank for ongoing)"
    )

    class Meta:
        model = LicenseInstance
        fields = (
            'license', 'assigned_object_selector',
            'start_date', 'end_date',
            'individual_price', 'billing_start', 'billing_end',
            'comments', 'tags'
        )
        # Note: individual_currency handled separately in save() due to ForeignKey conversion
        widgets = {
            'start_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
            'end_date': DateInput(attrs={'type': 'date', 'format': '%d/%m/%Y'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get license to determine allowed assignment type
        license_obj = self._get_license_object()

        # Determine which content type to use for the assigned_object queryset
        selected_ct = None

        # If editing existing instance, use its type
        if self.instance and self.instance.pk and self.instance.assigned_object_type:
            selected_ct = self.instance.assigned_object_type

        # Otherwise use the allowed type from license
        if not selected_ct and license_obj and license_obj.assignment_type:
            selected_ct = license_obj.assignment_type

        # Set the queryset based on selected content type
        if selected_ct:
            model_class = selected_ct.model_class()
            if model_class:
                self.fields['assigned_object_selector'].queryset = model_class.objects.all()
                self.fields['assigned_object_selector'].label = f"Assigned {model_class._meta.verbose_name.title()}"

        # If editing existing instance, populate initial value
        if self.instance and self.instance.pk and self.instance.assigned_object:
            self.fields['assigned_object_selector'].initial = self.instance.assigned_object

        # Pre-populate individual_currency if editing
        if self.instance and self.instance.pk and self.instance.individual_currency:
            self.fields['individual_currency'].initial = self.instance.individual_currency.currency_code

        # Auto-fill pricing from license for new instances (if license has undefined capacity)
        if not self.instance.pk and license_obj and license_obj.total_licenses is None:
            # This is a new instance for an undefined capacity license
            # Pre-fill with license's active period pricing as a helpful default
            if license_obj.active_period_per_seat_price and license_obj.active_period_per_seat_price > 0:
                self.fields['individual_price'].initial = license_obj.active_period_per_seat_price
                self.fields['individual_currency'].initial = license_obj.active_period_currency
                self.fields['individual_price'].help_text = f"Pre-filled from license (default: {license_obj.active_period_per_seat_price} {license_obj.active_period_currency})"

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

    def clean(self):
        cleaned_data = super().clean()

        if not cleaned_data:
            return cleaned_data

        license = cleaned_data.get('license')
        assigned_object_selector = cleaned_data.get('assigned_object_selector')

        if not license:
            return cleaned_data

        # Check license availability for new instances (warning only, allow overallocation)
        # Skip check for unlimited licenses (total_licenses = None)
        if not self.instance.pk and license.total_licenses is not None:  # New instance with limited seats
            current_instances = license.instances.count()
            available_licenses = license.total_licenses - current_instances

            if available_licenses <= 0:
                from django.contrib import messages
                # Add warning instead of error - allow overallocation
                if hasattr(self, 'request'):
                    messages.warning(
                        self.request,
                        f"Warning: This will overallocate the license. "
                        f"{license.name} has {license.total_licenses} total slots "
                        f"with {current_instances} already consumed."
                    )

        # Validate object matches the license's allowed type
        if assigned_object_selector and license.assignment_type:
            actual_ct = ContentType.objects.get_for_model(assigned_object_selector)
            if actual_ct.pk != license.assignment_type.pk:
                self.add_error('assigned_object_selector',
                    f"Selected object type does not match license's assignment type")

        # Assignment is required for instances
        if not assigned_object_selector:
            self.add_error('assigned_object_selector', "An assigned object is required for license instances")

        # Validate individual pricing currency
        individual_price = cleaned_data.get('individual_price')
        individual_currency_code = cleaned_data.get('individual_currency')

        if individual_price and individual_currency_code:
            # Convert currency code to CurrencyConversionRate object
            currency_code = individual_currency_code.upper()
            try:
                from netbox_licenses.models import CurrencyConversionRate
                currency = CurrencyConversionRate.objects.get(currency_code=currency_code)
                cleaned_data['individual_currency'] = currency
            except CurrencyConversionRate.DoesNotExist:
                # Try to auto-create from API
                from netbox_licenses.services.currency_service import create_currency_from_api, NorgesBankAPIError
                try:
                    currency = create_currency_from_api(currency_code)
                    cleaned_data['individual_currency'] = currency
                except (ValidationError, NorgesBankAPIError) as e:
                    self.add_error('individual_currency', f"Currency '{currency_code}' not found: {str(e)}")
        elif individual_price and not individual_currency_code:
            # Price without currency - assume NOK
            from netbox_licenses.models import CurrencyConversionRate
            try:
                currency = CurrencyConversionRate.objects.get(currency_code='NOK')
                cleaned_data['individual_currency'] = currency
            except CurrencyConversionRate.DoesNotExist:
                cleaned_data['individual_currency'] = None  # Will be treated as NOK in model
        else:
            cleaned_data['individual_currency'] = None

        return cleaned_data

    def _post_clean(self):
        """Override to set GenericForeignKey fields before model validation"""
        # Set the assignment fields BEFORE calling super()._post_clean()
        # This allows model validation to see these fields
        if hasattr(self, 'cleaned_data'):
            assigned_object_selector = self.cleaned_data.get('assigned_object_selector')

            if assigned_object_selector:
                self.instance.assigned_object_type = ContentType.objects.get_for_model(assigned_object_selector)
                self.instance.assigned_object_id = assigned_object_selector.pk

            # CRITICAL: Handle currency conversion BEFORE super()._post_clean()
            # This prevents Django from trying to assign the string value directly
            if 'individual_currency' in self.cleaned_data:
                self.instance.individual_currency = self.cleaned_data['individual_currency']

        super()._post_clean()

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Assignment fields and currency already set in _post_clean()
        if commit:
            instance.save()
            self.save_m2m()

        return instance


class LicenseInstanceBulkEditForm(NetBoxModelForm):
    """Bulk edit form for license instances"""

    end_date = DateField(
        required=False,
        widget=DateInput(attrs={'type': 'date'}),
        help_text="Update end date for selected instances"
    )

    comments = CommentField()

    class Meta:
        model = LicenseInstance
        fields = ['end_date', 'comments']
        nullable_fields = ['end_date', 'comments']


class BulkLicenseInstanceForm(forms.Form):
    """Form for bulk creation of license instances"""

    quantity = forms.IntegerField(
        min_value=1,
        label="How many instances?",
        help_text="Number of license instances to create"
    )

    # Common settings applied to all instances
    start_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Start Date"
    )

    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="End Date"
    )

    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        label="Comments"
    )

    def __init__(self, license, *args, **kwargs):
        self.license = license
        super().__init__(*args, **kwargs)

        # Set default start date to today
        if 'initial' not in kwargs or 'start_date' not in kwargs.get('initial', {}):
            self.fields['start_date'].initial = timezone.now().date()

        # Add dynamic assignment fields (up to 20)
        # Allow overallocation - don't restrict based on available_licenses
        if license.assignment_type:
            model_class = license.assignment_type.model_class()

            for i in range(1, 21):  # Cap at 20 for UI sanity
                field_name = f'assigned_object_{i}'
                self.fields[field_name] = DynamicModelChoiceField(
                    queryset=model_class.objects.all(),
                    required=False,  # JavaScript makes them required dynamically
                    label=f"Instance {i}",
                    help_text=f"Assign to {license.assignment_type.model}"
                )


    def clean(self):
        cleaned_data = super().clean()

        # If super().clean() returns None, return early
        if not cleaned_data:
            return cleaned_data

        # Use the quantity from the form
        quantity = cleaned_data.get('quantity', 0)

        # Allow overallocation - just show warning if it would happen
        # Skip check for unlimited licenses (total_licenses = None)
        if self.license.total_licenses is not None:
            available = self.license.available_licenses
            if available is not None and quantity > available:
                from django.contrib import messages
                messages.warning(
                    self.request if hasattr(self, 'request') else None,
                    f"Warning: Creating {quantity} instances will overallocate this license. "
                    f"License has {self.license.total_licenses} total slots with "
                    f"{self.license.consumed_licenses} already consumed."
                )

        # Check that we have enough assigned objects and no duplicates
        assigned_objects = []
        for i in range(1, quantity + 1):
            field_name = f'assigned_object_{i}'
            obj = cleaned_data.get(field_name)
            if obj:
                if obj in assigned_objects:
                    self.add_error(field_name, "This object is already selected for another instance.")
                assigned_objects.append(obj)
            else:
                self.add_error(field_name, f"Instance {i} assignment is required.")

        return cleaned_data

    def save(self, commit=True):
        """Create multiple license instances"""
        quantity = self.cleaned_data.get('quantity', 0)
        instances = []

        for i in range(1, quantity + 1):
            field_name = f'assigned_object_{i}'
            assigned_obj = self.cleaned_data.get(field_name)

            if assigned_obj:
                instance = LicenseInstance(
                    license=self.license,
                    assigned_object=assigned_obj,
                    start_date=self.cleaned_data.get('start_date'),
                    end_date=self.cleaned_data.get('end_date'),
                    comments=self.cleaned_data.get('comments', ''),
                )

                if commit:
                    instance.save()
                    # Handle tags
                    if self.cleaned_data.get('tags'):
                        instance.tags.set(self.cleaned_data['tags'])

                instances.append(instance)

        return instances


class CurrencyConversionRateManualForm(NetBoxModelForm):
    """Form for manually creating/editing currency conversion rates"""

    currency_code = CharField(
        max_length=3,
        label="Currency Code",
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)"
    )
    rate_to_nok = DecimalField(
        max_digits=12,
        decimal_places=6,
        min_value=0,
        widget=NumberInput(attrs={'step': '0.000001'}),
        label="Rate to NOK",
        help_text="Conversion rate: 1 [currency] = X NOK"
    )

    class Meta:
        model = CurrencyConversionRate
        fields = ('currency_code', 'rate_to_nok', 'notes', 'tags')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set source to manual (hidden field, set programmatically)
        if not self.instance.pk:
            self.instance.source = 'manual'

    def clean_currency_code(self):
        code = self.cleaned_data.get('currency_code', '').upper()

        # Check if it already exists (only for new records)
        if not self.instance.pk:
            if CurrencyConversionRate.objects.filter(currency_code=code).exists():
                raise ValidationError(f"Currency {code} already exists.")

        return code

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.source = 'manual'
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CurrencyConversionRateAPIForm(forms.Form):
    """Form for fetching currency rate from Norges Bank API"""

    currency_code = CharField(
        max_length=3,
        label="Currency Code",
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP)",
        widget=forms.TextInput(attrs={'placeholder': 'USD'})
    )
    notes = CharField(
        required=False,
        widget=Textarea(attrs={'rows': 3}),
        label="Notes",
        help_text="Optional notes about this currency"
    )

    def clean_currency_code(self):
        code = self.cleaned_data.get('currency_code', '').upper()

        # Check if it already exists
        if CurrencyConversionRate.objects.filter(currency_code=code).exists():
            raise ValidationError(
                f"Currency {code} already exists. Use the sync button to update its rate."
            )

        return code

    def save(self):
        """Fetch rate from API and create currency"""
        from netbox_licenses.services.currency_service import create_currency_from_api

        currency_code = self.cleaned_data['currency_code']
        notes = self.cleaned_data.get('notes', '')

        # This will raise NorgesBankAPIError if it fails
        return create_currency_from_api(currency_code, notes)


class CurrencyConversionRateFilterForm(NetBoxModelFilterSetForm):
    """FilterSet form for currency conversion rates"""
    model = CurrencyConversionRate

    source = ChoiceField(
        choices=[('', 'All'), ('api', 'Norges Bank API'), ('manual', 'Manual Entry')],
        required=False,
        label='Source'
    )


class LicenseBulkEditForm(NetBoxModelForm):
    """
    Bulk edit form for licenses.
    Allows editing vendor, tenant, payment info, contacts, and pricing for multiple licenses.
    """
    vendor = DynamicModelChoiceField(
        queryset=Manufacturer.objects.all(),
        required=False,
        label="Vendor"
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        label="Tenant"
    )
    payment_method = ChoiceField(
        choices=[('', '---------')] + list(PaymentMethodChoices.CHOICES),
        required=False,
        label="Payment Method"
    )
    billing_cycle = ChoiceField(
        choices=[('', '---------'), ('monthly', 'Monthly'), ('annually', 'Annually'), ('perpetual', 'Perpetual'), ('other', 'Other')],
        required=False,
        label="Billing Cycle"
    )
    payment_portal_url = URLField(
        required=False,
        max_length=500,
        label="Payment Portal URL"
    )
    responsible_contact = DynamicModelChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        label="Responsible Contact"
    )
    currency = CharField(
        max_length=3,
        required=False,
        widget=forms.Select(),
        label="Currency"
    )
    price = DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="Price per License"
    )

    class Meta:
        model = License
        fields = []  # We define fields manually above
        nullable_fields = ['payment_portal_url', 'responsible_contact', 'price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate currency choices
        currencies = CurrencyConversionRate.get_available_currencies()
        self.fields['currency'].widget.choices = [('', '---------')] + [(c, c) for c in currencies]


class PluginConfigurationForm(forms.ModelForm):
    """Form for editing plugin configuration"""

    utilization_excellent_threshold = IntegerField(
        min_value=0,
        max_value=100,
        initial=90,
        label="Excellent Utilization Threshold (%)",
        help_text="Green badge - licenses are well utilized (≥90%)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    utilization_good_threshold = IntegerField(
        min_value=0,
        max_value=100,
        initial=70,
        label="Good Utilization Threshold (%)",
        help_text="Blue badge - acceptable license usage (≥70%)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    utilization_moderate_threshold = IntegerField(
        min_value=0,
        max_value=100,
        initial=50,
        label="Moderate Utilization Threshold (%)",
        help_text="Yellow badge - approaching underutilization (≥50%)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    currency_sync_enabled = BooleanField(
        required=False,
        initial=True,
        label="Enable Automatic Currency Sync",
        help_text="Automatically sync stale API-sourced currency rates on-demand when used",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    currency_stale_days = IntegerField(
        min_value=1,
        initial=7,
        label="Currency Stale Days",
        help_text="Number of days before a currency rate is considered stale and triggers auto-sync",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    renewal_warning_days = IntegerField(
        min_value=1,
        initial=90,
        label="Renewal Warning Days",
        help_text="Days before expiry to show renewal warnings",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    renewal_critical_days = IntegerField(
        min_value=1,
        initial=30,
        label="Renewal Critical Days",
        help_text="Days before expiry to show critical renewal alerts",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    dashboard_expiring_soon_days = IntegerField(
        min_value=1,
        initial=90,
        label="Dashboard: Expiring Soon (days)",
        help_text="Show instances expiring within this many days on dashboard",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    dashboard_recently_expired_days = IntegerField(
        min_value=1,
        initial=30,
        label="Dashboard: Recently Expired (days)",
        help_text="Show instances expired within this many days on dashboard",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    class Meta:
        model = PluginConfiguration
        fields = [
            'utilization_excellent_threshold',
            'utilization_good_threshold',
            'utilization_moderate_threshold',
            'currency_sync_enabled',
            'currency_stale_days',
            'renewal_warning_days',
            'renewal_critical_days',
            'dashboard_expiring_soon_days',
            'dashboard_recently_expired_days',
        ]


class LicensePeriodForm(NetBoxModelForm):
    """Form for creating license period records (billing/subscription periods)"""

    license = DynamicModelChoiceField(
        queryset=License.objects.all(),
        required=True
    )

    period_start = DateField(
        widget=DateInput(attrs={'type': 'date'}),
        required=True,
        help_text="Start date of this billing period"
    )

    period_end = DateField(
        widget=DateInput(attrs={'type': 'date'}),
        required=False,
        help_text="End date of this billing period (leave blank for perpetual/free licenses)"
    )

    pricing_mode = ChoiceField(
        choices=PricingModeChoices.CHOICES,
        initial=PricingModeChoices.PER_SEAT,
        required=True,
        label="Pricing Mode",
        help_text="How is the price calculated?",
        widget=forms.Select(attrs={'id': 'id_pricing_mode'})
    )

    price = DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        label="Price",
        help_text="Price value (label updates based on pricing mode)",
        widget=forms.NumberInput(attrs={'id': 'id_price', 'step': '0.01'})
    )

    currency = CharField(
        max_length=3,
        required=True,
        label="Currency",
        help_text="ISO 4217 currency code (e.g., USD, EUR, GBP). Enter 3-letter code and click sync to import from API.",
        widget=forms.TextInput(attrs={
            'placeholder': 'USD',
            'maxlength': '3',
            'style': 'text-transform: uppercase;',
            'class': 'form-control currency-code-input',
            'autocomplete': 'off',
            'list': 'currency-datalist'
        })
    )

    price_nok = DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        label="Price (NOK Override)",
        help_text="Optional: manually set NOK price. Leave blank to auto-convert from native currency.",
        widget=forms.NumberInput(attrs={'step': '0.01'})
    )

    conversion_rate = DecimalField(
        max_digits=10,
        decimal_places=6,
        required=False,
        label="Conversion Rate",
        help_text="Optional: conversion rate (1 native = X NOK). Auto-calculated if left blank.",
        widget=forms.NumberInput(attrs={'step': '0.000001'})
    )

    payment_method = ChoiceField(
        choices=PaymentMethodChoices.CHOICES,
        required=True,
        help_text="How this renewal will be paid"
    )

    seats_purchased = IntegerField(
        min_value=1,
        required=True,
        help_text="Number of license seats for this period"
    )

    # seats_utilized is auto-set from license.consumed_licenses on save - not user editable

    # Invoice tracking fields (optional)
    invoice_reference = CharField(
        max_length=200,
        required=False,
        help_text="Invoice number or reference"
    )

    invoice_file = forms.FileField(
        required=False,
        help_text="Upload invoice PDF or image"
    )

    invoice_url = URLField(
        max_length=500,
        required=False,
        help_text="Link to invoice in accounting system"
    )

    comments = CommentField()

    class Meta:
        model = LicensePeriod
        fields = [
            'license', 'period_start', 'period_end', 'pricing_mode', 'price', 'currency',
            'price_nok', 'conversion_rate', 'payment_method', 'seats_purchased',
            'invoice_reference', 'invoice_file', 'invoice_url',
            'comments', 'tags'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Currency is now a ForeignKey with quick_add support - no manual choices needed

        # Auto-fill fields based on the selected license
        # Only for new renewals, not edits
        if not self.instance.pk:
            # Get license from initial data (set by view's alter_object)
            license_id = self.initial.get('license')

            if license_id:
                try:
                    license_obj = License.objects.get(pk=license_id)

                    # Auto-fill from license (if not unlimited)
                    if 'seats_purchased' not in self.initial and license_obj.total_licenses is not None:
                        self.initial['seats_purchased'] = license_obj.total_licenses
                        self.fields['seats_purchased'].initial = license_obj.total_licenses

                    # Calculate total price from active period
                    if 'price' not in self.initial:
                        from decimal import Decimal
                        # Default to per-seat pricing from active period
                        per_seat_price = license_obj.active_period_per_seat_price
                        self.initial['price'] = per_seat_price
                        self.initial['pricing_mode'] = 'per_seat'

                    if 'currency' not in self.initial:
                        self.initial['currency'] = license_obj.active_period_currency
                    if 'payment_method' not in self.initial:
                        self.initial['payment_method'] = license_obj.payment_method

                    # Auto-set period start date only
                    if 'period_start' not in self.initial:
                        from django.utils import timezone
                        self.initial['period_start'] = timezone.now().date()

                except License.DoesNotExist:
                    pass

    def clean_currency(self):
        """Convert currency code to CurrencyConversionRate object, auto-creating from API if needed"""
        currency_code = self.cleaned_data.get('currency', '').upper()

        if not currency_code:
            raise ValidationError("Currency code is required")

        # Look up the currency
        try:
            currency = CurrencyConversionRate.objects.get(currency_code=currency_code)
        except CurrencyConversionRate.DoesNotExist:
            # Try to auto-create from API
            from .services.currency_service import create_currency_from_api, NorgesBankAPIError
            try:
                currency = create_currency_from_api(currency_code)
            except ValidationError as e:
                # Currency was created by another request between lookup and creation
                # Try to get it again
                try:
                    currency = CurrencyConversionRate.objects.get(currency_code=currency_code)
                except CurrencyConversionRate.DoesNotExist:
                    raise ValidationError(str(e))
            except NorgesBankAPIError as e:
                raise ValidationError(
                    f"Currency '{currency_code}' not found in database and could not be fetched from API: {str(e)}"
                )

        return currency

    def clean(self):
        cleaned_data = super().clean()

        # If parent clean() returned None or there are errors, return early
        if cleaned_data is None:
            return cleaned_data

        period_start = cleaned_data.get('period_start')
        period_end = cleaned_data.get('period_end')

        if period_start and period_end and period_end <= period_start:
            raise ValidationError("Period end date must be after start date")

        seats_purchased = cleaned_data.get('seats_purchased')
        seats_utilized = cleaned_data.get('seats_utilized', 0)

        if seats_utilized > seats_purchased:
            raise ValidationError("Seats utilized cannot exceed seats purchased")

        return cleaned_data
