# Build Plans

Each build gets an entry here. Work starts only after the plan is approved.

## Template

```
## Build N: Title

Status: Proposed | Approved | Done | Rejected
Date proposed:
Date approved:

### Goal
What this build achieves.

### Work
What will be built, and which files will change.

### Decisions needed
Anything the owner must decide.

### Outcome
What was actually done, and any differences from the plan.
```

## Builds

## Build 1: Core app

Status: Done locally on 2026-11-02. Not pushed yet.
Date proposed: 2026-11-02
Date approved: 2026-11-02

### Goal
A new invoicing app for manufacturing units that serves several clients and works offline.

### Work
- Step A: design preview with an animated login and loading screens, plus dashboard and invoice entry. All assets are stored locally.
- Step B, after design approval: Django + SQLite app with company profiles, users, products, customers, invoice entry and tax calculation, with tests and a `start.bat` launcher.

Not included: FBR calls, the upload queue, final invoice printing.

### Decisions needed
- How foreign buyers are reported to FBR.
- How a discount is reported to FBR.

### Outcome
Step A: `design_preview/` added and the design approved by the owner.

Step B: app built, with these points to note:
- Added at the owner's request: invoices are saved first, and only an "Approve and send to FBR" click releases them. Until the FBR connection is built, the button only marks the invoice as approved.
- One person uses the app and approves their own invoices. The Users screen is hidden from the menu.
- Tax is worked out after discount.
- Lot size varies, so pieces per lot is entered on each invoice line.
- Foreign buyers' invoices are saved as held and can't be approved.
- Invoices can be edited or deleted until approved, then they're locked. A deleted invoice's number is used again by the next new invoice.
- `start.bat` hasn't been run on Windows yet.

## Build 2: FBR connection (sandbox)

Status: Built and tested against the spec's samples and a fake local server. Not yet tested against FBR.
Date proposed: 2026-11-02
Date approved: 2026-11-02

### Goal
Send approved invoices to the FBR sandbox and run the assigned scenarios.

### Work
- `fbr` app: encrypted token, FBR lists, rate lookup, validate then post, strict reply reading, permanent call log, scenarios table.
- Unknown post results stop for a person to check IRIS, and are never resent automatically.
- Rejected invoices stay editable. Sandbox and demo acceptances never count as final.

Not included: production token, QR code and printing, sending export invoices.

### Decisions needed
- Confirm in sandbox: `valueSalesExcludingST` is sent after discount, and `extraTax` is an empty string as in the IRIS sample.
- Confirm in sandbox: how FED and SRO fields work for the FED and SRO scenarios.

### Outcome
The token test and list download worked against the FBR sandbox. Invoice sending is not yet tested against FBR.

Also added at the owner's request: a clear "page expired" screen instead of the plain security error.

## Build A: Printing

Status: Done locally on 2026-11-03. Not pushed yet.
Date proposed: 2026-11-03
Date approved: 2026-11-03

### Goal
A4 invoice printing that can never pass off an unaccepted invoice as final.

### Work
Print screen with Pending FBR, Sandbox test and final copies, amount in words, and a further tax column only when needed.

### Decisions needed
None.

### Outcome
The final copy has the FBR logo, the IRN and a version 2.0 (25x25) QR code at 1x1 inch holding the IRN, as confirmed by the owner. It only appears after production acceptance, which isn't built yet.

## Build B: Sales register and backup

Status: Done locally on 2026-11-03.
Date proposed: 2026-11-03
Date approved: 2026-11-03

### Goal
Help reconcile the monthly return, and protect the data.

### Work
- Sales register: date and status filters, totals, and an export that opens in Excel.
- `backup.bat`: saves the database, keys and media to a folder outside the project.
- "Send all waiting" was dropped at the owner's request.

### Outcome
Built and tested. The register totals show a warning when they include invoices not accepted in production.

## Build C: Features from the FBR documents

Status: Done locally on 2026-11-03. Not pushed yet, and not yet tested against FBR.
Date proposed: 2026-11-03
Date approved: 2026-11-03

### Goal
Support what the PRAL spec v1.12 and User Manual v1.5 require.

### Work
- QR code on the final copy: version 2.0 (25x25) at 1x1 inch, holding the IRN as confirmed by the owner. The documents don't state the content.
- Lookups: units for an HS code, SRO schedules and SRO items.
- Buyer checks: registration type and active status.
- Debit notes against accepted invoices, with FBR's 180-day and sales tax limits.
- Production mode: separate token, real URLs and no scenario ID. It needs a deliberate switch.

### Decisions needed
- Errors 0027 and 0028 mention a reason for debit notes, but the spec has no field for it. Confirm in sandbox.
- The spec names STATL and Get_Reg_Type as GET with a JSON body. POST is tried if GET is refused.
- Credit notes appear only in error messages, so they aren't built. Ask PRAL.

