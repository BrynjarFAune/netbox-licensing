# NetBox Licensing Plugin - API Documentation

**Base URL:** `/api/plugins/licenses/`
**Auth:** Token header `Authorization: Token YOUR_API_TOKEN`
**CRITICAL:** Always include trailing slash `/` - POST/PATCH/DELETE will 500 error without it

---

## Licenses

**Endpoint:** `/api/plugins/licenses/licenses/`

### Required Fields
- `name` (string) - License name
- `vendor` (int) - Vendor/Manufacturer ID

### Optional Fields
- `tenant` (int), `assignment_type` (int - ContentType ID), `external_id` (string)
- `total_licenses` (int, default: 1), `billing_cycle` (string), `payment_method` (string)
- `payment_portal_url` (URL), `responsible_contact` (int - Contact ID), `metadata` (JSON)
- `comments` (string), `tags` (array)

### Read-Only
- `consumed_licenses`, `available_licenses`, `utilization_percentage`
- `is_active`, `license_status`, `active_period_per_seat_price`, `active_period_currency`

### Examples

```bash
# Create
POST /api/plugins/licenses/licenses/
{"name": "Microsoft 365", "vendor": 5, "total_licenses": 100}

# Update
PATCH /api/plugins/licenses/licenses/123/
{"total_licenses": 150}

# List
GET /api/plugins/licenses/licenses/?vendor_id=5
```

---

## License Periods

**Endpoint:** `/api/plugins/licenses/license-periods/`

Periods are billing cycles that store pricing snapshots.

### Required Fields
- `license` (int) - License ID
- `period_start` (date) - YYYY-MM-DD format
- `pricing_mode` (string) - `per_seat` or `total`
- `price` (decimal) - Price in native currency
- `currency` (string) - Currency code (e.g., "USD", "EUR", "NOK")
- `seats_purchased` (int) - Number of seats
- `payment_method` (string) - Payment method choice

### Optional Fields
- `period_end` (date, null = perpetual)
- `invoice_reference`, `invoice_url`, `invoice_file`
- `comments`, `tags`

### Read-Only
- `price_nok`, `conversion_rate`, `current_seats_utilized`, `utilization_percentage`
- `is_active`, `days_remaining`, `total_price`, `per_seat_price`
- `per_seat_price_nok`, `total_price_nok`, `name` (formatted display name)

### Validation
- `period_end` must be after `period_start`
- Periods cannot overlap (adjacent OK)
- Expired periods cannot be edited

### Examples

```bash
# Create period
POST /api/plugins/licenses/license-periods/
{
  "license": 123,
  "period_start": "2025-01-01",
  "period_end": "2025-12-31",
  "pricing_mode": "per_seat",
  "price": "30.00",
  "currency": "USD",
  "seats_purchased": 100,
  "payment_method": "invoice"
}

# Perpetual license
POST /api/plugins/licenses/license-periods/
{
  "license": 456,
  "period_start": "2024-11-01",
  "period_end": null,
  "pricing_mode": "total",
  "price": "5000.00",
  "currency": "NOK",
  "seats_purchased": 50,
  "payment_method": "prepaid"
}
```

---

## License Instances

**Endpoint:** `/api/plugins/licenses/license-instances/`

Instances assign licenses to users, devices, or other objects.

### Required Fields
- `license` (int) - License ID
- `assigned_object_type` (int) - ContentType ID
- `assigned_object_id` (int) - Assigned object's ID

### Optional Fields
- `start_date` (date, default: today)
- `end_date` (date, null = active)
- `comments`, `tags`

### Read-Only
- `assigned_object` (full representation)
- `license_price`, `license_currency`, `instance_price_nok`
- `is_active`, `derived_status`

### Examples

```bash
# Assign to user
POST /api/plugins/licenses/license-instances/
{
  "license": 123,
  "assigned_object_type": 15,  # User ContentType
  "assigned_object_id": 42,
  "start_date": "2024-11-14"
}

# End assignment
PATCH /api/plugins/licenses/license-instances/789/
{"end_date": "2025-01-31"}

# Get ContentType IDs
GET /api/extras/content-types/?model=user
GET /api/extras/content-types/?model=device
```

---

## Currency Rates

**Endpoint:** `/api/plugins/licenses/currency-rates/`

```bash
# Fetch from API (recommended)
POST /api/plugins/licenses/currency-rates/add-api/
{"currency_code": "USD"}

# Manual entry
POST /api/plugins/licenses/currency-rates/
{"currency_code": "USD", "rate_to_nok": 10.52, "source": "manual"}
```

---

## Common Patterns

**Bulk create:**
```bash
POST /api/plugins/licenses/license-instances/
[
  {"license": 123, "assigned_object_type": 15, "assigned_object_id": 1},
  {"license": 123, "assigned_object_type": 15, "assigned_object_id": 2}
]
```

**Filtering:**
```bash
GET /api/plugins/licenses/licenses/?vendor_id=5&is_active=true
GET /api/plugins/licenses/license-instances/?license_id=123&status=active
```

**Pagination:**
```bash
GET /api/plugins/licenses/licenses/?limit=50&offset=100&ordering=-created
```

---

## Tips

- **Dates:** Use `YYYY-MM-DD` format
- **Nested reads, ID writes:** Response has nested objects, requests use IDs
- **Auto-conversion:** Periods auto-calculate `price_nok` from currency rates
- **Auto-currency fetch:** When creating a period with a new currency code, it automatically fetches the rate from Norges Bank API
- **Live utilization:** Period utilization counts overlapping instances in real-time
- **Name property:** License periods have a computed `name` field showing "License Name (DD/MM/YYYY - DD/MM/YYYY)"
