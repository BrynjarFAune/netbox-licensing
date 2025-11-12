# Generated migration for assignment_type to assignment_types conversion

from django.db import migrations, models


def migrate_assignment_type_to_types(apps, schema_editor):
    """Migrate existing single assignment_type values to the new ManyToMany field"""
    License = apps.get_model('netbox_licenses', 'License')

    for license in License.objects.all():
        if hasattr(license, 'assignment_type') and license.assignment_type:
            # Add the old single assignment_type to the new ManyToMany field
            license.assignment_types.add(license.assignment_type)


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_licenses', '0001_initial_complete'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # Add new ManyToMany field
        migrations.AddField(
            model_name='license',
            name='assignment_types',
            field=models.ManyToManyField(
                blank=True,
                help_text='What object types can be assigned to this license',
                related_name='licenses_by_type',
                to='contenttypes.contenttype'
            ),
        ),
        # Migrate data from old field to new field
        migrations.RunPython(migrate_assignment_type_to_types, migrations.RunPython.noop),
        # Remove old ForeignKey field
        migrations.RemoveField(
            model_name='license',
            name='assignment_type',
        ),
    ]
