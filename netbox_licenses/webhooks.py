# Phase 3: Vendor Integration Webhooks

import json
import logging
from typing import Dict, Any
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.contenttypes.models import ContentType
from .models import License, LicenseInstance, VendorIntegration, LicenseAlert
from .services import ComplianceMonitoringService

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class VendorWebhookView(View):
    """Generic webhook endpoint for vendor integrations"""
    
    def post(self, request, vendor_slug):
        """Handle incoming webhook from vendor"""
        try:
            # Parse JSON payload
            payload = json.loads(request.body.decode('utf-8'))
            
            # Get vendor integration config
            integration = self._get_vendor_integration(vendor_slug)
            if not integration:
                return HttpResponseBadRequest(f"No integration configured for vendor: {vendor_slug}")
            
            # Process webhook based on integration type
            if integration.integration_type == 'microsoft365':
                return self._handle_microsoft365_webhook(payload, integration)
            elif integration.integration_type == 'generic_api':
                return self._handle_generic_webhook(payload, integration)
            else:
                return HttpResponseBadRequest(f"Unsupported integration type: {integration.integration_type}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload received from {vendor_slug}")
            return HttpResponseBadRequest("Invalid JSON payload")
        except Exception as e:
            logger.error(f"Webhook processing failed for {vendor_slug}: {str(e)}")
            return HttpResponseBadRequest(f"Webhook processing failed: {str(e)}")
    
    def _get_vendor_integration(self, vendor_slug):
        """Get vendor integration by slug"""
        try:
            return VendorIntegration.objects.select_related('vendor').get(
                vendor__slug=vendor_slug,
                is_active=True
            )
        except VendorIntegration.DoesNotExist:
            return None
    
    def _handle_microsoft365_webhook(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Handle Microsoft 365 Graph API webhook"""
        event_type = payload.get('changeType', '')
        resource = payload.get('resource', '')
        
        if event_type in ['created', 'updated', 'deleted']:
            if 'subscribedSkus' in resource:
                return self._sync_microsoft365_licenses(payload, integration)
            elif 'users' in resource:
                return self._sync_microsoft365_assignments(payload, integration)
        
        return JsonResponse({'status': 'processed', 'message': f'Event {event_type} processed'})
    
    def _handle_generic_webhook(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Handle generic vendor webhook"""
        event_type = payload.get('event_type', '')
        
        if event_type == 'license_assigned':
            return self._handle_license_assignment(payload, integration)
        elif event_type == 'license_released':
            return self._handle_license_release(payload, integration)
        elif event_type == 'license_expired':
            return self._handle_license_expiration(payload, integration)
        
        return JsonResponse({'status': 'processed', 'message': f'Event {event_type} processed'})
    
    def _sync_microsoft365_licenses(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Sync Microsoft 365 license information"""
        resource_data = payload.get('resourceData', {})
        sku_id = resource_data.get('skuId', '')
        
        if not sku_id:
            return HttpResponseBadRequest("Missing skuId in payload")
        
        # Find matching license by external_id
        try:
            license_obj = License.objects.get(
                vendor=integration.vendor,
                external_id=sku_id
            )
            
            # Update license consumption from Microsoft data
            enabled_units = resource_data.get('consumedUnits', 0)
            total_units = resource_data.get('prepaidUnits', {}).get('enabled', 0)
            
            license_obj.consumed_licenses = enabled_units
            license_obj.total_licenses = total_units
            license_obj.save()
            
            logger.info(f"Updated Microsoft 365 license {license_obj.name}: {enabled_units}/{total_units}")
            
            return JsonResponse({
                'status': 'success',
                'message': f'License {license_obj.name} updated',
                'consumed': enabled_units,
                'total': total_units
            })
            
        except License.DoesNotExist:
            # Create alert for unknown SKU
            LicenseAlert.objects.create(
                license=None,  # No associated license
                alert_type='sync_error',
                severity='medium',
                title=f'Unknown Microsoft 365 SKU: {sku_id}',
                message=f'Received webhook for unknown SKU {sku_id}. Consider adding to NetBox.',
                alert_data={'sku_id': sku_id, 'vendor': integration.vendor.name}
            )
            
            return JsonResponse({
                'status': 'warning',
                'message': f'Unknown SKU {sku_id} - alert created'
            })
    
    def _sync_microsoft365_assignments(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Sync Microsoft 365 user license assignments"""
        resource_data = payload.get('resourceData', {})
        user_id = resource_data.get('id', '')
        assigned_licenses = resource_data.get('assignedLicenses', [])
        
        # Process each assigned license
        for license_info in assigned_licenses:
            sku_id = license_info.get('skuId', '')
            
            try:
                license_obj = License.objects.get(
                    vendor=integration.vendor,
                    external_id=sku_id
                )
                
                # Check if instance exists for this user
                content_type = ContentType.objects.get_for_model(User)  # Assuming User model
                instance, created = LicenseInstance.objects.get_or_create(
                    license=license_obj,
                    assigned_object_type=content_type,
                    assigned_object_id=user_id,
                    defaults={
                        'start_date': timezone.now().date()
                    }
                )
                
                if created:
                    logger.info(f"Created license instance for user {user_id}, license {license_obj.name}")
                
            except License.DoesNotExist:
                logger.warning(f"Received assignment for unknown SKU {sku_id}")
        
        return JsonResponse({'status': 'success', 'message': 'User assignments processed'})
    
    def _handle_license_assignment(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Handle generic license assignment event"""
        license_id = payload.get('license_id', '')
        user_id = payload.get('user_id', '')
        
        if not license_id or not user_id:
            return HttpResponseBadRequest("Missing license_id or user_id")
        
        try:
            license_obj = License.objects.get(
                vendor=integration.vendor,
                external_id=license_id
            )
            
            # Update consumed licenses count
            license_obj.consumed_licenses = license_obj.consumed_licenses + 1
            license_obj.save()
            
            # Check for overallocation
            if license_obj.consumed_licenses > license_obj.total_licenses:
                LicenseAlert.objects.create(
                    license=license_obj,
                    alert_type='overallocated',
                    severity='critical',
                    title=f'License {license_obj.name} overallocated via webhook',
                    message=f'Assignment to {user_id} caused overallocation: {license_obj.consumed_licenses}/{license_obj.total_licenses}',
                    alert_data={'user_id': user_id, 'source': 'webhook'}
                )
            
            return JsonResponse({
                'status': 'success',
                'message': f'License assigned to {user_id}',
                'utilization': f'{license_obj.consumed_licenses}/{license_obj.total_licenses}'
            })
            
        except License.DoesNotExist:
            return HttpResponseBadRequest(f"License {license_id} not found")
    
    def _handle_license_release(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Handle generic license release event"""
        license_id = payload.get('license_id', '')
        user_id = payload.get('user_id', '')
        
        try:
            license_obj = License.objects.get(
                vendor=integration.vendor,
                external_id=license_id
            )
            
            # Update consumed licenses count
            license_obj.consumed_licenses = max(0, license_obj.consumed_licenses - 1)
            license_obj.save()
            
            return JsonResponse({
                'status': 'success',
                'message': f'License released from {user_id}',
                'utilization': f'{license_obj.consumed_licenses}/{license_obj.total_licenses}'
            })
            
        except License.DoesNotExist:
            return HttpResponseBadRequest(f"License {license_id} not found")
    
    def _handle_license_expiration(self, payload: Dict[Any, Any], integration: VendorIntegration):
        """Handle license expiration event"""
        license_id = payload.get('license_id', '')
        expiration_date = payload.get('expiration_date', '')
        
        try:
            license_obj = License.objects.get(
                vendor=integration.vendor,
                external_id=license_id
            )
            
            # Create expiration alert
            LicenseAlert.objects.create(
                license=license_obj,
                alert_type='expired',
                severity='critical',
                title=f'License {license_obj.name} expired',
                message=f'License expired on {expiration_date} (reported via webhook)',
                alert_data={'expiration_date': expiration_date, 'source': 'webhook'}
            )
            
            return JsonResponse({
                'status': 'success',
                'message': f'Expiration processed for license {license_obj.name}'
            })
            
        except License.DoesNotExist:
            return HttpResponseBadRequest(f"License {license_id} not found")


class VendorSyncStatusView(View):
    """API endpoint to check vendor sync status"""
    
    def get(self, request, vendor_slug=None):
        """Get sync status for vendor(s)"""
        if vendor_slug:
            try:
                integration = VendorIntegration.objects.select_related('vendor').get(
                    vendor__slug=vendor_slug
                )
                return JsonResponse(self._get_integration_status(integration))
            except VendorIntegration.DoesNotExist:
                return JsonResponse({'error': f'No integration found for {vendor_slug}'}, status=404)
        else:
            # Get all integrations
            integrations = VendorIntegration.objects.select_related('vendor').all()
            status_data = {
                integration.vendor.slug: self._get_integration_status(integration)
                for integration in integrations
            }
            return JsonResponse(status_data)
    
    def _get_integration_status(self, integration: VendorIntegration) -> Dict:
        """Get detailed status for an integration"""
        return {
            'vendor': integration.vendor.name,
            'integration_type': integration.get_integration_type_display(),
            'is_active': integration.is_active,
            'sync_health': integration.sync_health,
            'last_sync': integration.last_sync.isoformat() if integration.last_sync else None,
            'next_sync': integration.next_sync.isoformat() if integration.next_sync else None,
            'sync_errors': integration.sync_errors,
            'last_error': integration.last_error if integration.sync_errors > 0 else None
        }


# Webhook URL patterns will be added to urls.py
webhook_patterns = [
    # /api/plugins/licenses/webhooks/{vendor_slug}/
    # /api/plugins/licenses/vendor-status/
    # /api/plugins/licenses/vendor-status/{vendor_slug}/
]