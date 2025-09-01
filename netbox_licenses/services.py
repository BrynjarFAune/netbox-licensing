# Phase 3: Business Logic Services

from django.utils import timezone
from django.db.models import Q, F
from datetime import timedelta, date
from typing import List, Dict, Optional
from decimal import Decimal
import logging

from .models import (
    License, LicenseInstance, LicenseRenewal, 
    LicenseAlert, LicenseAnalytics, VendorIntegration,
    CostAllocation
)

logger = logging.getLogger(__name__)


class LicenseLifecycleService:
    """Service for automated license lifecycle management"""
    
    @staticmethod
    def check_expiring_licenses(days_ahead: int = 30) -> List[LicenseInstance]:
        """Find license instances expiring within specified days"""
        cutoff_date = timezone.now().date() + timedelta(days=days_ahead)
        
        return LicenseInstance.objects.filter(
            end_date__lte=cutoff_date,
            end_date__gte=timezone.now().date()
        ).select_related('license', 'license__vendor')
    
    @staticmethod
    def create_renewal_alerts(days_ahead: int = 60):
        """Create renewal alerts for licenses approaching renewal"""
        expiring_instances = LicenseLifecycleService.check_expiring_licenses(days_ahead)
        
        alerts_created = 0
        for instance in expiring_instances:
            # Check if alert already exists
            existing_alert = LicenseAlert.objects.filter(
                license=instance.license,
                alert_type='expiring',
                status='active'
            ).first()
            
            if not existing_alert:
                alert = LicenseAlert.objects.create(
                    license=instance.license,
                    alert_type='expiring',
                    severity='medium' if instance.end_date - timezone.now().date() > timedelta(days=30) else 'high',
                    title=f"License {instance.license.name} expiring soon",
                    message=f"License expires on {instance.end_date}. Renewal required.",
                    alert_data={
                        'instance_id': instance.id,
                        'expiration_date': instance.end_date.isoformat(),
                        'days_remaining': (instance.end_date - timezone.now().date()).days
                    }
                )
                alerts_created += 1
                logger.info(f"Created expiration alert for license {instance.license.name}")
        
        return alerts_created
    
    @staticmethod
    def create_renewal_records():
        """Create renewal records for expiring licenses"""
        # Find licenses with instances expiring in next 90 days that don't have pending renewals
        expiring_instances = LicenseLifecycleService.check_expiring_licenses(90)
        renewals_created = 0
        
        for instance in expiring_instances:
            # Check if renewal record already exists
            existing_renewal = LicenseRenewal.objects.filter(
                license=instance.license,
                status__in=['pending', 'approved', 'in_progress']
            ).first()
            
            if not existing_renewal:
                renewal = LicenseRenewal.objects.create(
                    license=instance.license,
                    renewal_date=instance.end_date - timedelta(days=30),  # Renew 30 days before expiration
                    renewal_cost=instance.license.total_cost,
                    currency=instance.license.currency,
                    notes=f"Auto-generated renewal for expiring instance (ID: {instance.id})"
                )
                renewals_created += 1
                logger.info(f"Created renewal record for license {instance.license.name}")
        
        return renewals_created
    
    @staticmethod
    def process_expired_licenses():
        """Handle expired licenses - create alerts and deactivate if needed"""
        expired_instances = LicenseInstance.objects.filter(
            end_date__lt=timezone.now().date(),
            assigned_object__isnull=False  # Only process assigned instances
        )
        
        processed = 0
        for instance in expired_instances:
            # Create expired alert if not exists
            existing_alert = LicenseAlert.objects.filter(
                license=instance.license,
                alert_type='expired',
                status='active',
                alert_data__instance_id=instance.id
            ).first()
            
            if not existing_alert:
                LicenseAlert.objects.create(
                    license=instance.license,
                    alert_type='expired',
                    severity='critical',
                    title=f"License {instance.license.name} has expired",
                    message=f"License expired on {instance.end_date}. Compliance risk!",
                    alert_data={
                        'instance_id': instance.id,
                        'expiration_date': instance.end_date.isoformat(),
                        'assigned_object': str(instance.assigned_object) if instance.assigned_object else None
                    }
                )
                processed += 1
                logger.warning(f"License {instance.license.name} expired on {instance.end_date}")
        
        return processed


