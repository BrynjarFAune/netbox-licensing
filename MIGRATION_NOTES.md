# Database Migration Required

## Change Summary
Making `total_licenses` field optional to support unlimited licenses.

## Migration Command
Run this on the NetBox server after deploying the code:

```bash
cd netbox-docker
docker compose exec netbox python manage.py makemigrations netbox_licenses
docker compose exec netbox python manage.py migrate netbox_licenses
```

## Expected Migration Changes

The migration will modify the `netbox_licenses_license` table:

```python
# Generated migration (approximate)
operations = [
    migrations.AlterField(
        model_name='license',
        name='total_licenses',
        field=models.PositiveIntegerField(
            blank=True,
            null=True,
            help_text='Total available license slots purchased (leave blank for unlimited licenses)'
        ),
    ),
]
```

## SQL Changes (PostgreSQL)
The migration will execute approximately:

```sql
-- Make column nullable
ALTER TABLE "netbox_licenses_license"
ALTER COLUMN "total_licenses" DROP NOT NULL;

-- Update default (removes default value)
ALTER TABLE "netbox_licenses_license"
ALTER COLUMN "total_licenses" DROP DEFAULT;
```

## Data Impact
- **Existing Records**: All existing licenses will retain their current `total_licenses` values
- **New Records**: Can now be created with `total_licenses = NULL` (unlimited)
- **No Data Loss**: This is a non-destructive change

## Validation Steps
After migration:

1. Check existing licenses still display correctly:
   ```bash
   docker compose exec netbox python manage.py shell
   >>> from netbox_licenses.models import License
   >>> License.objects.first().total_licenses  # Should show existing value
   ```

2. Test creating an unlimited license via UI:
   - Navigate to Licenses > Add
   - Leave "Seats" field blank
   - Save and verify it shows "unlimited" badge

3. Test API:
   ```bash
   curl -X GET http://10.0.123.5:8000/api/plugins/licenses/licenses/ \
     -H "Authorization: Token YOUR_TOKEN"
   ```

## Rollback Plan
If issues occur, rollback by:

```bash
docker compose exec netbox python manage.py migrate netbox_licenses <previous_migration_number>
```

Then revert code changes and redeploy.

## Testing Checklist
- [ ] Migration runs without errors
- [ ] Existing licenses retain their values
- [ ] Can create new unlimited licenses (seats = blank)
- [ ] Can create new limited licenses (seats = number)
- [ ] Utilization calculations work correctly
- [ ] API returns correct data for both types
- [ ] Cost reports handle unlimited licenses
- [ ] Alerts skip unlimited licenses appropriately
