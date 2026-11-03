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
- What goes inside the QR code. The spec doesn't say, and its sample QR is only a third-party link.

### Outcome
The final copy has the FBR logo, IRN and an empty QR box. It only appears after production acceptance, which isn't built yet.

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

## Later builds (not approved yet)

3. Run the sandbox scenarios from the whitelisted computer.
5. Reliability: offline queue, sales register, backups.
6. Go live: production token, first real invoice, training.
