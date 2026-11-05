# 02 — FBR Digital Invoicing API Reference

**Source:** PRAL, *Technical Specification for DI API*, **Version 1.12**, issued 7-Apr-2025,
last updated 24-Jul-2025. Full copy in [reference/PRAL-DI-API-v1.12.pdf](../reference/PRAL-DI-API-v1.12.pdf),
extracted text in [reference/PRAL-DI-API-v1.12-extracted.txt](../reference/PRAL-DI-API-v1.12-extracted.txt).

Everything on this page is ✅ **VERIFIED** against that document unless marked otherwise.

> **Check for a newer version before coding.** The spec changed 12 times between April and
> July 2025. v1.12 is the newest we have found; it is now roughly a year old, so a newer
> revision very likely exists. Re-download from `download1.fbr.gov.pk` before Phase 3.

---

## 1. Authentication

A **security token** issued by PRAL, passed on every request:

```
Authorization: Bearer <TOKEN>
Content-Type: application/json
```

- Validity: **5 years**. A new token is issued automatically on expiry.
- The token is issued to the taxpayer along with the URLs.
- **Sandbox vs production is determined by which token you use** — the spec states:
  > "DI data acquisition API URL's mentioned in this document will remain the same for Sandbox
  > and Production; routing will be based on the security token being used."

  ⚠️ This contradicts the separate `_sb` URLs the same document lists. Treat the `_sb` URLs as
  authoritative for sandbox, and expect that the token also matters. Test both.

---

## 2. Core endpoints

| Purpose | Method | URL |
|---|---|---|
| Post invoice — **sandbox** | POST | `https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb` |
| Post invoice — **production** | POST | `https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata` |
| Validate invoice — **sandbox** | POST | `https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata_sb` |
| Validate invoice — **production** | POST | `https://gw.fbr.gov.pk/di_data/v1/di/validateinvoicedata` |

`validateinvoicedata` takes the **same payload** as `postinvoicedata` but does **not** issue an
IRN — it only reports whether the invoice would be accepted. **Use it as a pre-flight check
before posting.** This is the single most useful safety feature in the API; build the workflow
around validate → fix → post.

### HTTP status codes
| Code | Meaning |
|---|---|
| 200 | OK (note: a 200 can still carry `statusCode: "01"` = business-rule failure) |
| 401 | Unauthorized (bad/expired token) |
| 500 | Internal Server Error — contact administrator |

**Do not treat HTTP 200 as success.** Always parse `validationResponse.statusCode`.

---

## 3. Request payload

The invoice header appears **once**; line items go in the `items[]` array.

```json
{
  "invoiceType": "Sale Invoice",
  "invoiceDate": "2025-04-21",
  "sellerNTNCNIC": "0786909",
  "sellerBusinessName": "Company 8",
  "sellerProvince": "Sindh",
  "sellerAddress": "Karachi",
  "buyerNTNCNIC": "1000000000000",
  "buyerBusinessName": "FERTILIZER MANUFAC IRS NEW",
  "buyerProvince": "Sindh",
  "buyerAddress": "Karachi",
  "buyerRegistrationType": "Registered",
  "invoiceRefNo": "",
  "scenarioId": "SN001",
  "items": [
    {
      "hsCode": "0101.2100",
      "productDescription": "product Description",
      "rate": "18%",
      "uoM": "Numbers, pieces, units",
      "quantity": 1.0000,
      "totalValues": 0.00,
      "valueSalesExcludingST": 1000.00,
      "fixedNotifiedValueOrRetailPrice": 0.00,
      "salesTaxApplicable": 180.00,
      "salesTaxWithheldAtSource": 0.00,
      "extraTax": 0.00,
      "furtherTax": 120.00,
      "sroScheduleNo": "",
      "fedPayable": 0.00,
      "discount": 0.00,
      "saleType": "Goods at standard rate (default)",
      "sroItemSerialNo": ""
    }
  ]
}
```

### Header fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `invoiceType` | string | ✔ | `"Sale Invoice"` or `"Debit Note"` |
| `invoiceDate` | date | ✔ | **`YYYY-MM-DD`** — error 0005 if not |
| `sellerNTNCNIC` | string | ✔ | 7 or 13 digits |
| `sellerBusinessName` | string | ✔ | |
| `sellerProvince` | string | ✔ | Must match a value from the `provinces` reference API |
| `sellerAddress` | string | ✔ | |
| `buyerNTNCNIC` | string | conditional | Required for registered buyers; **optional when unregistered** |
| `buyerBusinessName` | string | ✔ | |
| `buyerProvince` | string | ✔ | From `provinces` reference API |
| `buyerAddress` | string | ✔ | |
| `buyerRegistrationType` | string | ✔ | `"Registered"` or `"Unregistered"` |
| `invoiceRefNo` | string | conditional | **Required for debit notes only.** 22 digits (NTN) / 28 digits (CNIC) |
| `sourceInvoiceNo` | string | not in the spec | The seller's own invoice number. Found by testing on 2026-11-06: in the sandbox it fills Source Invoice No. in IRIS. Production not confirmed. |
| `scenarioId` | string | **sandbox only** | e.g. `"SN001"` — see [03-CODES-AND-SCENARIOS.md](03-CODES-AND-SCENARIOS.md). **Omit in production.** |
| `items` | array | ✔ | |

