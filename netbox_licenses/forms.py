from netbox.forms import NetBoxModelForm, NetBoxModelFilterSetForm
from utilities.forms.fields import CommentField, DynamicModelChoiceField, ContentTypeChoiceField
from django import forms
from django.forms import DateInput, NumberInput, IntegerField, DateField, ModelChoiceField, HiddenInput, CharField, ChoiceField, DecimalField, Textarea, BooleanField, URLField
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from .models import License, LicenseInstance, LicensePeriod, CurrencyConversionRate, PluginConfiguration
from .choices import CurrencyChoices, PaymentMethodChoices
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
    currency = CharField(
        max_length=3,
        initial='NOK',
        required=True,
        widget=forms.Select(),
        help_text="Currency code (must be defined in Currency Rates)"
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

    responsible_contact = DynamicModelChoiceField(
        queryset=Contact.objects.all(),
        required=False,
        label="Responsible Contact",
        help_text="Person responsible for maintaining this license (payments, renewals, compliance)"
    )

    class Meta:
        model = License
        fields = (
            'name', 'vendor', 'tenant', 'assignment_type', 'price', 'currency',
            'billing_cycle', 'payment_method', 'payment_portal_url', 'responsible_contact',
            'external_id', 'total_licenses', 'metadata',
            'comments', 'tags'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate currency choices dynamically from available conversion rates
        currencies = CurrencyConversionRate.get_available_currencies()
        self.fields['currency'].widget.choices = [(c, c) for c in currencies]

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


    class Meta:
        model = LicenseInstance
        fields = (
            'license', 'assigned_object_selector',
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


class QuantitySelectionForm(forms.Form):
    """Simple form to select quantity for bulk creation"""
    quantity = forms.IntegerField(
        min_value=1,
        label="How many instances?",
        help_text="Number of license instances to create",
        widget=forms.NumberInput(attrs={
            'min': '1',
            'step': '1',
            'class': 'form-control',
            'oninput': 'this.value = this.value.replace(/[^0-9]/g, "")'
        })
    )

    def __init__(self, license, *args, **kwargs):
        self.license = license
        super().__init__(*args, **kwargs)

        max_available = license.available_licenses
        self.fields['quantity'].widget.attrs['max'] = max_available
        self.fields['quantity'].help_text = f"Number of instances to create (max {max_available} available)"

        if max_available <= 0:
            self.fields['quantity'].widget.attrs['disabled'] = True
            self.fields['quantity'].help_text = "No license slots available"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        max_available = self.license.available_licenses

        if quantity > max_available:
            # Auto-clamp to maximum available instead of raising error
            quantity = max_available

        return quantity

class BulkLicenseInstanceForm(forms.Form):
    """Form for bulk creation of license instances"""

    # Common settings applied to all instances
    start_date = forms.DateField(
        required=False,
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

    def __init__(self, license, quantity=None, *args, **kwargs):
        self.license = license
        self.quantity = quantity
        super().__init__(*args, **kwargs)

        # Remove the dynamic quantity field since it's now passed as parameter
        if 'quantity' in self.fields:
            del self.fields['quantity']

        # Add static assignment fields based on quantity
        if license.assignment_type and quantity:
            model_class = license.assignment_type.model_class()

            for i in range(1, quantity + 1):
                field_name = f'assigned_object_{i}'
                self.fields[field_name] = DynamicModelChoiceField(
                    queryset=model_class.objects.all(),
                    required=True,  # Now required since we know exactly how many we need
                    label=f"Instance {i}",
                    help_text=f"Assign to {license.assignment_type.model}"
                )


    def clean(self):
        cleaned_data = super().clean()

        # If super().clean() returns None, return early
        if not cleaned_data:
            return cleaned_data

        # Use the quantity passed to the form
        quantity = self.quantity or 0

        if quantity > self.license.available_licenses:
            raise forms.ValidationError(
                f"Cannot create {quantity} instances. Only {self.license.available_licenses} slots available."
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
        quantity = self.quantity or 0
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
        help_text="Automatically sync API-sourced currency rates on schedule",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    currency_sync_interval_hours = IntegerField(
        min_value=1,
        initial=24,
        label="Currency Sync Interval (hours)",
        help_text="Hours between automatic currency rate synchronization",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    currency_stale_days = IntegerField(
        min_value=1,
        initial=7,
        label="Currency Stale Days",
        help_text="Number of days before a currency rate is considered stale",
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
            'currency_sync_interval_hours',
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

    price = DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        help_text="Cost for this renewal period"
    )

    currency = CharField(
        max_length=3,
        initial='NOK',
        required=True,
        widget=forms.Select(),
        help_text="Currency code (must be defined in Currency Rates)"
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
            'license', 'period_start', 'period_end', 'price', 'currency',
            'payment_method', 'seats_purchased',
            'invoice_reference', 'invoice_file', 'invoice_url',
            'comments', 'tags'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate currency choices dynamically from available conversion rates
        currencies = CurrencyConversionRate.get_available_currencies()
        self.fields['currency'].widget.choices = [(c, c) for c in currencies]

        # Auto-fill fields based on the selected license
        # Only for new renewals, not edits
        if not self.instance.pk:
            # Get license from initial data (set by view's alter_object)
            license_id = self.initial.get('license')

            if license_id:
                try:
                    license_obj = License.objects.get(pk=license_id)

                    # Auto-fill from license
                    if 'price' not in self.initial:
                        self.initial['price'] = license_obj.price
                    if 'currency' not in self.initial:
                        self.initial['currency'] = license_obj.currency
                    if 'payment_method' not in self.initial:
                        self.initial['payment_method'] = license_obj.payment_method
                    if 'seats_purchased' not in self.initial:
                        self.initial['seats_purchased'] = license_obj.total_licenses

                    # Auto-calculate period dates
                    if 'period_start' not in self.initial:
                        from django.utils import timezone
                        self.initial['period_start'] = timezone.now().date()

                    if 'period_end' not in self.initial:
                        from dateutil.relativedelta import relativedelta
                        from django.utils import timezone
                        start_date = self.initial.get('period_start') or timezone.now().date()

                        # Calculate end date based on billing cycle
                        if license_obj.billing_cycle == 'monthly':
                            end_date = start_date + relativedelta(months=1) - relativedelta(days=1)
                        elif license_obj.billing_cycle == 'quarterly':
                            end_date = start_date + relativedelta(months=3) - relativedelta(days=1)
                        elif license_obj.billing_cycle == 'yearly':
                            end_date = start_date + relativedelta(years=1) - relativedelta(days=1)
                        else:
                            # Default to 1 year for one_time or custom
                            end_date = start_date + relativedelta(years=1) - relativedelta(days=1)

                        self.initial['period_end'] = end_date

                except License.DoesNotExist:
                    pass

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get('period_start')
        period_end = cleaned_data.get('period_end')

        if period_start and period_end and period_end <= period_start:
            raise ValidationError("Period end date must be after start date")

        seats_purchased = cleaned_data.get('seats_purchased')
        seats_utilized = cleaned_data.get('seats_utilized', 0)

        if seats_utilized > seats_purchased:
            raise ValidationError("Seats utilized cannot exceed seats purchased")

        return cleaned_data
