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

Status: Step A done, waiting for design approval. Step B not started.
Date proposed: 2026-11-02
Date approved: 2026-11-02

### Goal
A new invoicing app for manufacturing units that serves several clients and works offline.

### Work
- Step A: design preview with an animated login and loading screens, plus dashboard and invoice entry. All assets are stored locally.
- Step B, after design approval: Django + SQLite app with company profiles, users, products, customers, invoice entry and tax calculation, with tests and a `start.bat` launcher.

Not included: FBR calls, the upload queue, final invoice printing.

### Decisions needed
- Approve the design.
- How many pieces make a lot, and does it vary?
- How foreign buyers are reported to FBR.

### Outcome
Step A: `design_preview/` added. All data in it is sample data, and it makes no FBR calls.

## Later builds (not approved yet)

2. FBR connection: validate and post, response parsing, call log, encrypted token.
3. Sandbox scenarios, run from the whitelisted computer.
4. Printing: IRN, QR code and FBR logo.
5. Reliability: offline queue, sales register, backups.
6. Go live: production token, first real invoice, training.
