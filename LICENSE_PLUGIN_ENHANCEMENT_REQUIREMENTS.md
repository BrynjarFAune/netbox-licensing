# NetBox Licenses Plugin Enhancement - Detailed Requirements

## Overview
The NetBox Licenses Plugin needs comprehensive enhancement to support modern license management across multiple vendors with flexible assignment models. This document provides complete technical specifications for a Django developer to implement the required changes.

## Current State Analysis
- ✅ Basic license tracking with name, vendor/manufacturer, price
- ✅ Instance-based assignment tracking via `assigned_object_type`/`assigned_object_id` 
- ❌ Missing license utilization tracking (total vs consumed)
- ❌ Missing vendor-specific metadata storage
- ❌ No external ID tracking for API integrations
- ❌ Limited assignment flexibility and bulk operations

## Technical Requirements

### 1. Database Schema Enhancements

#### License Model Additions
```python
class License(models.Model):
    # Existing fields remain unchanged:
    # - name, vendor (manufacturer), tenant, price, currency, etc.
    
    # NEW REQUIRED FIELDS:
    external_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="Vendor-specific identifier (SKU ID, subscription ID, license key, etc.)"
    )
    
    total_licenses = models.PositiveIntegerField(
        default=1,
        help_text="Total available license slots purchased"
    )
    
    consumed_licenses = models.PositiveIntegerField(
        default=0,
        help_text="Currently assigned/consumed licenses"
    )
    
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Vendor-specific data (service plans, features, API limits, etc.)"
    )
    
    # COMPUTED PROPERTIES:
    @property
    def available_licenses(self):
        """Calculate remaining available licenses"""
        return self.total_licenses - self.consumed_licenses
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.total_licenses == 0:
            return 0
        return (self.consumed_licenses / self.total_licenses) * 100
```

#### Database Indexes
```python
class Meta:
    indexes = [
        models.Index(fields=['external_id']),
        models.Index(fields=['vendor', 'external_id']),
        models.Index(fields=['consumed_licenses', 'total_licenses']),
    ]
```

### 2. Assignment Model Enhancements

The existing `LicenseInstance` model should be enhanced to support flexible assignments:

```python
class LicenseInstance(models.Model):
    # Existing fields remain unchanged
    
    # ENHANCED ASSIGNMENT SUPPORT:
    # assigned_object_type and assigned_object_id already support generic assignments
    # Ensure ContentType supports: auth.User, dcim.Device, and any other NetBox objects
    
    # ADD HELPER METHODS:
    def get_assignment_display(self):
        """Return human-readable assignment info"""
        if self.assigned_object_type.model == 'user':
            return f"User: {self.assigned_object.username}"
        elif self.assigned_object_type.model == 'device':
            return f"Device: {self.assigned_object.name}"
        else:
            return f"{self.assigned_object_type.model}: {str(self.assigned_object)}"
    
    @property
    def assignment_type(self):
        """Return assignment type for filtering"""
        return self.assigned_object_type.model
```

### 3. API Serializer Updates

#### License Serializer Enhancements
```python
class LicenseSerializer(serializers.ModelSerializer):
    available_licenses = serializers.ReadOnlyField()
    utilization_percentage = serializers.ReadOnlyField()
    instance_count = serializers.SerializerMethodField()
    
    class Meta:
        model = License
        fields = [
            # Existing fields...
            'external_id',
            'total_licenses', 
            'consumed_licenses',
            'available_licenses',
            'utilization_percentage',
            'metadata',
            'instance_count'
        ]
    
    def get_instance_count(self, obj):
        return obj.licenseinstance_set.count()
```

#### Filter Classes
```python
class LicenseFilterSet(django_filters.FilterSet):
    vendor = django_filters.ModelChoiceFilter(queryset=Manufacturer.objects.all())
    external_id = django_filters.CharFilter(lookup_expr='icontains')
    has_external_id = django_filters.BooleanFilter(method='filter_has_external_id')
    underutilized = django_filters.BooleanFilter(method='filter_underutilized')
    overallocated = django_filters.BooleanFilter(method='filter_overallocated')
    
    def filter_has_external_id(self, queryset, name, value):
        if value:
            return queryset.exclude(external_id__isnull=True).exclude(external_id='')
        return queryset.filter(models.Q(external_id__isnull=True) | models.Q(external_id=''))
    
    def filter_underutilized(self, queryset, name, value):
        if value:
            return queryset.filter(consumed_licenses__lt=models.F('total_licenses'))
        return queryset
    
    def filter_overallocated(self, queryset, name, value):
        if value:
            return queryset.filter(consumed_licenses__gt=models.F('total_licenses'))
        return queryset
```

