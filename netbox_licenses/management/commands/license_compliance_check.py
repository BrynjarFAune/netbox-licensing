"""
Management command for automated license compliance monitoring
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from netbox_licenses.services import ComplianceMonitoringService, LicenseLifecycleService, AnalyticsService


class Command(BaseCommand):
    help = 'Run comprehensive license compliance checks and generate alerts'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-renewals',
            action='store_true',
            help='Create renewal records for expiring licenses',
        )
        parser.add_argument(
            '--record-metrics',
            action='store_true', 
            help='Record analytics metrics for trend analysis',
        )
        parser.add_argument(
            '--underutilized-threshold',
            type=int,
            default=50,
            help='Utilization threshold for underutilized alerts (default: 50%)',
        )
        
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'Starting license compliance check at {timezone.now()}'
            )
        )
        
        try:
            # Run all compliance checks
            results = ComplianceMonitoringService.run_compliance_checks()
            
            # Display results
            self.stdout.write(f"✅ Overallocation alerts created: {results['overallocated_alerts']}")
            self.stdout.write(f"⚠️  Underutilized alerts created: {results['underutilized_alerts']}")
            self.stdout.write(f"📅 Expiration alerts created: {results['expiring_alerts']}")
            self.stdout.write(f"💀 Expired licenses processed: {results['expired_processed']}")
            self.stdout.write(f"🔄 Renewal records created: {results['renewals_created']}")
            
            # Create additional renewal records if requested
            if options['create_renewals']:
                additional_renewals = LicenseLifecycleService.create_renewal_records()
                self.stdout.write(f"📝 Additional renewal records: {additional_renewals}")
            
            # Record analytics metrics if requested
            if options['record_metrics']:
                metrics_recorded = AnalyticsService.record_license_metrics()
                self.stdout.write(f"📊 Analytics metrics recorded: {metrics_recorded}")
            
            # Summary
            total_alerts = (
                results['overallocated_alerts'] + 
                results['underutilized_alerts'] + 
                results['expiring_alerts']
            )
            
            if total_alerts > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  {total_alerts} total alerts created - review recommended'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('✅ All licenses compliant - no alerts created')
                )
                
        except Exception as e:
            raise CommandError(f'Compliance check failed: {str(e)}')