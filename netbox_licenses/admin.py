from django.contrib import admin
from django.utils.html import format_html
from .models import License, LicenseInstance


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
        ('Assignment Configuration', {
            'fields': ('assignment_type',)
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
        if percentage < 80:
            color = 'green'
        elif percentage < 100:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}% ({}/{})</span>',
            color, percentage, obj.consumed_licenses, obj.total_licenses
        )
    license_utilization.short_description = 'Utilization'
    
    def instance_count(self, obj):
        return obj.instances.count()
    instance_count.short_description = 'Instance Count'


@admin.register(LicenseInstance)
class LicenseInstanceAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'license', 'get_assignment_display',
        'display_price', 'derived_status', 'start_date', 'end_date'
    ]
    list_filter = [
        'license__vendor', 'currency_override', 'start_date', 'end_date',
        'created', 'last_updated'
    ]
    search_fields = ['license__name', 'comments']
    readonly_fields = ['instance_price_nok', 'display_price']
    
    fieldsets = (
        ('License Assignment', {
            'fields': ('license', 'assigned_object_type', 'assigned_object_id')
        }),
        ('Pricing Override', {
            'fields': ('price_override', 'currency_override', 'nok_price_override')
        }),
        ('Computed Values', {
            'fields': ('instance_price_nok', 'display_price'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Additional Information', {
            'fields': ('comments', 'tags'),
            'classes': ('collapse',)
        })
    )
    
    def get_assignment_display(self, obj):
        return obj.get_assignment_display()
    get_assignment_display.short_description = 'Assigned To'