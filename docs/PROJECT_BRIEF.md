# Project Brief

## Confirmed

- What we are building: a new FBR digital invoicing system for manufacturing units
- First client: Ayesha Garments (`AYESHA GARMENTS` is the name sent to FBR)
- Several clients: each client gets its own installation, with one company and one user. One installation is never shared between clients
- New installations run as a 15 day demo until the client's registration file is added
- Scope: invoicing only for now; more can be added if a client asks
- Selling: pieces and lots, to registered and unregistered buyers, and for export
- Offline: all design assets are stored locally; invoices are saved locally and uploaded when internet returns
- Design: new look, with animated login and loading screens
- Printing and users: A4, one computer (assumed, owner agreed)
- Client's connection: a static IP, confirmed with the provider
- Client computer: the client will get a new PC or upgrade Windows before installation
- QR code: holds the IRN given by FBR (confirmed by the owner, and Rule 150R(4)(e) says it is based on the FBR invoice number)
- Company registration: NTN (format 0000000-0) is required and prints on invoices; CNIC is optional and doesn't print
- Invoice flow: save locally first, edit or delete if needed, then an Approve and send button releases it to FBR and locks it
- Users: one person uses the app and approves invoices
- Tax: worked out after discount
- Lots: size varies, so pieces per lot is entered on each invoice line
- Tech stack: Django + SQLite, with Bootstrap stored locally
- Reference only: an earlier project is used to understand FBR rules, not for its code or design

## FBR registration status

- Integrator: PRAL
- Technical details submitted; IP whitelisting pending with PRAL; sandbox token issued
- First client's business, confirmed by the client on 2026-11-04: processing and conversion only, no export. It takes in and returns cloth by weight, charges by the set or pack, and gives each job a number. The client says its HS code is reported to FBR in KG. Its IRIS profile says Manufacturer and Exporter, which still needs checking.
- Assigned sandbox scenarios (9): SN001, SN002, SN005, SN006, SN007, SN009, SN016, SN017, SN024
- Client identity details, the IP, tokens and passwords are deliberately not stored in this repository

## Open questions

1. How is a foreign buyer reported to FBR? Export invoices must not be treated as ready until this is confirmed. The first client told us on 2026-11-04 that it doesn't export, so this matters only for later clients.
2. Product list with HS codes, units, prices and tax rates, from the client. The client's September 2026 FBR report shows one kind of sale in KG, and the client confirmed on 2026-11-04 that it does conversion only. Still to confirm: whether the same HS code is always used.
3. How is a discount reported to FBR? The spec has a discount field but doesn't say whether the value sent is before or after it.
4. Are credit notes supported? The spec lists only Sale Invoice and Debit Note, but its errors mention credit notes.
5. Does FBR accept the 7 digit NTN for a sole proprietor's token? Error 0401 ties the token to the seller's registration number, so confirm in sandbox.
6. QR size: Rule 150R(13) says 7x7 mm, but PRAL's spec says 1x1 inch. See `docs/PRAL_QUESTIONS.md`.
7. What is the e-invoicing software registration number when PRAL is the integrator?