class ComplianceMonitoringService:
    """Service for automated compliance monitoring and alerting"""
    
    @staticmethod
    def check_overallocated_licenses():
        """Find and alert on overallocated licenses"""
        overallocated = License.objects.filter(
            consumed_licenses__gt=F('total_licenses')
        )
        
        alerts_created = 0
        for license in overallocated:
            # Check if alert already exists
            existing_alert = LicenseAlert.objects.filter(
                license=license,
                alert_type='overallocated',
                status='active'
            ).first()
            
            if not existing_alert:
                excess = license.consumed_licenses - license.total_licenses
                LicenseAlert.objects.create(
                    license=license,
                    alert_type='overallocated',
                    severity='critical',
                    title=f"License {license.name} is overallocated",
                    message=f"Using {license.consumed_licenses}/{license.total_licenses} licenses. Excess: {excess}",
                    alert_data={
                        'total_licenses': license.total_licenses,
                        'consumed_licenses': license.consumed_licenses,
                        'excess_licenses': excess,
                        'utilization_percentage': float(license.utilization_percentage)
                    }
                )
                alerts_created += 1
                logger.critical(f"License {license.name} is overallocated by {excess} licenses")
        
        return alerts_created
    
    @staticmethod
    def check_underutilized_licenses(threshold: int = 50):
        """Find underutilized licenses for cost optimization"""
        underutilized = License.objects.filter(
            total_licenses__gt=0,
            consumed_licenses__lt=F('total_licenses') * threshold / 100
        )
        
        alerts_created = 0
        for license in underutilized:
            # Check if alert already exists
            existing_alert = LicenseAlert.objects.filter(
                license=license,
                alert_type='underutilized',
                status='active'
            ).first()
            
            if not existing_alert:
                utilization = license.utilization_percentage
                potential_savings = (license.total_licenses - license.consumed_licenses) * license.price
                
                LicenseAlert.objects.create(
                    license=license,
                    alert_type='underutilized',
                    severity='low',
                    title=f"License {license.name} is underutilized",
                    message=f"Only {utilization:.1f}% utilized. Potential savings: {potential_savings} {license.currency}",
                    alert_data={
                        'utilization_percentage': float(utilization),
                        'unused_licenses': license.available_licenses,
                        'potential_savings': float(potential_savings),
                        'currency': license.currency
                    }
                )
                alerts_created += 1
                logger.info(f"License {license.name} is underutilized at {utilization:.1f}%")
        
        return alerts_created
    
    @staticmethod
    def run_compliance_checks():
        """Run all compliance checks and return summary"""
        results = {
            'overallocated_alerts': ComplianceMonitoringService.check_overallocated_licenses(),
            'underutilized_alerts': ComplianceMonitoringService.check_underutilized_licenses(),
            'expiring_alerts': LicenseLifecycleService.create_renewal_alerts(),
            'expired_processed': LicenseLifecycleService.process_expired_licenses(),
            'renewals_created': LicenseLifecycleService.create_renewal_records(),
            'timestamp': timezone.now()
        }
        
        logger.info(f"Compliance check completed: {results}")
        return results