### Outcome
Built and tested against the spec's samples and a fake local server.

Also changed at the owner's request: the company now has a required NTN (0000000-0) and an optional CNIC. Invoices print only the NTN, and FBR receives its 7 digits.

## Build D: Print and offline rules from FBR's Sales Tax Rules

Status: Done locally on 2026-11-03. Not yet tested against FBR.
Date proposed: 2026-11-03
Date approved: 2026-11-03

### Goal
Cover what Rule 150R(13) and Rule 150XC require.

### Work
- Print: tax period, unit, and SRO and serial number where used.
- Offline: invoices saved without internet, or that couldn't reach FBR, are marked as offline on screen and in print, with a 24-hour warning on the dashboard.
- `docs/PRAL_QUESTIONS.md`: questions for PRAL support.

### Decisions needed
- The rules say a 7x7 mm QR, but PRAL's spec says 1x1 inch. The app follows PRAL's spec until PRAL confirms.
- The e-invoicing software registration number isn't printed yet. Ask PRAL what it is when PRAL is the integrator.

### Outcome
Built and tested locally.

## Build E: Selling by KG

Status: Done locally on 2026-11-04. Not yet tested against FBR.
Date proposed: 2026-11-04
Date approved: 2026-11-04

### Goal
The client's FBR sales report is in KG, but invoices only allowed pieces and lots. The app serves several clients, so KG becomes the default and piece and lot stay.

### Work
- A product whose FBR unit is KG or Kilogram is invoiced by KG. Any other product is invoiced by piece or lot.
- New products start on KG, and a new invoice starts on the first KG product if there is one.
- The saving step refuses a selling method that doesn't fit the product's unit, because the quantity goes to FBR in that unit.
- The invoice form, invoice screen, print copy and product screens show the right unit.
- One KG sample product and invoice added to the demo data.
- In sandbox, an invoice whose items are all Processing/Conversion of Goods suggests SN016. Approved by the owner on 2026-11-04.

### Decisions needed
- The client's starting invoice number. The app starts at 1 and has no setting for this yet.
- The client's report shows whole rupees, while the app keeps paisa. Watch this in the sandbox.

### Outcome
Built and tested locally with a fake server.

## Build F: Pack lines with KG, job number, buyer STRN and last invoice number

Status: Done locally on 2026-11-04. Not yet tested against FBR.
Date proposed: 2026-11-04
Date approved: 2026-11-04

### Goal
The first client charges by the set or pack, but reports KG to FBR, because that's the unit for its HS code (the client's statement). The app needs both on each line.

### Work
- A KG product can have a pack unit. Its invoice line has packs, a rate per pack and KG. The value comes from packs and rate.
- Total weight shows at the end of the invoice, on screen and in print.
- "Your reference" is now "Job no.". It prints but doesn't go to FBR.
- Customers have a STRN. It prints with the NTN but doesn't go to FBR.
- FBR gets KG as the quantity. Pack lines that match on HS code, sale type, rate, unit, SRO details and fixed value go as one item, with KG, value and tax added up. Pack lines that differ go as separate items. Other lines stay separate.
- Companies can enter their last invoice number. New invoices take the lowest free number after it, so a deleted number is used again. A blank prefix gives plain numbers like 119.

### Decisions needed
- Does FBR accept the combined item? The owner will check this in the sandbox.

### Outcome
Built and tested locally with a fake server.

## Build G: One install, demo and registration

Status: Done locally on 2026-11-04. Not yet tested against FBR.
Date proposed: 2026-11-04
Date approved: 2026-11-04

### Goal
Each client gets a separate install, used by one person. New installs run as a demo until the developer registers them.

### Work
- Removed new company, switch company, user screens and the operator role. The database structure stays, so existing data is safe.
- Setup needs the developer password. Without the demo file, this copy says it isn't ready.
- Demo: 15 days from first use. Invoices say DEMO on screen and in print, the sandbox works and production is refused. After 15 days, or if the date moves back, new invoices and sending stop, while old data stays open.
- Registration: a file signed with the developer's private key, tied to the client's NTN, replaces the demo. It holds the hash of that client's developer password.
- Production: needs registration, a production token and the existing confirmation tick.
- Company details ask for the developer password, and stay open for 10 minutes.
- The last invoice number has its own box on the new invoice screen, which closes after the first invoice.
- Developer commands: `setup_licensing` and `make_licence`.

### Limits
- Someone who can change the code can remove these checks. The code runs on the client's computer.

### Decisions needed
- The owner still has to run `setup_licensing` and add `licensing/demo.json` and `licensing/public_key.pem` to the repository. Until then, new installs can't be set up.

### Outcome
Built and tested locally with a fake server.

## Later builds (not approved yet)

3. Run the sandbox scenarios from the whitelisted computer.
6. Go live: first real invoice, training.
