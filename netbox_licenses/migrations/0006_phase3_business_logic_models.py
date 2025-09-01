# Generated manually for Phase 3 business logic models
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('dcim', '0002_auto_20160622_1821'),
        ('netbox_licenses', '0005_license_enhancement_fields'),
    ]

    operations = [
        # Add Phase 3 models
        migrations.CreateModel(
            name='LicenseRenewal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('tags', models.ManyToManyField(blank=True, related_name='+', to='extras.tag')),
                ('renewal_date', models.DateField(help_text='Date when license needs to be renewed')),
                ('new_end_date', models.DateField(blank=True, help_text='New expiration date after renewal', null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('requested_by', models.CharField(blank=True, max_length=100)),
                ('approved_by', models.CharField(blank=True, max_length=100)),
                ('approval_date', models.DateTimeField(blank=True, null=True)),
                ('renewal_cost', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('currency', models.CharField(choices=[('USD', 'US Dollar'), ('EUR', 'Euro'), ('GBP', 'British Pound'), ('NOK', 'Norwegian Krone'), ('DKK', 'Danish Krone'), ('SEK', 'Swedish Krona')], default='NOK', max_length=3)),
                ('budget_approved', models.BooleanField(default=False)),
                ('budget_code', models.CharField(blank=True, max_length=50)),
                ('workflow_data', models.JSONField(blank=True, default=dict, help_text='Workflow-specific data and approval history')),
                ('notes', models.TextField(blank=True)),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='renewals', to='netbox_licenses.license')),
            ],
            options={
                'ordering': ['-renewal_date'],
            },
        ),
        migrations.CreateModel(
            name='VendorIntegration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('tags', models.ManyToManyField(blank=True, related_name='+', to='extras.tag')),
                ('integration_type', models.CharField(choices=[('microsoft365', 'Microsoft 365 Graph API'), ('generic_api', 'Generic REST API'), ('webhook', 'Webhook Integration'), ('csv_import', 'CSV Import'), ('ldap', 'LDAP/Active Directory')], max_length=50)),
                ('api_endpoint', models.URLField(blank=True)),
                ('api_credentials', models.JSONField(blank=True, default=dict, help_text='Encrypted API credentials and configuration')),
                ('sync_schedule', models.CharField(choices=[('hourly', 'Every Hour'), ('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('manual', 'Manual Only')], default='daily', max_length=20)),
                ('last_sync', models.DateTimeField(blank=True, null=True)),
                ('next_sync', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('sync_errors', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('field_mappings', models.JSONField(blank=True, default=dict, help_text='Field mapping configuration between vendor and NetBox')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='integrations', to='dcim.manufacturer')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LicenseAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(choices=[('utilization', 'Utilization Percentage'), ('cost', 'Total Cost'), ('instances', 'Instance Count'), ('available', 'Available Licenses'), ('consumed', 'Consumed Licenses'), ('efficiency', 'Cost Efficiency')], max_length=20)),
                ('metric_value', models.DecimalField(decimal_places=2, max_digits=12)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional metric context and dimensions')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='netbox_licenses.license')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='LicenseAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('tags', models.ManyToManyField(blank=True, related_name='+', to='extras.tag')),
                ('alert_type', models.CharField(choices=[('expiring', 'License Expiring Soon'), ('expired', 'License Expired'), ('overallocated', 'License Overallocated'), ('underutilized', 'License Underutilized'), ('renewal_due', 'Renewal Due'), ('budget_exceeded', 'Budget Exceeded'), ('compliance_violation', 'Compliance Violation'), ('sync_error', 'Vendor Sync Error')], max_length=30)),
                ('severity', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('critical', 'Critical')], max_length=10)),
                ('status', models.CharField(choices=[('active', 'Active'), ('acknowledged', 'Acknowledged'), ('resolved', 'Resolved'), ('suppressed', 'Suppressed')], default='active', max_length=15)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('triggered_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('alert_data', models.JSONField(blank=True, default=dict, help_text='Alert-specific data and context')),
                ('notifications_sent', models.PositiveIntegerField(default=0)),
                ('last_notification', models.DateTimeField(blank=True, null=True)),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='netbox_licenses.license')),
            ],
            options={
                'ordering': ['-triggered_at'],
            },
        ),
        migrations.CreateModel(
            name='CostAllocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict)),
                ('tags', models.ManyToManyField(blank=True, related_name='+', to='extras.tag')),
                ('allocation_type', models.CharField(choices=[('department', 'Department'), ('project', 'Project'), ('cost_center', 'Cost Center'), ('business_unit', 'Business Unit')], max_length=20)),
                ('allocation_target', models.CharField(help_text='Department/project/cost center identifier', max_length=100)),
                ('percentage', models.DecimalField(decimal_places=2, help_text='Percentage of license cost allocated (0-100)', max_digits=5)),
                ('effective_from', models.DateField()),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('allocation_rules', models.JSONField(blank=True, default=dict, help_text='Rules and criteria for this allocation')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cost_allocations', to='netbox_licenses.license')),
            ],
            options={
                'ordering': ['-effective_from'],
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='licenseanalytics',
            index=models.Index(fields=['license', 'metric_type', '-timestamp'], name='netbox_lice_license_db5a63_idx'),
        ),
        migrations.AddIndex(
            model_name='licenseanalytics',
            index=models.Index(fields=['timestamp'], name='netbox_lice_timesta_aa1e3d_idx'),
        ),
        migrations.AddIndex(
            model_name='licensealert',
            index=models.Index(fields=['status', '-triggered_at'], name='netbox_lice_status_5b8aab_idx'),
        ),
        migrations.AddIndex(
            model_name='licensealert',
            index=models.Index(fields=['alert_type', 'severity'], name='netbox_lice_alert_t_1e47f4_idx'),
        ),
        # Add unique constraints
        migrations.AddConstraint(
            model_name='costallocation',
            constraint=models.UniqueConstraint(fields=['license', 'allocation_target', 'effective_from'], name='netbox_lice_license_f17c06_uniq'),
        ),
    ]