### 4. Admin Interface Enhancements

```python
@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'vendor', 'external_id', 
        'license_utilization', 'total_licenses', 
        'consumed_licenses', 'available_licenses',
        'price_display'
    ]
    list_filter = [
        'vendor', 'tenant', 'currency',
        ('external_id', admin.EmptyFieldListFilter),
        'created', 'last_updated'
    ]
    search_fields = ['name', 'external_id', 'comments']
    readonly_fields = ['available_licenses', 'utilization_percentage', 'instance_count']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'vendor', 'tenant', 'external_id')
        }),
        ('License Allocation', {
            'fields': ('total_licenses', 'consumed_licenses', 'available_licenses')
        }),
        ('Pricing', {
            'fields': ('price', 'currency', 'price_display')
        }),
        ('Metadata', {
            'fields': ('metadata', 'comments'),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('utilization_percentage', 'instance_count', 'created', 'last_updated'),
            'classes': ('collapse',)
        })
    )
    
    def license_utilization(self, obj):
        percentage = obj.utilization_percentage
        color = 'green' if percentage < 80 else 'orange' if percentage < 100 else 'red'
        return format_html(
            '<span style="color: {};">{:.1f}% ({}/{})</span>',
            color, percentage, obj.consumed_licenses, obj.total_licenses
        )
    license_utilization.short_description = 'Utilization'
```

### 5. Vendor-Specific Metadata Examples

#### Microsoft Licenses
```json
{
  "service_plans": [
    {
      "servicePlanId": "113feb6c-3fe4-4440-bddc-54d774bf0318",
      "servicePlanName": "EXCHANGE_S_FOUNDATION", 
      "servicePlanType": "Exchange",
      "provisioningStatus": "Success"
    }
  ],
  "license_type": "subscription",
  "renewal_date": "2025-12-31"
}
```

#### OpenAI Licenses
```json
{
  "api_limits": {
    "requests_per_minute": 3500,
    "tokens_per_minute": 90000
  },
  "models": ["gpt-4", "gpt-3.5-turbo"],
  "tier": "paid",
  "organization_id": "org-xxxxx"
}
```

#### ESET Security Licenses
```json
{
  "product": "ESET Endpoint Security",
  "version": "10.0",
  "features": ["antivirus", "firewall", "web_protection"],
  "license_key": "XXXX-XXXX-XXXX-XXXX",
  "expiration_date": "2025-06-30"
}
```

#### Anthropic Licenses
```json
{
  "models": ["claude-3-sonnet", "claude-3-haiku"],
  "usage_limits": {
    "monthly_messages": 100000,
    "rate_limit": "100/minute"
  },
  "plan": "pro",
  "workspace_id": "ws-xxxxx"
}
```

### 6. Migration Script Template

```python
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('licenses', '0001_initial'),  # Adjust to actual last migration
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='external_id',
            field=models.CharField(blank=True, max_length=255, null=True,
                                 help_text='Vendor-specific identifier'),
        ),
        migrations.AddField(
            model_name='license',
            name='total_licenses',
            field=models.PositiveIntegerField(default=1,
                                            help_text='Total available license slots'),
        ),
        migrations.AddField(
            model_name='license',
            name='consumed_licenses',
            field=models.PositiveIntegerField(default=0,
                                            help_text='Currently assigned licenses'),
        ),
        migrations.AddField(
            model_name='license',
            name='metadata',
            field=models.JSONField(blank=True, default=dict,
                                 help_text='Vendor-specific data'),
        ),
        migrations.AddIndex(
            model_name='license',
            index=models.Index(fields=['external_id'], name='licenses_license_external_id_idx'),
        ),
        migrations.AddIndex(
            model_name='license',
            index=models.Index(fields=['vendor', 'external_id'], name='licenses_license_vendor_external_idx'),
        ),
    ]
```

### 7. Business Logic Requirements

#### Automatic consumed_licenses Updates
```python
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver([post_save, post_delete], sender=LicenseInstance)
def update_consumed_licenses(sender, instance, **kwargs):
    """Automatically update consumed_licenses when instances are added/removed"""
    license = instance.license
    license.consumed_licenses = license.licenseinstance_set.count()
    license.save(update_fields=['consumed_licenses'])
```

