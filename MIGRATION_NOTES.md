# Database Migration Required

## Change Summary
1. Making `total_licenses` field optional to support undefined capacity licenses
2. Adding individual instance pricing fields to LicenseInstance model (for per-user subscriptions)

## Migration Command
Run this on the NetBox server after deploying the code:

```bash
cd netbox-docker
docker compose exec netbox python manage.py makemigrations netbox_licenses
docker compose exec netbox python manage.py migrate netbox_licenses
```

## Expected Migration Changes

The migration will modify two tables:

### 1. `netbox_licenses_license` table
```python
migrations.AlterField(
    model_name='license',
    name='total_licenses',
    field=models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Total available license slots purchased (leave blank if undefined/not applicable)'
    ),
)
```

### 2. `netbox_licenses_licenseinstance` table
```python
migrations.AddField(
    model_name='licenseinstance',
    name='individual_price',
    field=models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True),
),
migrations.AddField(
    model_name='licenseinstance',
    name='individual_currency',
    field=models.ForeignKey(to='netbox_licenses.CurrencyConversionRate', null=True, blank=True),
),
migrations.AddField(
    model_name='licenseinstance',
    name='billing_start',
    field=models.DateField(null=True, blank=True),
),
migrations.AddField(
    model_name='licenseinstance',
    name='billing_end',
    field=models.DateField(null=True, blank=True),
),
```

## SQL Changes (PostgreSQL)
The migration will execute approximately:

```sql
-- License table: Make total_licenses nullable
ALTER TABLE "netbox_licenses_license"
ALTER COLUMN "total_licenses" DROP NOT NULL;

ALTER TABLE "netbox_licenses_license"
ALTER COLUMN "total_licenses" DROP DEFAULT;

-- LicenseInstance table: Add individual pricing columns
ALTER TABLE "netbox_licenses_licenseinstance"
ADD COLUMN "individual_price" NUMERIC(12, 2) NULL;

ALTER TABLE "netbox_licenses_licenseinstance"
ADD COLUMN "individual_currency_id" VARCHAR(3) NULL REFERENCES "netbox_licenses_currencyconversionrate"("currency_code");

ALTER TABLE "netbox_licenses_licenseinstance"
ADD COLUMN "billing_start" DATE NULL;

ALTER TABLE "netbox_licenses_licenseinstance"
ADD COLUMN "billing_end" DATE NULL;
```

## Data Impact
- **Existing Licenses**: All existing licenses will retain their current `total_licenses` values
- **Existing Instances**: All existing instances will have NULL for new pricing fields (will use license/period pricing as before)
- **New Licenses**: Can now be created with `total_licenses = NULL` (undefined capacity)
- **New Instances**: Can optionally include individual pricing for per-user subscriptions
- **No Data Loss**: This is a non-destructive, backward-compatible change

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
