"""
Management command for license optimization recommendations
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from netbox_licenses.services import AnalyticsService, CostAllocationService
from netbox_licenses.models import License
from decimal import Decimal


class Command(BaseCommand):
    help = 'Generate comprehensive license optimization report with cost savings recommendations'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            choices=['text', 'json', 'csv'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--min-savings',
            type=float,
            default=100.0,
            help='Minimum potential savings to include in report (default: 100 NOK)',
        )
        
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                f'🔍 Generating License Optimization Report - {timezone.now().strftime("%Y-%m-%d %H:%M")}'
            )
        )
        
        # Get optimization recommendations
        recommendations = AnalyticsService.get_cost_optimization_recommendations()
        
        # Filter by minimum savings
        min_savings = Decimal(str(options['min_savings']))
        filtered_recommendations = [
            rec for rec in recommendations 
            if rec['potential_savings'] >= float(min_savings)
        ]
        
        # Calculate totals
        total_potential_savings = sum(rec['potential_savings'] for rec in filtered_recommendations)
        total_licenses_reviewed = License.objects.count()
        
        # Output results
        if options['format'] == 'text':
            self._output_text_report(filtered_recommendations, total_potential_savings, total_licenses_reviewed)
        elif options['format'] == 'json':
            self._output_json_report(filtered_recommendations, total_potential_savings, total_licenses_reviewed)
        elif options['format'] == 'csv':
            self._output_csv_report(filtered_recommendations)
    
    def _output_text_report(self, recommendations, total_savings, total_licenses):
        """Output human-readable text report"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write(f"📊 LICENSE OPTIMIZATION REPORT")
        self.stdout.write("="*80)
        
        self.stdout.write(f"📋 Total licenses analyzed: {total_licenses}")
        self.stdout.write(f"💰 Total potential savings: {total_savings:,.2f} NOK")
        self.stdout.write(f"🎯 Optimization opportunities: {len(recommendations)}")
        
        if not recommendations:
            self.stdout.write(
                self.style.SUCCESS("✅ No significant optimization opportunities found!")
            )
            return
        
        self.stdout.write("\n🔍 TOP OPTIMIZATION OPPORTUNITIES:")
        self.stdout.write("-" * 80)
        
        for i, rec in enumerate(recommendations[:10], 1):  # Top 10
            license = rec['license']
            savings = rec['potential_savings']
            current = rec['current_total']
            recommended = rec['recommended_total']
            
            self.stdout.write(f"\n{i:2d}. {license.name}")
            self.stdout.write(f"    Vendor: {license.vendor.name}")
            self.stdout.write(f"    Current: {current} licenses | Recommended: {recommended} licenses")
            self.stdout.write(f"    💰 Potential savings: {savings:,.2f} NOK")
            
            if rec['priority'] == 'high':
                self.stdout.write(f"    🔴 Priority: {rec['priority'].upper()}")
            else:
                self.stdout.write(f"    🟡 Priority: {rec['priority']}")
        
        # Summary recommendations
        self.stdout.write("\n" + "="*80)
        self.stdout.write("💡 RECOMMENDATIONS:")
        self.stdout.write("="*80)
        
        high_priority = [r for r in recommendations if r['priority'] == 'high']
        if high_priority:
            high_savings = sum(r['potential_savings'] for r in high_priority)
            self.stdout.write(f"🔴 Immediate action: {len(high_priority)} high-priority items")
            self.stdout.write(f"   Could save {high_savings:,.2f} NOK (~{high_savings/12:,.2f} NOK/month)")
        
        self.stdout.write(f"📈 Review utilization monthly to maintain optimization")
        self.stdout.write(f"🔄 Consider auto-scaling for dynamic license allocation")
        
    def _output_json_report(self, recommendations, total_savings, total_licenses):
        """Output JSON format for API consumption"""
        import json
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_licenses': total_licenses,
                'total_potential_savings': float(total_savings),
                'opportunities_count': len(recommendations)
            },
            'recommendations': []
        }
        
        for rec in recommendations:
            report['recommendations'].append({
                'license_id': rec['license'].id,
                'license_name': rec['license'].name,
                'vendor': rec['license'].vendor.name,
                'current_total': rec['current_total'],
                'current_used': rec['current_used'],
                'recommended_total': rec['recommended_total'],
                'potential_savings': rec['potential_savings'],
                'priority': rec['priority'],
                'description': rec['description']
            })
        
        self.stdout.write(json.dumps(report, indent=2))
    
    def _output_csv_report(self, recommendations):
        """Output CSV format for spreadsheet analysis"""
        import csv
        import sys
        
        writer = csv.writer(sys.stdout)
        writer.writerow([
            'License Name', 'Vendor', 'Current Total', 'Current Used',
            'Recommended Total', 'Potential Savings (NOK)', 'Priority', 'Description'
        ])
        
        for rec in recommendations:
            writer.writerow([
                rec['license'].name,
                rec['license'].vendor.name,
                rec['current_total'],
                rec['current_used'],
                rec['recommended_total'],
                f"{rec['potential_savings']:.2f}",
                rec['priority'],
                rec['description']
            ])