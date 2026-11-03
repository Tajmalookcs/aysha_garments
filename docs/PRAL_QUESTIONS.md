# Questions for PRAL support

Raise these at https://dicrm.pral.com.pk with **+ New Case**, Query Type **Integration**.

**Title:** Questions on export invoices, QR size and printed invoice details

**Description:**

We're integrating our own invoicing software with Digital Invoicing, with PRAL as Licensed Integrator, using Technical Specification v1.12 and User Manual v1.5. Please confirm:

1. **Export invoices.** The FBR FAQ says a digital invoice is required for all sales reported in Annexure-C.
   - Must export sales be sent through Digital Invoicing?
   - Which scenario and sale type apply? Is it SN007, Goods at zero-rate?
   - What should we send in `buyerNTNCNIC`, `buyerProvince`, `buyerAddress` and `buyerRegistrationType` for a foreign buyer with no NTN or Pakistani province?
2. **QR code size.** Sales Tax Rule 150R(13) gives 7x7 mm, but the Technical Specification gives version 2.0 (25x25) at 1.0 x 1.0 inch. Which applies to Digital Invoicing?
3. **QR code content.** Rule 150R(4)(e) says the QR is based on the unique FBR invoice number. Should it hold only the `invoiceNumber` returned by the API?
4. **Software registration number.** Rule 150R(13) lists the e-invoicing software registration number on the invoice. What is this number when PRAL is the integrator, and where do we find it?
5. **Debit note reason.** Errors 0027 and 0028 mention a reason for debit and credit notes, but the specification has no field for it. Which field should we use?
6. **Credit notes.** The specification lists only Sale Invoice and Debit Note, but some errors mention credit notes. How should a sales return be reported?
7. **Changing a sent invoice.** STGO 01 of 2026 mentions a 72-hour period. How is a posted invoice changed or cancelled through the API within that period?
8. **Sole proprietors.** Should `sellerNTNCNIC` hold the 7 digit NTN or the 13 digit CNIC for a sole proprietor?
9. **Newer documents.** Is there a newer version than Technical Specification v1.12 or User Manual v1.5?
