# Database Structure

## License Model

| Field Name | Type | Input Type | Mandatory | Storage | Description |
|------------|------|------------|-----------|---------|-------------|
| **id** | AutoField | - | Yes | DB | Primary key (auto-generated) |
| **name** | CharField(50) | Text | Yes | DB | License name |
| **vendor** | ForeignKey(Manufacturer) | Select | Yes | DB | Vendor/manufacturer |
| **tenant** | ForeignKey(Tenant) | Select | Yes | DB | Tenant owner |
| **assignment_type** | ForeignKey(ContentType) | Select | Yes | DB | What type of object licenses assign to |
| **price** | DecimalField(10,2) | Number | Yes | DB | Unit price per license |
| **currency** | CharField(3) | Select | Yes | DB | Currency code (NOK, USD, EUR, etc.) |
| **external_id** | CharField(255) | Text | No | DB | Vendor SKU/subscription ID |
| **total_licenses** | PositiveIntegerField | Number | Yes | DB | Total capacity purchased |
| **consumed_licenses** | PositiveIntegerField | Number | Yes | DB | Currently assigned (auto-calculated) |
| **metadata** | JSONField | JSON | No | DB | Vendor-specific data |
| **billing_cycle** | CharField(20) | Select | Yes | DB | monthly/quarterly/yearly/one_time/custom |
| **auto_renew** | BooleanField | Checkbox | Yes | DB | Auto-renew flag (deprecated) |
| **payment_method** | CharField(30) | Select | Yes | DB | invoice/card_auto/card_manual/etc. |
| **payment_portal_url** | URLField(500) | URL | No | DB | Link to payment portal |
| **responsible_contact** | ForeignKey(Contact) | Select | No | DB | Person responsible for license |
| **total_instances** | PositiveIntegerField | Number | Yes | DB | Legacy field |
| **comments** | TextField | Textarea | No | DB | Free-form notes |
| **tags** | ManyToManyField | Tags | No | DB | NetBox tags |
| **created** | DateTimeField | - | Yes | DB | Auto-generated creation timestamp |
| **last_updated** | DateTimeField | - | Yes | DB | Auto-updated modification timestamp |
| **custom_fields** | JSONField | - | No | DB | NetBox custom fields |
| **available_licenses** | Property | - | - | Calculated | total_licenses - consumed_licenses |
| **utilization_percentage** | Property | - | - | Calculated | (consumed / total) × 100 |
| **monthly_equivalent_price** | Property | - | - | Calculated | Price normalized to monthly |
| **annual_equivalent_price** | Property | - | - | Calculated | monthly_equivalent_price × 12 |
| **total_monthly_commitment** | Property | - | - | Calculated | monthly_equivalent × total_licenses |
| **total_yearly_commitment** | Property | - | - | Calculated | annual_equivalent × total_licenses |
| **total_monthly_commitment_nok** | Property | - | - | Calculated | Converted to NOK with conversion rates |
| **total_yearly_commitment_nok** | Property | - | - | Calculated | total_monthly_commitment_nok × 12 |
| **total_cost** | CachedProperty | - | - | Calculated | Sum of all instance prices (legacy) |
| **price_display** | Property | - | - | Calculated | Formatted price with currency |

## LicenseInstance Model

| Field Name | Type | Input Type | Mandatory | Storage | Description |
|------------|------|------------|-----------|---------|-------------|
| **id** | AutoField | - | Yes | DB | Primary key (auto-generated) |
| **license** | ForeignKey(License) | Select | Yes | DB | Parent license |
| **assigned_object_type** | ForeignKey(ContentType) | - | Yes | DB | GenericForeignKey content type |
| **assigned_object_id** | PositiveIntegerField | - | Yes | DB | GenericForeignKey object ID |
| **assigned_object** | GenericForeignKey | Dynamic Select | Yes | Virtual | The actual assigned object (device/VM/user/etc.) |
| **start_date** | DateField | Date | No | DB | License activation date |
| **end_date** | DateField | Date | No | DB | License expiration date |
| **comments** | TextField | Textarea | No | DB | Free-form notes |
| **tags** | ManyToManyField | Tags | No | DB | NetBox tags |
| **created** | DateTimeField | - | Yes | DB | Auto-generated creation timestamp |
| **last_updated** | DateTimeField | - | Yes | DB | Auto-updated modification timestamp |
| **custom_fields** | JSONField | - | No | DB | NetBox custom fields |
| **license_currency** | Property | - | - | Calculated | Currency from parent license |
| **license_price** | Property | - | - | Calculated | Unit price from parent license |
| **instance_price_nok** | Property | - | - | Calculated | Price in NOK (simplified, returns 0 for non-NOK) |
| **display_price** | Property | - | - | Calculated | Formatted price display |
| **derived_status** | Property | - | - | Calculated | active/pending/warning/expired based on dates |
| **get_derived_status_class** | Property | - | - | Calculated | CSS class for status badge |
| **is_available** | Property | - | - | Calculated | Whether instance is unassigned and not expired |
| **assigned_object_str** | Property | - | - | Calculated | String representation for sorting |
| **assignment_type** | Property | - | - | Calculated | Model name of assigned object type |
| **renewal_status** | Property | - | - | Calculated | Renewal status considering payment method |
| **monthly_cost_contribution** | Property | - | - | Calculated | Monthly cost from parent license |
| **is_auto_renewing** | Property | - | - | Calculated | Whether instance auto-renews (from license) |

## Key Relationships

- **License → LicenseInstance**: One-to-Many via `instances` related name
- **License → Manufacturer**: Many-to-One via `vendor` 
- **License → Tenant**: Many-to-One via `tenant`
- **License → Contact**: Many-to-One via `responsible_contact`
- **LicenseInstance → License**: Many-to-One via `license`
- **LicenseInstance → Any Object**: GenericForeignKey via `assigned_object`

## Removed Fields (Migration 0005)

### Removed from LicenseInstance:
- `auto_renew` - Moved to License model
- `price_override` - No longer needed
- `currency_override` - No longer needed  
- `nok_price_override` - Replaced by parent license pricing

### Deprecated in License:
- `auto_renew` - Replaced by `payment_method` field
