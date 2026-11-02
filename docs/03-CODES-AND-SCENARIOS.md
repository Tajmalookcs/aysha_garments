# 03 — Scenarios, Sale Types and Error Codes

✅ All VERIFIED from [reference/PRAL-DI-API-v1.12.pdf](../reference/PRAL-DI-API-v1.12.pdf)
(§7 Sales Error Codes, §9 Scenarios, §10 Applicable Scenarios).

---

## 1. Sandbox scenarios (SN001–SN028)

`scenarioId` is **required in sandbox and omitted in production**. During onboarding, FBR
requires the taxpayer to successfully post the scenarios applicable to their **business
activity + sector** before a production token is released.

| Scenario | Description | `saleType` to send |
|---|---|---|
| SN001 | Goods at standard rate to **registered** buyers | Goods at Standard Rate (default) |
| SN002 | Goods at standard rate to **unregistered** buyers | Goods at Standard Rate (default) |
| SN003 | Sale of Steel (melted and re-rolled) | Steel Melting and re-rolling |
| SN004 | Sale by Ship Breakers | Ship breaking |
| SN005 | Reduced rate sale | Goods at Reduced Rate |
| SN006 | Exempt goods sale | Exempt Goods |
| SN007 | Zero rated sale | Goods at zero-rate |
| SN008 | Sale of 3rd schedule goods | 3rd Schedule Goods |
| SN009 | Cotton Spinners purchase from Cotton Ginners (Textile) | Cotton Ginners |
| SN010 | Telecom services rendered or provided | Telecommunication services |
| SN011 | Toll Manufacturing sale by Steel sector | Toll Manufacturing |
| SN012 | Sale of Petroleum products | Petroleum Products |
| SN013 | Electricity Supply to Retailers | Electricity Supply to Retailers |
| SN014 | Sale of Gas to CNG stations | Gas to CNG stations |
| SN015 | Sale of mobile phones | Mobile Phones |
| SN016 | Processing / Conversion of Goods | Processing/ Conversion of Goods |
| SN017 | Sale of Goods where FED is charged in ST mode | Goods (FED in ST Mode) |
| SN018 | Services where FED is charged in ST mode | Services (FED in ST Mode) |
| SN019 | Services rendered or provided | Services |
| SN020 | Sale of Electric Vehicles | Electric Vehicle |
| SN021 | Sale of Cement / Concrete Block | Cement /Concrete Block |
| SN022 | Sale of Potassium Chlorate | Potassium Chlorate |
| SN023 | Sale of CNG | CNG Sales |
| SN024 | Goods listed in SRO 297(I)/2023 | Goods as per SRO.297(I)/2023 |
| SN025 | Drugs at fixed ST rate, serial 81 of Eighth Schedule Table 1 | Non-Adjustable Supplies |
| SN026 | Sale to End Consumer by retailers | Goods at Standard Rate (default) |
| SN027 | Sale to End Consumer by retailers | 3rd Schedule Goods |
| SN028 | Sale to End Consumer by retailers | Goods at Reduced Rate |

> **SN026, SN027, SN028 apply only if registered as a retailer in the sales tax profile.**

---

## 2. Which scenarios must the client pass?

Determined by **Business Activity × Sector** in the FBR sales tax profile. The likely rows —
**but we do not yet know his actual profile** (Q3 in [06-OPEN-QUESTIONS.md](06-OPEN-QUESTIONS.md)):

| Business Activity | Sector | Scenarios |
|---|---|---|
| **Distributor** | All Other Sectors | SN001, SN002, SN005, SN006, SN007, SN015, SN016, SN017, SN021, SN022, SN024, SN026, SN027, SN028, SN008 |
| **Distributor** | Wholesale / Retails | SN001, SN002, SN026, SN027, SN028, SN008 |
| **Wholesaler** | All Other Sectors | SN001, SN002, SN005, SN006, SN007, SN015, SN016, SN017, SN021, SN022, SN024, SN026, SN027, SN028, SN008 |
| **Wholesaler** | Wholesale / Retails | SN001, SN002, SN026, SN027, SN028, SN008 |
| **Retailer** | All Other Sectors | SN001, SN002, SN005, SN006, SN007, SN015, SN016, SN017, SN021, SN022, SN024, SN026, SN027, SN028, SN008 |
| **Retailer** | Wholesale / Retails | SN026, SN027, SN028, SN008 |
| **Retailer** | FMCG | SN026, SN027, SN028, SN008 |
| **Manufacturer** | All Other Sectors | SN001, SN002, SN005, SN006, SN007, SN015, SN016, SN017, SN021, SN022, SN024 |
| **Service Provider** | Services | SN018, SN019 |

Full 118-row matrix: spec §10, lines ~1863–2197 of the extracted text.

**Practical read:** the "All Other Sectors" rows require **11–15 scenarios**, the
"Wholesale / Retails" rows only **4–6**. Getting the client's profile right materially changes
how much onboarding work Phase 1 involves.