#### Validation Rules
```python
def clean(self):
    """Validate license data"""
    super().clean()
    
    if self.consumed_licenses > self.total_licenses:
        # Allow but warn about overallocation
        pass  # or raise ValidationError if strict validation needed
    
    if self.total_licenses < 0:
        raise ValidationError("Total licenses cannot be negative")
    
    if self.consumed_licenses < 0:
        raise ValidationError("Consumed licenses cannot be negative")
```

### 8. Assignment Type Support

The plugin should support these assignment patterns:

#### User Assignments (Microsoft 365, SaaS)
- `assigned_object_type` → `ContentType.objects.get_for_model(User)`
- Track which users have specific licenses
- Used for: Microsoft 365, OpenAI, Anthropic, Visma

#### Device Assignments (Security Software)
- `assigned_object_type` → `ContentType.objects.get_for_model(Device)`
- Track which devices have security licenses installed
- Used for: ESET, Heimdal, endpoint protection

#### Generic Assignments (Future Flexibility)
- Support any NetBox model via ContentType framework
- Enables assignment to Sites, Circuits, VMs, etc.

### 9. Reporting and Analytics

#### Required Reports
1. **License Utilization Report**: Show usage across all manufacturers
2. **Cost Optimization Report**: Identify underutilized expensive licenses  
3. **Expiration Report**: Track licenses nearing renewal
4. **Manufacturer Summary**: Group utilization by vendor

#### Example Query Patterns
```python
# Underutilized licenses (less than 80% used)
underutilized = License.objects.annotate(
    utilization=models.F('consumed_licenses') * 100.0 / models.F('total_licenses')
).filter(utilization__lt=80, total_licenses__gt=1)

# Overallocated licenses
overallocated = License.objects.filter(consumed_licenses__gt=models.F('total_licenses'))

# Cost savings opportunity  
savings = License.objects.annotate(
    unused_cost=models.F('price') * (models.F('total_licenses') - models.F('consumed_licenses'))
).filter(unused_cost__gt=0)
```

### 10. API Integration Support

The enhanced plugin should support external API synchronization:

#### Microsoft Graph Integration
- Use `external_id` to store SKU IDs
- `metadata` stores service plans
- `total_licenses`/`consumed_licenses` from subscribedSkus API

#### Other Vendor APIs
- `external_id` enables lookup in vendor systems
- `metadata` stores vendor-specific configuration
- Standardized update patterns for consumption data

## Implementation Priority

### Phase 1: Core Schema
1. Database migrations for new fields
2. Model enhancements with computed properties
3. Admin interface basic updates

### Phase 2: API and UI
1. Serializer updates with new fields
2. Filter enhancements for utilization queries
3. Advanced admin interface with utilization display

### Phase 3: Business Logic
1. Automatic consumed_licenses calculation
2. Signal handlers for instance tracking
3. Validation and cleanup logic

### Phase 4: Integration Features
1. Bulk assignment operations
2. Reporting and analytics views
3. External API synchronization support

## Backward Compatibility Requirements

- All existing License records must remain functional
- Existing API endpoints must continue to work
- New fields should have sensible defaults
- Migration should handle existing data gracefully
- LicenseInstance model changes must preserve existing assignments

## Success Criteria

- ✅ All vendor license types supported without schema changes
- ✅ License utilization clearly visible (consumed/total)
- ✅ Cost optimization opportunities identifiable
- ✅ External ID tracking enables vendor API integration
- ✅ Flexible assignment model supports users, devices, any NetBox object
- ✅ Manufacturer-based filtering and reporting functional
- ✅ Backward compatibility maintained
- ✅ Performance optimized for large license datasets

## Testing Requirements

1. **Migration Testing**: Verify existing data integrity
2. **API Testing**: Ensure all endpoints work with new fields
3. **Assignment Testing**: Verify user/device/generic assignments work
4. **Utilization Testing**: Confirm automatic calculation accuracy
5. **Performance Testing**: Large dataset queries remain fast
6. **Integration Testing**: External ID lookup and metadata handling

This enhancement will transform the NetBox Licenses Plugin into a comprehensive license management solution suitable for modern enterprise environments with diverse vendor ecosystems.