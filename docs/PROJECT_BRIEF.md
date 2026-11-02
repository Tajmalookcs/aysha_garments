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
- Tech stack: Django + SQLite, with Bootstrap stored locally
- Reference only: the earlier Rasheed project is used to understand FBR rules, not for its code or design

## FBR registration status

- Integrator: PRAL
- Technical details submitted; IP whitelisting pending with PRAL; no sandbox token yet
- Assigned sandbox scenarios (9): SN001, SN002, SN005, SN006, SN007, SN009, SN016, SN017, SN024
- Client identity details, the IP, tokens and passwords are deliberately not stored in this repository

## Open questions

1. How many pieces make a lot, and does it vary?
2. How is a foreign buyer reported to FBR? Export invoices must not be treated as ready until this is confirmed.
3. What goes inside the QR code? The spec does not say.
4. Product list with HS codes, units, prices and tax rates, from the client.
5. The client's STRN.
6. Is a static IP available? It's needed for reliable daily use.