---

## 3. Sales error codes

Most common / most likely to hit us are marked ★.

| Code | Meaning |
|---|---|
| 0001 | Seller not registered for sales tax — provide valid registration/NTN |
| 0002 | ★ Invalid buyer registration no. — must be 13-digit CNIC or 7/9-digit NTN |
| 0003 | Invoice type not valid or empty |
| 0005 | ★ Invoice date format wrong — must be `YYYY-MM-DD` |
| 0006 | Sale invoice does not exist (against STWH) |
| 0007 | Wrong sale type selected for this invoice/registration |
| 0008 | ★ ST withheld at source must be **zero or equal to** sales tax |
| 0009 | Buyer registration no. empty |
| 0010 | Buyer name empty |
| 0011 | Invoice type empty |
| 0012 | ★ Buyer registration type empty |
| 0013 | Sale type empty/null |
| 0018 | Sales Tax / FED in ST mode empty |
| 0019 | HS Code empty |
| 0020 | Rate empty |
| 0021 | Value of Sales Excl. ST / Quantity empty |
| 0022 | ST withheld at source / STS withheld empty |
| 0023 | Sales tax empty |
| 0024 | Sales tax withheld empty |
| 0026 | Invoice Reference No. required (debit/credit note) |
| 0027 | Reason required (debit/credit note) |
| 0028 | Reason remarks required when reason is "Others" |
| 0029 | Note date must be ≥ original invoice date |
| 0030 | Unregistered distributor type not allowed before system cut-off date |
| 0031 | Sales tax not mentioned |
| 0032 | STWH only for GOV/FTN holders |
| 0034 | ★ Debit/credit note only within **180 days** of original invoice |
| 0035 | Note date must be ≥ original invoice date |
| 0036 | Credit note value of sale exceeds original invoice |
| 0037 | Credit note ST withheld exceeds original invoice |
| 0039 | For registered users, STWH invoice fields must match the sale invoice |
| 0041 | Invoice number empty |
| 0042 | Invoice date empty |
| 0043 | Invoice date invalid |
| 0044 | HS Code empty |
| 0046 | ★ Rate empty — must match the selected sale type |
| 0050 | For 'Cotton ginners', ST withheld must equal sales tax or zero |
| 0052 | ★ HS Code does not match the provided sale type |
| 0053 | ★ Buyer registration type invalid |
| 0055 | ST withheld as WH agent empty/invalid |
| 0056 | Buyer does not exist in steel sector |
| 0057 | Reference invoice for debit/credit note does not exist |
| 0058 | ★ **Self-invoicing not allowed** — buyer and seller reg. no. are the same |
| 0064 | Credit note already added to this invoice |
| 0067 | Debit note sales tax exceeds original invoice's sales tax |
| 0068 | Credit note sales tax below original invoice's sales tax per the rate |
| 0070 | STWH not allowed for unregistered buyers |
| 0071 | Credit note only allowed for specific users |
| 0073 | Sale Origination Province of Supplier empty |
| 0074 | Destination of Supply empty |
| 0077 | SRO / Schedule number empty |
| 0078 | Item serial number empty |
| 0079 | ★ If Value of Sales Excl. ST > 20,000, **rate 5% not allowed** |
| 0080 | Further Tax empty |
| 0081 | 'Input Credit not Allowed' empty |
| 0082 | Seller not registered for sales tax |
| 0083 | Seller registration no. mismatch |
| 0085 | Total Value of Sales required (PFAD only) |
| 0086 | Not an EFS licence holder who imported Compressor Scrap in last 12 months |
| 0087 | Petroleum Levy rates not configured properly |
| 0088 | ★ Invoice no. must be alphanumeric; `-` allowed **between** alphanumerics, e.g. `Inv-001` |
| 0089 | FED Charged empty |
| 0090 | Fixed / notified value or Retail Price empty |
| 0091 | Extra tax must be empty |
| 0092 | Purchase type empty |
| 0170 | Duplicate of 0079 (>20,000 → 5% not allowed) |
| 0171 | Duplicate of 0086 |
| 0172 | Duplicate of 0087 |
| 0173 | Duplicate of 0088 |
| 0174 | Duplicate of 0031 (sales tax empty) |
| 0175 | Duplicate of 0090 |
| 401 / 402 | Added in spec revision 24-Jul-2025 — **text not captured; look them up** ❓ |

> The `0170`–`0175` block mirrors `0079`–`0090`. Likely the purchase-side equivalents. The
> purchase error code table (spec §8) has **not** been transcribed here — read the extracted
> text if purchase-side posting is ever in scope.

## 4. Build these as a lookup table
Map every code to a **plain-Urdu/English message the shopkeeper can act on**. "Provide rate."
means nothing to a counter operator. `0052` should read: *"This product's HS code doesn't match
its tax category — open the product and fix it."*
