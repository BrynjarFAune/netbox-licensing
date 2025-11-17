# NetBox Licensing Plugin - API Documentation

## Base URL

```
http://your-netbox-instance/api/plugins/licenses/
```

**Important:** Always include the trailing slash `/` in API endpoints or you'll get a 301 redirect.

## Authentication

Use NetBox's token authentication:

```bash
curl -H "Authorization: Token YOUR_API_TOKEN" \
     -H "Content-Type: application/json" \
     http://your-netbox-instance/api/plugins/licenses/licenses/
```

---

## Licenses

**Endpoint:** `/api/plugins/licenses/licenses/`

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | License name |
| `vendor` | integer (FK) | ✅ | Vendor/Manufacturer ID |
| `tenant` | integer (FK) | ❌ | Tenant ID |
| `assignment_types` | array[integer] | ❌ | ContentType IDs for assignable object types |
| `external_id` | string | ❌ | Vendor-specific identifier (SKU, subscription ID, etc.) |
| `total_licenses` | integer | ❌ | Total available seats (default: 1) |
| `billing_cycle` | string | ❌ | `monthly`, `quarterly`, `yearly`, `one_time`, `custom` |
| `payment_method` | string | ❌ | `invoice`, `card_auto`, `card_manual`, `bank_transfer`, `prepaid`, `free_trial` |
| `payment_portal_url` | string (URL) | ❌ | Link to payment/subscription portal |
| `responsible_contact` | integer (FK) | ❌ | Contact ID for responsible person |
| `metadata` | object (JSON) | ❌ | Vendor-specific data |
| `comments` | string | ❌ | Free-form comments |
| `tags` | array | ❌ | Tag IDs or names |

### Read-Only Fields

- `id`, `url`, `display`, `created`, `last_updated`
- `consumed_licenses` - Currently assigned instances (auto-calculated)
- `available_licenses` - Free seats remaining
- `utilization_percentage` - Usage percentage
- `is_active` - Has an active period covering today
- `license_status` - `active`, `expiring_soon`, or `inactive`
- `active_period_per_seat_price` - Per-seat price from active period
- `active_period_total_price` - Total price from active period
- `active_period_currency` - Currency code from active period

### Examples

**List all licenses:**
```bash
GET /api/plugins/licenses/licenses/
```

**Get specific license:**
```bash
GET /api/plugins/licenses/licenses/123/
```

**Create license:**
```bash
POST /api/plugins/licenses/licenses/
Content-Type: application/json

{
  "name": "Microsoft 365 E5",
  "vendor": 5,
  "tenant": 2,
  "total_licenses": 100,
  "billing_cycle": "yearly",
  "payment_method": "invoice",
  "responsible_contact": 10,
  "external_id": "MS-E5-2024",
  "metadata": {
    "features": ["Teams", "SharePoint", "Advanced Security"],
    "max_mailbox_size_gb": 100
  }
}
```

**Update license:**
```bash
PATCH /api/plugins/licenses/licenses/123/
Content-Type: application/json

{
  "total_licenses": 150,
  "comments": "Increased capacity for Q1 2025"
}
```

---

## License Periods

**Endpoint:** `/api/plugins/licenses/license-periods/`

Periods represent paid billing cycles and store pricing snapshots.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `license` | integer (FK) | ✅ | License ID |
| `period_start` | date | ✅ | Start date (YYYY-MM-DD) |
| `period_end` | date | ❌ | End date (null = perpetual) |
| `pricing_mode` | string | ✅ | `per_seat` or `total` |
| `price` | decimal | ✅ | Price in native currency |
| `currency` | integer (FK) | ✅ | CurrencyConversionRate ID |
| `seats_purchased` | integer | ✅ | Number of seats for this period |
| `payment_method` | string | ❌ | Payment method (snapshot from license) |
| `invoice_reference` | string | ❌ | Invoice number |
| `invoice_url` | string (URL) | ❌ | Link to invoice |
| `invoice_file` | file | ❌ | Uploaded invoice PDF/image |
| `comments` | string | ❌ | Notes about this period |
| `tags` | array | ❌ | Tag IDs or names |

### Read-Only Fields

- `id`, `url`, `display`, `created`, `last_updated`
- `price_nok` - Auto-converted NOK price
- `conversion_rate` - Exchange rate used (1 native = X NOK)
- `seats_utilized` - Snapshot of usage when period created
- `current_seats_utilized` - Live count of overlapping instances
- `is_active` - Covers today's date
- `days_remaining` - Days until expiration (null if perpetual)
- `utilization_percentage` - Current usage vs purchased seats
- `total_price` - Total cost (price × seats if per_seat mode)
- `per_seat_price` - Per-seat cost (price ÷ seats if total mode)

### Validation Rules

- `period_end` must be after `period_start`
- Periods for the same license **cannot overlap** (adjacent OK)
- Expired periods cannot be edited (preserves history)

### Examples

**Create period (auto-fill from API):**
```bash
POST /api/plugins/licenses/license-periods/
Content-Type: application/json

{
  "license": 123,
  "period_start": "2025-01-01",
  "period_end": "2025-12-31",
  "pricing_mode": "per_seat",
  "price": "30.00",
  "currency": 2,  # Currency ID (e.g., USD)
  "seats_purchased": 100,
  "payment_method": "invoice",
  "invoice_reference": "INV-2025-001"
}
```