class AnalyticsService:
    """Service for license analytics and trend analysis"""
    
    @staticmethod
    def record_license_metrics():
        """Record current license metrics for trend analysis"""
        licenses = License.objects.all()
        metrics_recorded = 0
        
        for license in licenses:
            metrics = [
                ('utilization', license.utilization_percentage),
                ('cost', license.total_cost or 0),
                ('instances', license.instances.count()),
                ('available', license.available_licenses),
                ('consumed', license.consumed_licenses),
            ]
            
            # Calculate cost efficiency (licenses per dollar)
            if license.total_cost and license.total_cost > 0:
                efficiency = license.consumed_licenses / float(license.total_cost)
                metrics.append(('efficiency', efficiency))
            
            for metric_type, value in metrics:
                LicenseAnalytics.objects.create(
                    license=license,
                    metric_type=metric_type,
                    metric_value=Decimal(str(value))
                )
                metrics_recorded += 1
        
        logger.info(f"Recorded {metrics_recorded} analytics metrics")
        return metrics_recorded
    
    @staticmethod
    def get_trend_analysis(license: License, metric_type: str, days: int = 30) -> Dict:
        """Get trend analysis for a specific license and metric"""
        cutoff_date = timezone.now() - timedelta(days=days)
        
        analytics = LicenseAnalytics.objects.filter(
            license=license,
            metric_type=metric_type,
            timestamp__gte=cutoff_date
        ).order_by('timestamp')
        
        if not analytics.exists():
            return {'trend': 'no_data', 'change': 0, 'data_points': 0}
        
        values = list(analytics.values_list('metric_value', flat=True))
        
        if len(values) < 2:
            return {'trend': 'insufficient_data', 'change': 0, 'data_points': len(values)}
        
        # Calculate trend
        first_value = float(values[0])
        last_value = float(values[-1])
        change = last_value - first_value
        
        if abs(change) < 0.01:  # Less than 1% change
            trend = 'stable'
        elif change > 0:
            trend = 'increasing'
        else:
            trend = 'decreasing'
        
        return {
            'trend': trend,
            'change': change,
            'change_percentage': (change / first_value * 100) if first_value != 0 else 0,
            'data_points': len(values),
            'first_value': first_value,
            'last_value': last_value,
            'average': sum(float(v) for v in values) / len(values)
        }
    
    @staticmethod
    def get_cost_optimization_recommendations() -> List[Dict]:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        # Find underutilized licenses
        underutilized = License.objects.filter(
            total_licenses__gt=0,
            consumed_licenses__lt=F('total_licenses') * 70 / 100  # Less than 70% utilized
        ).order_by('-total_licenses')
        
        for license in underutilized[:10]:  # Top 10 opportunities
            unused = license.available_licenses
            potential_savings = unused * license.price
            
            recommendations.append({
                'type': 'reduce_licenses',
                'license': license,
                'current_total': license.total_licenses,
                'current_used': license.consumed_licenses,
                'recommended_total': max(license.consumed_licenses + 2, int(license.consumed_licenses * 1.1)),
                'potential_savings': float(potential_savings),
                'priority': 'high' if potential_savings > 1000 else 'medium',
                'description': f"Reduce {license.name} from {license.total_licenses} to {max(license.consumed_licenses + 2, int(license.consumed_licenses * 1.1))} licenses"
            })
        
        return recommendations


class CostAllocationService:
    """Service for automated cost allocation and chargeback"""
    
    @staticmethod
    def calculate_department_costs(department: str, month: Optional[date] = None) -> Dict:
        """Calculate total license costs for a department in a given month"""
        if month is None:
            month = timezone.now().date().replace(day=1)
        
        # Find active allocations for the department in the given month
        allocations = CostAllocation.objects.filter(
            allocation_target=department,
            effective_from__lte=month,
            effective_to__gte=month
        ).select_related('license')
        
        total_cost = Decimal('0.0')
        license_costs = []
        
        for allocation in allocations:
            license_cost = allocation.license.total_cost or Decimal('0.0')
            allocated_cost = license_cost * (allocation.percentage / 100)
            total_cost += allocated_cost
            
            license_costs.append({
                'license': allocation.license,
                'total_cost': float(license_cost),
                'percentage': float(allocation.percentage),
                'allocated_cost': float(allocated_cost)
            })
        
        return {
            'department': department,
            'month': month,
            'total_cost': float(total_cost),
            'license_breakdown': license_costs,
            'license_count': len(license_costs)
        }
    
    @staticmethod
    def auto_allocate_unassigned_licenses():
        """Automatically allocate licenses that don't have cost allocations"""
        unallocated_licenses = License.objects.filter(
            cost_allocations__isnull=True
        )
        
        allocations_created = 0
        for license in unallocated_licenses:
            # Simple rule: allocate to IT department by default
            CostAllocation.objects.create(
                license=license,
                allocation_type='department',
                allocation_target='IT',
                percentage=Decimal('100.00'),
                effective_from=timezone.now().date(),
                allocation_rules={
                    'auto_allocated': True,
                    'reason': 'No specific allocation defined'
                }
            )
            allocations_created += 1
        
        return allocations_created