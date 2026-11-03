# Project Brief

## Confirmed

- What we are building: a new FBR digital invoicing system for manufacturing units
- First client: Ayesha Garments (`AYESHA GARMENTS` is the name sent to FBR)
- Several clients: the system must support more than one company
- Scope: invoicing only for now; more can be added if a client asks
- Selling: pieces and lots, to registered and unregistered buyers, and for export
- Offline: all design assets are stored locally; invoices are saved locally and uploaded when internet returns
- Design: new look, with animated login and loading screens
- Printing and users: A4, one computer (assumed, owner agreed)
- Client computer: the client will get a new PC or upgrade Windows before installation
- Invoice flow: save locally first, edit or delete if needed, then an Approve and send button releases it to FBR and locks it
- Users: one person uses the app and approves invoices
- Tax: worked out after discount
- Lots: size varies, so pieces per lot is entered on each invoice line
- Tech stack: Django + SQLite, with Bootstrap stored locally
- Reference only: an earlier project is used to understand FBR rules, not for its code or design

## FBR registration status

- Integrator: PRAL
- Technical details submitted; IP whitelisting pending with PRAL; sandbox token issued
- Assigned sandbox scenarios (9): SN001, SN002, SN005, SN006, SN007, SN009, SN016, SN017, SN024
- Client identity details, the IP, tokens and passwords are deliberately not stored in this repository

## Open questions

1. How is a foreign buyer reported to FBR? Export invoices must not be treated as ready until this is confirmed.
2. What goes inside the QR code? The spec does not say.
3. Product list with HS codes, units, prices and tax rates, from the client.
4. The client's STRN.
5. How is a discount reported to FBR? The spec has a discount field but doesn't say whether the value sent is before or after it.
6. Is a static IP available? It's needed for reliable daily use.
