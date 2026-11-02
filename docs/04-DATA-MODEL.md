# 04 — Draft Data Model

**Status: DRAFT — not approved, not implemented.** Framework-agnostic on purpose; see
[05-DECISIONS.md](05-DECISIONS.md) D-002. Field names follow the FBR payload where possible so
the mapping layer stays thin.

---

## Design principles
1. **The local invoice is the source of truth; the FBR IRN is an attribute of it.** The app
   must work when FBR is unreachable.
2. **Never mutate a posted invoice.** Corrections are debit/credit notes.
3. **Store the FBR request and response verbatim.** Not parsed fields — the raw JSON.
4. **Reference data is cached, versioned, and refreshable** — provinces, HS codes, UoM, rates.
5. **Decimal for money.** Never float.

---

## Entities

### `SellerProfile` (one row — the business itself)
| Field | Notes |
|---|---|
| `ntn_cnic` | 7 or 13 digits |
| `strn` | Sales tax registration number |
| `business_name` | |
| `province` | Must match `provinces` reference |
| `address` | |
| `business_activity` | Manufacturer / Importer / Distributor / Wholesaler / Exporter / Retailer / Service Provider / Other — **drives the scenario set** |
| `sector` | Drives the scenario set alongside activity |
| `is_retailer` | Gates SN026–SN028 |

### `ApiCredential`
| Field | Notes |
|---|---|
| `environment` | `sandbox` / `production` |
| `token` | **Encrypted at rest.** Never logged, never in git |
| `issued_on`, `expires_on` | 5-year validity — warn 90 days out |
| `is_active` | |

### `Customer`
| Field | Notes |
|---|---|
| `ntn_cnic` | Optional when unregistered |
| `business_name`, `province`, `address` | |
| `registration_type` | `Registered` / `Unregistered` — prefill via `Get_Reg_Type` |
| `reg_type_checked_at` | Cache the lookup; re-check periodically |
| `is_active_taxpayer`, `statl_checked_at` | From the `statl` endpoint |

### `Product`
The point of this table is that **the operator never types tax metadata at sale time.**

| Field | Notes |
|---|---|
| `name` | Shop-friendly name |
| `product_description` | Goes to FBR as `productDescription` |
| `hs_code` | From `itemdesccode` |
| `uom` | From `HS_UOM` for that HS code — constrained, not free text |
| `sale_type` | e.g. "Goods at standard rate (default)" |
| `rate_desc` | The `ratE_DESC` string, e.g. `"18%"` |
| `rate_value` | Numeric, for computing tax locally |
| `fixed_notified_value_or_retail_price` | For 3rd Schedule items |
| `further_tax_applicable`, `extra_tax_applicable`, `fed_applicable` | Flags |
| `sro_schedule_no`, `sro_item_serial_no` | Optional |
| `unit_price` | The shop's selling price |

### `Invoice`
| Field | Notes |
|---|---|
| `local_invoice_no` | **Ours.** Alphanumeric + hyphen, e.g. `AG-000123` (errors 0088/0173) |
| `local_uuid` | Idempotency guard for retries |
| `invoice_type` | `Sale Invoice` / `Debit Note` |
| `invoice_date` | `YYYY-MM-DD` |
| `customer` | FK |
| buyer snapshot fields | **Copy** name/NTN/province/address/reg-type at time of sale — customers get edited later, the invoice must not change |
| `invoice_ref_no` | Original IRN, for debit/credit notes |
| `scenario_id` | Sandbox only |
| **`fbr_invoice_number`** | The IRN. Null until accepted |
| `fbr_dated` | `dated` from the response |
| `status` | `draft` → `queued` → `validating` → `posting` → `accepted` / `rejected` |
| `posted_at`, `attempt_count`, `last_error_code`, `last_error_message` | |
| totals | `total_excl_st`, `total_sales_tax`, `total_further_tax`, `total_extra_tax`, `total_fed`, `total_discount`, `grand_total` |
| `created_by`, `created_at` | Audit |

> **`status` must be a real state machine, not a free string.** A `queued` invoice printed as
> final is a compliance failure.

### `InvoiceItem`
One row per FBR line item, field-for-field: `hs_code`, `product_description`, `rate`, `uom`,
`quantity`, `total_values`, `value_sales_excluding_st`, `fixed_notified_value_or_retail_price`,
`sales_tax_applicable`, `sales_tax_withheld_at_source`, `extra_tax`, `further_tax`,
`sro_schedule_no`, `fed_payable`, `discount`, `sale_type`, `sro_item_serial_no`,
plus `fbr_item_invoice_no` (the `-1` suffixed number) and `fbr_status` / `fbr_error_code`.

### `FbrApiLog` — the audit trail
| Field | Notes |
|---|---|
| `invoice` | FK, nullable (reference-API calls too) |
| `endpoint`, `environment`, `http_method` | |
| `request_body`, `response_body` | **Raw JSON text, verbatim** |
| `http_status`, `fbr_status_code`, `fbr_error_code` | |
| `duration_ms`, `created_at` | |

**Append-only. Never updated, never deleted.** Retention ≥ 6 years.

### Cached reference tables
`RefProvince`, `RefDocType`, `RefHsCode`, `RefUom`, `RefSaleTypeRate`, `RefSroSchedule`,
`RefSroItem`, `RefTransactionType` — each with `fetched_at`. A "Refresh FBR reference data"
button, plus a warning when data is older than ~30 days.

---

## The offline queue

Compliance requirement, not a convenience feature (24-hour upload window, ⚠️ SECONDARY —
see [01-FBR-REGIMES.md](01-FBR-REGIMES.md)).

```
Sale entered
   ↓
Save locally  (status = queued)          ← always succeeds, never blocks the counter
   ↓
Online?  ──no──→  stay queued, retry with backoff, show age on screen
   │ yes
   ↓
POST validateinvoicedata   ← pre-flight
   ↓
Valid? ──no──→ status = rejected, show operator-friendly message, DO NOT print as final
   │ yes
   ↓
POST postinvoicedata
   ↓
Parse:  invoiceNumber present AND every invoiceStatuses[].statusCode == "00"
   ↓
status = accepted, store IRN → print invoice with IRN + QR + FBR logo
```

**Rules for the queue:**
- Retry with exponential backoff; **cap attempts** and escalate to a human rather than
  hammering FBR.
- Never auto-retry a `postinvoicedata` that timed out without first establishing whether the
  original landed — a duplicate IRN is worse than a delay. (See Q6.)
- Dashboard shows queued count and **oldest queued age**, turning red as it approaches 24h.
- Printing a queued invoice: needs a client decision — see Q5.

---

## Open modelling questions
- Credit notes: the API's `invoiceType` enum in the spec lists only `"Sale Invoice"` and
  `"Debit Note"`, yet the error codes repeatedly reference **credit notes** (0036, 0064, 0068,
  0071). ❓ Unresolved — the enum may be incomplete. Confirm before building returns.
- Multi-user / multi-counter: assumed single user until the client says otherwise.
- Whether purchases (Annex-A side) ever need to be recorded here — currently out of scope.