> ⚠️ **Spelling trap.** The field-description table in the spec writes `buyeRegistrationType`
> (missing `r`), but **every JSON sample uses `buyerRegistrationType`**. Use the sample
> spelling. Verify against sandbox on day one — error 0012/0053 will tell you if it's wrong.

### Item fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `hsCode` | string | ✔ | Format `0101.2100`. Must match the sale type (error 0052) |
| `productDescription` | string | ✔ | |
| `rate` | string | ✔ | The **`ratE_DESC` string** from `SaleTypeToRate`, e.g. `"18%"` — not a number |
| `uoM` | string | ✔ | `description` from the `uom` / `HS_UOM` reference API |
| `quantity` | decimal | ✔ | |
| `totalValues` | decimal | ✔ | Total sales value **including** tax |
| `valueSalesExcludingST` | decimal | ✔ | Sales value **excluding** sales tax |
| `fixedNotifiedValueOrRetailPrice` | decimal | ✔ | Notified fixed / retail price (item-based). 0.00 if N/A |
| `salesTaxApplicable` | decimal | ✔ | Sales tax / FED in ST mode, **excluding** further & extra tax |
| `salesTaxWithheldAtSource` | decimal | ✔ | Must be **zero or exactly equal to sales tax** (error 0008) |
| `extraTax` | decimal | optional | |
| `furtherTax` | decimal | optional | |
| `sroScheduleNo` | string | optional | |
| `fedPayable` | decimal | optional | |
| `discount` | decimal | optional | |
| `saleType` | string | ✔ | e.g. `"Goods at standard rate (default)"` — see scenario table |
| `sroItemSerialNo` | string | optional | |

---

## 4. Response

### Success (`postinvoicedata`)
```json
{
  "invoiceNumber": "7000007DI1747119701593",
  "dated": "2025-05-13 12:01:41",
  "validationResponse": {
    "statusCode": "00",
    "status": "Valid",
    "error": "",
    "invoiceStatuses": [
      {
        "itemSNo": "1",
        "statusCode": "00",
        "status": "Valid",
        "invoiceNo": "7000007DI1747119701593-1",
        "errorCode": "",
        "error": ""
      }
    ]
  }
}
```

- `invoiceNumber` is the **IRN** — this is what goes on the printed invoice and into the QR.
  Format: `<seller reg no>DI<epoch-millis>`. Per-item numbers get a `-<n>` suffix.
- `statusCode`: **`00` = Valid**, **`01` = Invalid**.

### Failure — whole-invoice rejection
```json
{
  "dated": "2025-05-13 13:09:05",
  "validationResponse": {
    "statusCode": "01",
    "status": "Invalid",
    "errorCode": "0052",
    "error": "Provide proper HS Code with invoice no. null",
    "invoiceStatuses": null
  }
}
```
Note: **no `invoiceNumber` key at all.** Do not assume it exists.

### Failure — item-level rejection
```json
{
  "dated": "2025-05-13 13:10:00",
  "validationResponse": {
    "statusCode": "00",
    "status": "invalid",
    "error": "",
    "invoiceStatuses": [
      { "itemSNo": "1", "statusCode": "01", "status": "Invalid",
        "invoiceNo": null, "errorCode": "0046", "error": "Provide rate." }
    ]
  }
}
```

> ⚠️ **Parsing trap — this one will bite.** In this example the **outer `statusCode` is `00`**
> while `status` is the lowercase string `"invalid"` and the item failed. So:
> - Do **not** trust the outer `statusCode` alone.
> - Do **not** compare `status` case-sensitively (`"Valid"`, `"Invalid"`, `"invalid"` all appear).
> - Treat the invoice as accepted **only if** `invoiceNumber` is present **and** every entry in
>   `invoiceStatuses` has `statusCode == "00"`.

---

## 5. Reference / lookup APIs

All are `GET`, all take the same `Authorization: Bearer` header, all return the same
200/401/500 codes. **Cache these locally** — they are large, slow-changing, and needed offline.

