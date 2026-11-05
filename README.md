# Aysha Garments

FBR digital invoicing system for manufacturing units, starting with Ayesha Garments (see [Project Brief](docs/PROJECT_BRIEF.md)).

## Locations

| What | Where |
| --- | --- |
| Local project folder | `D:\aysha_garments` |
| GitHub repository | https://github.com/Tajmalookcs/aysha_garments |

## Folder structure

```
aysha_garments/
├── README.md               Project overview (this file)
├── CLAUDE.md               Working rules for Claude
├── billing/                Invoices, tax calculation, numbering and approval
├── core/                   Companies, users, products and customers
├── fbr/                    FBR token, lists, sending and call log
├── config/                 Django settings
├── templates/, static/     Screens, design and local Bootstrap, icons and fonts
├── start.bat               Starts the app on Windows
├── add_demo_data.bat       Adds labelled demo products, customers and invoices
├── start_app.vbs           Opens the app with no black window, and adds desktop shortcuts
├── stop_app.vbs            Stops the app when it runs with no window
├── add_seed_data.bat       Adds a client's records and sandbox test invoices from instance/seed_data.json
├── backup.bat              Backs up the database, keys and media
├── instance/               Local database and secret keys; created on first run, never pushed
├── design_preview/         The approved design preview
├── docs/
│   ├── PROJECT_BRIEF.md    What we are building, and open questions
│   ├── CLIENT_SETUP_GUIDE.md  Steps for each new client, with the sandbox values that passed
│   ├── seed_data.example.json  Starting point for a client's instance/seed_data.json
│   ├── BUILD_PLANS.md      Plan and approval record for each build
│   ├── PRAL_QUESTIONS.md   Questions to ask PRAL support
│   └── 01 to 04            FBR rules, API, codes and draft data model
├── reference/              Official PRAL API specification
├── licensing/              Demo password's hash and the public key; never the private key
└── media/                  Client documents; stays on the local computer, never pushed
```

## Status

Core app built: company, login, products, customers, invoices and approval. Invoice printing is built, including the QR code. The sales register, backup, lookups, buyer checks and debit notes are built. Invoices follow the client's slip layout, with one Total KG. They work by KG, which is the default, by pack with KG, or by piece or lot. The demo, registration and developer password are built. Production mode is built but off until a registered copy switches it on. All 9 assigned scenarios have passed the FBR sandbox. Production isn't tested yet.

## Run it

Install Python 3.12 or newer, then double-click `start.bat`. The first run needs internet to install the packages. The app then opens at http://127.0.0.1:8000 and works without internet.

Run the tests with `python manage.py test`.

## Demo and registration

Each client gets a separate install, with one company and one user. A new install runs as a 15 day demo.

Developer only, on your own computer. Keep the keys folder outside this project and back it up:

```
python manage.py setup_licensing --keys-dir D:\licence_keys
python manage.py make_licence --keys-dir D:\licence_keys --ntn 0000000-0 --name "BUSINESS NAME" --out D:\licence_keys\licence_client.json
```

The first command makes the keys and asks for the demo password. The second makes one client's registration file. The client adds that file under Registration.

## Seed data

`add_seed_data.bat` reads `instance/seed_data.json`, which holds tax numbers and is never pushed. It adds the client's products and buyers, then test products, a test buyer and one saved test invoice for each sandbox scenario. It can run more than once. It keeps records that already exist and sends nothing to FBR.

For a client's install, use `manage.py add_seed_data --real-only`, which skips the test records.

## New clients

Follow [the new client setup guide](docs/CLIENT_SETUP_GUIDE.md).

## How we work

- All work is done locally in `D:\aysha_garments`.
- Nothing is pushed to GitHub until the owner asks for it.
- Every build starts with a plan, and work continues only after approval.