**Create perpetual period:**
```bash
POST /api/plugins/licenses/license-periods/
Content-Type: application/json

{
  "license": 456,
  "period_start": "2024-11-01",
  "period_end": null,  # Perpetual - never expires
  "pricing_mode": "total",
  "price": "5000.00",
  "currency": 1,  # NOK
  "seats_purchased": 50,
  "payment_method": "prepaid"
}
```

**List periods for a license:**
```bash
GET /api/plugins/licenses/license-periods/?license_id=123
```

---

## License Instances

**Endpoint:** `/api/plugins/licenses/license-instances/`

Instances represent individual license assignments to users, devices, or other objects.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `license` | integer (FK) | ✅ | License ID |
| `assigned_object_type` | integer (FK) | ✅ | ContentType ID (e.g., User, Device) |
| `assigned_object_id` | integer | ✅ | ID of the assigned object |
| `start_date` | date | ❌ | Assignment start date (default: today) |
| `end_date` | date | ❌ | Assignment end date (null = active) |
| `comments` | string | ❌ | Assignment notes |
| `tags` | array | ❌ | Tag IDs or names |

### Read-Only Fields

- `id`, `url`, `display`, `created`, `last_updated`
- `assigned_object` - Full object representation (type, id, display)
- `license_price` - Per-seat price from license's active period
- `license_currency` - Currency code from license's active period
- `instance_price_nok` - Price in NOK (auto-converted)
- `is_active` - Assignment is currently active
- `derived_status` - `active`, `pending`, `expired`, or `expiring_soon`

### Examples

**Assign license to user:**
```bash
POST /api/plugins/licenses/license-instances/
Content-Type: application/json

{
  "license": 123,
  "assigned_object_type": 15,  # ContentType for User
  "assigned_object_id": 42,    # User ID
  "start_date": "2024-11-14",
  "comments": "Assigned for new employee onboarding"
}
```

**End an assignment:**
```bash
PATCH /api/plugins/licenses/license-instances/789/
Content-Type: application/json

{
  "end_date": "2025-01-31",
  "comments": "Employee offboarding"
}
```

**List instances for a license:**
```bash
GET /api/plugins/licenses/license-instances/?license_id=123
```

**Filter by status:**
```bash
GET /api/plugins/licenses/license-instances/?status=active
```

**Get assigned object info:**
```json
{
  "id": 789,
  "license": {...},
  "assigned_object": {
    "type": "user",
    "id": 42,
    "display": "john.doe"
  },
  "license_price": "30.00",
  "license_currency": "USD",
  "instance_price_nok": "316.29",
  "is_active": true,
  "derived_status": "active"
}
```

---

## Currency Conversion Rates

**Endpoint:** `/api/plugins/licenses/currency-rates/`

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `currency_code` | string | ✅ | ISO 4217 code (USD, EUR, GBP, etc.) |
| `rate_to_nok` | decimal | ✅ | Exchange rate (1 CURRENCY = X NOK) |
| `source` | string | ❌ | `api` or `manual` (default: api) |
| `notes` | string | ❌ | Optional notes |

### Read-Only Fields

- `id`, `url`, `display`, `created`, `last_updated`
- `is_stale` - Rate older than 7 days
- `can_sync` - Can be updated from API (source=api)

### Examples

**Fetch from Norges Bank API (recommended):**
```bash
POST /api/plugins/licenses/currency-rates/add-api/
Content-Type: application/json

{
  "currency_code": "USD"
}
```

**Manual entry:**
```bash
POST /api/plugins/licenses/currency-rates/
Content-Type: application/json

{
  "currency_code": "USD",
  "rate_to_nok": 10.52,
  "source": "manual",
  "notes": "Fixed rate for Q1 2025"
}
```

---

## Common Patterns

### Get ContentType IDs

```bash
GET /api/extras/content-types/?model=user
GET /api/extras/content-types/?model=device
```

### Bulk Operations

Most endpoints support bulk create/update/delete:

```bash
POST /api/plugins/licenses/license-instances/
Content-Type: application/json

[
  {"license": 123, "assigned_object_type": 15, "assigned_object_id": 1},
  {"license": 123, "assigned_object_type": 15, "assigned_object_id": 2},
  {"license": 123, "assigned_object_type": 15, "assigned_object_id": 3}
]
```

### Filtering & Pagination

```bash
# Filter by multiple fields
GET /api/plugins/licenses/licenses/?vendor_id=5&is_active=true

# Pagination
GET /api/plugins/licenses/licenses/?limit=50&offset=100

# Ordering
GET /api/plugins/licenses/licenses/?ordering=-created
```

---

## Error Responses

### Validation Error (400)
```json
{
  "period_end": ["Period end date must be after start date"],
  "total_licenses": ["Cannot reduce total licenses to 50. There are currently 75 licenses in use."]
}
```

### Not Found (404)
```json
{
  "detail": "Not found."
}
```

### Overlapping Period (400)
```json
{
  "period_start": ["Period overlaps with existing period: 01/01/2025 - 31/12/2025. Periods can be adjacent (ending the same day another starts) but cannot overlap."]
}
```

---

## Tips

1. **Always use trailing slashes** in URLs
2. **Use nested serializers for reads, IDs for writes:**
   - Read: `"vendor": {"id": 5, "name": "Microsoft"}`
   - Write: `"vendor": 5`
3. **Dates use ISO format:** `YYYY-MM-DD`
4. **Currency auto-conversion:** Periods auto-calculate `price_nok` from currency rates
5. **Period validation:** System prevents overlapping periods automatically
6. **Utilization is live:** Period utilization counts overlapping instances in real-time
