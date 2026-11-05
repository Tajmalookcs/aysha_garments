# New client setup guide

The steps for each new client, based on the first client's setup in November 2026. Follow them in order.

This repository is public. Keep tax numbers, CNICs, IP addresses, tokens and passwords out of this guide and out of every tracked file.

## Before you start

Done once by the developer, on the developer's computer. This is already done.

- Make the signing keys with `setup_licensing`. The private key stays in `D:\licence_keys`, outside this project. Back it up.
- `licensing/demo.json` and `licensing/public_key.pem` are in the repository. New installs need them.

## 1. Collect from the client

- [ ] NTN, STRN, business name as FBR has it, address and province
- [ ] FBR registration status in IRIS, and the assigned sandbox scenarios
- [ ] Sandbox token
- [ ] Static IP, added in IRIS
- [ ] Annex-C report and recent invoices, saved in `media/`, which is never pushed
- [ ] Products: name, HS code, unit, sale type, rate, price, and pack unit if charged by the pack
- [ ] Buyers: name, NTN or CNIC, STRN, province and address
- [ ] Whether it sells to unregistered buyers
- [ ] Total KG for each invoice, if it's charged by the pack and reports KG
- [ ] Last invoice number before the app

The Annex-C report answers most product and buyer questions. Check the rest with the client or the tax consultant.

## 2. Install and set up

1. Get the latest `main`, and run `start.bat`.
2. Finish the setup screen, using the demo password. After the first run, use `start_app.vbs`, which opens the app with no black window and adds desktop shortcuts to start and stop it.
3. Under FBR setup, save the sandbox token, enter the assigned scenarios, and download FBR's lists.

## 3. Add the data with the seed file

1. Copy `docs/seed_data.example.json` to `instance/seed_data.json`. The `instance` folder is never pushed.
2. Replace the example products and buyers with the client's.
3. Keep test records only for this client's assigned scenarios. The command skips scenarios that aren't assigned.
4. Run `add_seed_data.bat`.

Each test invoice is saved, with its scenario already chosen and a job number starting with `TEST-`. Nothing goes to FBR until someone presses Approve and send. Running it again adds nothing new.

STRN is saved as digits only. Invoices show the dashes.

The invoice form asks for Qty, Unit, Product and Rate on each line, and one Total KG. It asks for a separate Total KG only for lines that differ in HS code, sale type, rate or SRO, because FBR needs their weights separately. Invoices show each line's HS code in its own column.

## 4. Run the sandbox scenarios

Before any real FBR test, the owner chooses the time and the connection, because FBR checks the IP. Only the owner runs real tests.

1. Open each test invoice, and check that it says Sandbox mode and shows the right scenario.
2. Press Approve and send to FBR once.
3. Check the result in IRIS, under Sandbox Testing.

### Values that passed on 2026-11-05

Rates, SROs and items came from FBR's lookups for Punjab on 2026-11-05, unless noted. They can change, so check them again under Find tax rates and Lookups. Where FBR offered several choices, this is just the one tested. All of these are test values, not advice for real invoices.

| Scenario | Sale type | HS code | Unit | Rate text | Sales tax rate | SRO schedule | SRO item |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SN001 | Goods at standard rate (default) | 6302.3990 | KG | 18% | 18 | | |
| SN002 | Goods at standard rate (default) | 6302.3990 | KG | 18% | 18 | | |
| SN005 | Goods at Reduced Rate | 6302.3990 | KG | 1% | 1 | EIGHTH SCHEDULE Table 1 | 70 |
| SN006 | Exempt goods | 6302.3990 | KG | Exempt | 0 | 6th Schd Table I | 100 |
| SN007 | Goods at zero-rate | 6302.3990 | KG | 0% | 0 | FIFTH SCHEDULE | 1(i) |
| SN009 | Cotton ginners | 6302.3990 | KG | 18% | 18 | | |
| SN016 | Processing/Conversion of Goods | 6302.3990 | KG | 18% | 18 | | |
| SN017 | Goods (FED in ST Mode) | 2710.1240 | Liter | 18% and Rs. 80 per Liter | 118 | | |
| SN024 | Goods as per SRO.297(\|)/2023 | 6302.3990 | KG | 25% | 25 | 297(I)/2023-Table-I | 12 |

SN002 used an unregistered buyer with no NTN or CNIC, and further tax of 4%.

SN017 needs exact values: quantity 1, price 100 and sales tax 118. They came from a Manager.io forum post, not an official document. FBR's formula is unconfirmed, so never use them on a real invoice.

### Other scenarios

These haven't been tested. To find their values:

1. Under Find tax rates, choose the transaction type and province. Note the rate text and Rate ID.
2. Under Lookups, enter the Rate ID to find its SRO schedules, then the SRO ID to find its items.
3. Under Lookups, check the units for the HS code.
4. Add the product and test invoice to `instance/seed_data.json`, and run the seed again.

### Lessons from the first run

- Copy sale types from FBR's downloaded list. PRAL's document spaces some differently.
- **0052, HS code doesn't match the sale type:** change the HS code, not the sale type. The sale type comes from the scenario.
- **0131, sales tax doesn't match for FED in ST Mode:** use the SN017 values above.
- **Couldn't reach FBR:** the invoice stays waiting and is marked as issued offline. Send it again when the connection returns.
- **Unknown result, check in IRIS:** don't send it again. Look for it in IRIS first.
- The client's own invoice number goes in `sourceInvoiceNo`. PRAL's specification and the IRIS sample don't list it. `invoiceNumber` and `invoiceRefNo` were accepted, but left Source Invoice No. empty in IRIS.
- For the first client, the sandbox and production both accepted invoices while the IP still showed Pending in IRIS. Don't assume this holds for every client or connection.
- The Sold by list on an invoice line shows KG options or piece and lot, based on the product's FBR unit.
- PRAL support is at https://dicrm.pral.com.pk. Log in with the IRIS option. Case titles can have at most 50 characters, and descriptions at most 500. IP Whitelisting is one of the query types.

## 5. Register and go live

1. Make the client's registration file on the developer's computer:

   ```
   venv\Scripts\python manage.py make_licence --keys-dir D:\licence_keys --ntn 0000000-0 --name "BUSINESS NAME" --out D:\licence_keys\licence_client.json
   ```

   Use the NTN exactly as saved in the app. Each client gets its own developer password, of at least 16 characters.
2. Make a fresh database for real invoices: move the test database out of `instance`, then run `start.bat` and finish setup again.
3. Run `manage.py add_seed_data --real-only`, which skips the test records.
4. Add the registration file under Registration. The demo ends.
5. Check that the IP is approved in IRIS, and get the production token.
6. Save the production token in FBR setup, and enter the client's real last invoice number before the first invoice.
7. Switch to Production mode only with the client's agreement. From then on, invoices are real.

The first client's first real invoice was accepted on 2026-11-06. Check the print and the invoice in IRIS after the first real invoice for each client.