| # | Purpose | URL | Input |
|---|---|---|---|
| 5.1 | Provinces | `https://gw.fbr.gov.pk/pdi/v1/provinces` | none |
| 5.2 | Document types | `https://gw.fbr.gov.pk/pdi/v1/doctypecode` | none |
| 5.3 | HS codes + descriptions | `https://gw.fbr.gov.pk/pdi/v1/itemdesccode` | none |
| 5.4 | SRO item codes | `https://gw.fbr.gov.pk/pdi/v1/sroitemcode` | none |
| 5.5 | Transaction types | `https://gw.fbr.gov.pk/pdi/v1/transtypecode` | none |
| 5.6 | Units of measure | `https://gw.fbr.gov.pk/pdi/v1/uom` | none |
| 5.7 | SRO schedule | `https://gw.fbr.gov.pk/pdi/v1/SroSchedule` | `rate_id`, `date`, `origination_supplier_csv` |
| 5.8 | **Sale type → rate** | `https://gw.fbr.gov.pk/pdi/v2/SaleTypeToRate` | `date`, `transTypeId`, `originationSupplier` |
| 5.9 | Valid UoM for an HS code | `https://gw.fbr.gov.pk/pdi/v2/HS_UOM` | `hs_code`, `annexure_id` |
| 5.10 | SRO items for an SRO | `https://gw.fbr.gov.pk/pdi/v2/SROItem` | `date`, `sro_id` |
| 5.11 | **STATL** (active-taxpayer check) | `https://gw.fbr.gov.pk/dist/v1/statl` | `{"regno","date"}` |
| 5.12 | **Registration type** | `https://gw.fbr.gov.pk/dist/v1/Get_Reg_Type` | `{"Registration_No"}` |

### Sample shapes
```jsonc
// 5.1 provinces
[{ "stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB" }]

// 5.2 doctypecode
[{ "docTypeId": 4, "docDescription": "Sale Invoice" },
 { "docTypeId": 9, "docDescription": "Debit Note" }]

// 5.3 itemdesccode
[{ "hS_CODE": "8432.1010", "description": "NUCLEAR REACTOR, BOILERS, ..." }]

// 5.6 uom
[{ "uoM_ID": 77, "description": "Square Metre" }, { "uoM_ID": 13, "description": "KG" }]

// 5.8 SaleTypeToRate  →  feed ratE_DESC into the item's `rate` field
[{ "ratE_ID": 734, "ratE_DESC": "18% along with rupees 60 per kilogram", "ratE_VALUE": 18 },
 { "ratE_ID": 280, "ratE_DESC": "0%", "ratE_VALUE": 0 }]

// 5.11 statl  request {"regno":"0788762","date":"2025-05-18"}
{ "status code": "01", "status": "In-Active" }        // note the SPACE in "status code"

// 5.12 Get_Reg_Type  request {"Registration_No":"0788762"}
{ "statuscode": "00", "REGISTRATION_NO": "0788762", "REGISTRATION_TYPE": "Registered" }
```

> ⚠️ **Inconsistent key casing across endpoints** — `hS_CODE`, `uoM_ID`, `ratE_DESC`,
> `srO_ITEM_ID`, `transactioN_TYPE_ID`, `"status code"` (with a space), `statuscode` (no space).
> This looks like a broken camel-casing pass over Oracle column names. Do not normalise by
> guesswork — map each endpoint's keys explicitly and pin them with tests.

**`Get_Reg_Type` is genuinely useful:** call it when the operator enters a buyer's NTN to set
`buyerRegistrationType` automatically instead of asking the shopkeeper. Same for `statl` to
warn that a buyer is inactive.

---

## 6. Printing requirements

✅ VERIFIED — every invoice issued to a customer must carry:
- The **FBR Digital Invoicing System logo**
- A **QR code**:
  - QR **version 2.0 (25 × 25)**
  - Physical size **1.0 × 1.0 inch**

❓ **UNVERIFIED and important:** the spec does not state *what data goes inside the QR*. The
IRN is the obvious candidate but do not assume. **Confirm this before Phase 3** — from a newer
spec revision, PRAL support, or by inspecting a compliant invoice from another vendor.
Logged as Q7 in [06-OPEN-QUESTIONS.md](06-OPEN-QUESTIONS.md).

---

## 7. Implementation notes for whoever writes the client

1. **Always `validateinvoicedata` before `postinvoicedata`.** Cheap insurance.
2. **Post is not idempotent** as far as we know. A retry after a timeout may create a duplicate
   IRN. Store a local UUID per invoice, record the request/response verbatim, and never
   auto-retry a post without checking whether the first one landed. ❓ Ask PRAL whether a
   lookup-by-local-invoice-number exists.
3. **Log every request and response body**, forever. This is the audit trail, and it is the
   only way to debug an FBR rejection months later.
4. **Never let the user hand-type HS code, UoM, rate, or sale type** at invoice time. Pin them
   to the product record, sourced from the reference APIs.
5. **Invoice number format:** alphanumeric with hyphens allowed, hyphen must be *between*
   alphanumeric characters — e.g. `Inv-001` (errors 0088 / 0173).
6. **Self-invoicing is rejected** — buyer and seller registration numbers must differ (0058).
7. **Debit/credit notes only within 180 days** of the original invoice (0034).
8. `salesTaxWithheldAtSource` must be **0 or exactly equal to** the sales tax (0008).
9. If `valueSalesExcludingST` > **20,000**, a **5% rate is not allowed** (0079 / 0170).
10. Money must be handled as **decimal, never float**. Rounding differences will be rejected.

## Coverage note
The following parts of the source spec have **not** been read in full and are summarised only
partially here: the purchase-side error codes (spec §8) and part of the validate-method field
tables (spec §4.2). Read [reference/PRAL-DI-API-v1.12-extracted.txt](../reference/PRAL-DI-API-v1.12-extracted.txt)
directly before relying on those areas.
