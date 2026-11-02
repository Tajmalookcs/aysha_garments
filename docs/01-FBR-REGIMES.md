# 01 — FBR Regimes, Legal Framework, Compliance

> **Read the client's notice before trusting anything on this page.** The notice names the
> section/SRO it is issued under, and that determines which regime applies. Everything below
> is background so you can read the notice intelligently — it is not a substitute for it.

## The three regimes people confuse

There are three separate FBR integration regimes. "POS integration" is used loosely in
conversation to mean any of them.

### A. Sales Tax — POS Integration for Tier-1 Retailers
- Authority: Sales Tax Act 1990 + **SRO 1006(I)/2021** and successors ❓ UNVERIFIED (cite not confirmed)
- Who: **Tier-1 retailers** — large retail counters, chain stores, big shops, restaurants
- Mechanic: each **counter** is registered as a POS; every receipt is pushed live; receipt
  carries FBR invoice no. + QR + logo; a small per-invoice fee applies
- Signal it's this one: notice talks about *outlets*, *counters*, *Tier-1 retailer*

### B. Sales Tax — Digital Invoicing (e-invoicing)  ← ✅ **CONFIRMED: this is the applicable regime**
Established 2026-08-12 from the client's own notice — see [07-CLIENT-PROFILE.md](07-CLIENT-PROFILE.md).

- **Statutory basis: subsection (5) of section 23 of the Sales Tax Act, 1990** ✅ VERIFIED,
  quoted verbatim from the notice:
  > "failed to comply with the Digital Invoicing requirements prescribed under subsection (5)
  > of section 23 of the Sales Tax Act, 1990, by not integrating with issuing sales tax
  > invoices through the Federal Board of Revenue's Digital Invoicing System"
- Implementing SROs: **SRO 69(I)/2025** and successors ⚠️ SECONDARY (widely cited, not read directly)
- Who: sales-tax-registered persons generally — manufacturers, importers, **wholesalers,
  distributors, traders**, exporters, retailers, service providers
- **Enforcement provisions cited in this client's notice** ✅ VERIFIED:
  | Provision | Consequence |
  |---|---|
  | Section 21 | Suspension and/or **blacklisting** |
  | Second proviso to section 8B(1) | Restriction/reduction of **input tax adjustment** |
  | Serial No. 25A of section 33 | **Penalty** |
- Mechanic: invoice JSON posted to PRAL's DI API → FBR returns an **IRN** → IRN + QR + logo
  printed on the invoice
- **This is the regime the API in [02-FBR-DI-API.md](02-FBR-DI-API.md) belongs to.**
- Signal it's this one: notice talks about *digital invoicing*, *e-invoicing*, *integration
  through a licensed integrator*

### C. Income Tax — Online Integration of Businesses
- Authority: **SRO 288(I)/2026** ⚠️ SECONDARY (entirely from a vendor blog — **must be read directly**)
- Who: reportedly **14 business categories** — restaurants, hotels, courier services, beauty
  parlours, medical providers, laboratories, hospitals, gyms, photographers/event managers,
  accountants, retailers, forex dealers, educational institutions
- Reported thresholds: doctors charging Rs. 500+/consultation; event managers above
  Rs. 50,000/event; private schools charging Rs. 1,000+/month per student; retailers assessed
  by **shop area, electricity consumption, and chain-store status**
- Reported obligations: register and integrate POS/e-invoicing software **through a licensed
  integrator**; display an integration signboard; retain records **6 years**; upload offline
  invoices **within 24 hours**
- Reported penalty: under **section 182 of the Income Tax Ordinance**
- Signal it's this one: notice cites the Income Tax Ordinance rather than the Sales Tax Act

> ⚠️ Everything in section C came from a single vendor blog. Before designing to it, pull
> SRO 288(I)/2026 from `fbr.gov.pk` and replace this section with the real text.

## The licensed-integrator constraint — read this before writing any code

⚠️ SECONDARY, but consistently reported and it shapes the whole project:

> "No entity may integrate a business with FBR's system without a five-year, non-transferable
> license from the Board." Licensed integrators reportedly need **Rs. 10 million paid-up
> capital**. **PRAL acts as a licensed integrator and provides free integration on demand.**

**What this means practically.** There are two plausible paths and we do not yet know which
one is open to the client:

| Path | How it works | Feasible for us? |
|---|---|---|
| **P1 — Taxpayer's own token** | The business registers on IRIS, gets its own PRAL bearer token, and its own software posts directly | ✅ Likely. The PRAL spec is written for "Supply Chain Operators" integrating their own ERP. This is the assumption we proceed on. |
| **P2 — Through a licensed integrator** | Our software talks to an integrator's API, not FBR's | Possible fallback; adds a third party and a fee |
| **P3 — We become a licensed integrator** | Rs. 10m capital, FBR license | ❌ Not happening |

**→ Blocking question:** can the client obtain its own token from IRIS? See
[06-OPEN-QUESTIONS.md](06-OPEN-QUESTIONS.md) Q1. If the answer is no, the architecture changes
completely and this project may not be viable as scoped.

## Timeline
- ⚠️ SECONDARY: a **July 2026** deadline has been widely reported, with larger businesses
  phased in first and smaller ones later. Today is **August 2026** — so if that reporting is
  right, the deadline has already passed, which is consistent with the client receiving a
  notice now. Treat the matter as **urgent** but verify the actual date from the notice.

## Design consequences (regardless of which regime)
These fall out of the rules above and should be treated as hard requirements:

1. **Every issued invoice must carry the FBR IRN, QR code, and DI logo.** No IRN → the
   invoice is not compliant → do not let the software print a "final" invoice without one.
2. **Offline invoices must be uploaded within 24 hours** (⚠️ SECONDARY). The offline queue is
   therefore a compliance feature, not a nicety. It needs a visible age indicator and an alarm
   as items approach the window.
3. **Records must be retained 6 years** (⚠️ SECONDARY). Never hard-delete an invoice; use
   credit/debit notes for corrections. Design for soft-delete + full audit trail from day one.
4. **No tampering.** The audit trail must make after-the-fact edits impossible or at least
   evident. Do not build a "edit posted invoice" feature.
5. **Corrections go through debit/credit notes**, and only within **180 days** of the original
   invoice (✅ VERIFIED — error code 0034).

## Sources
- [PRAL, *Technical Specification for DI API* v1.12](../reference/PRAL-DI-API-v1.12.pdf) — ✅ primary, in repo
- [FBR download portal — DI API spec](https://download1.fbr.gov.pk/Docs/20257301172130815TechnicalDocumentationforDIAPIV1.12.pdf)
- [Switcher Techno — SRO 288(I)/2026 summary](https://www.switchertechno.com/sro-288-2026-fbr-online-integration-of-businesses) — ⚠️ vendor blog
- [Switcher Techno — July 2026 deadline & penalties](https://www.switchertechno.com/fbr-digital-invoicing-july-2026-deadline-penalties/) — ⚠️ vendor blog
