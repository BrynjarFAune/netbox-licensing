# Generated migration for NetBox Licenses Plugin

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('dcim', '0001_initial'),
        ('tenancy', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='License',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('name', models.CharField(max_length=30)),
                ('price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('comments', models.TextField(blank=True)),
                ('assignment_type', models.ForeignKey(help_text='What object type will the license be assigned to', limit_choices_to={'model__in': ['contact', 'device', 'virtualmachine', 'tenant', 'service']}, on_delete=django.db.models.deletion.PROTECT, to='contenttypes.contenttype')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='licenses', to='tenancy.tenant')),
                ('vendor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='licenses', to='dcim.manufacturer')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LicenseInstance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=None)),
                ('assigned_object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('price_override', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('comments', models.TextField(blank=True)),
                ('assigned_object_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='contenttypes.contenttype')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instances', to='netbox_licenses.license')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddConstraint(
            model_name='license',
            constraint=models.UniqueConstraint(fields=['name', 'vendor', 'tenant'], name='unique_license_key'),
        ),
    ]