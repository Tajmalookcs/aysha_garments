"""Add a full set of clearly labelled demo records. None of it is real or sent to FBR."""

from datetime import timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice
from billing.services import LineInput, approve_invoice, create_invoice
from core.models import Company, Customer, Product

R, U, F = Customer.Kind.REGISTERED, Customer.Kind.UNREGISTERED, Customer.Kind.FOREIGN

# Name, type, obviously fake NTN, province, country, address.
CUSTOMERS = [
    ("Demo Textile Mills", R, "0000001", "PUNJAB", "", "Demo Road, Faisalabad"),
    ("Demo Weaving Company", R, "0000002", "PUNJAB", "", "Demo Road, Lahore"),
    ("Demo Home Textiles", R, "0000003", "SINDH", "", "Demo Road, Karachi"),
    ("Demo Walk-in Buyer", U, "", "PUNJAB", "", "Demo Road, Faisalabad"),
    ("Demo Retail Shop", U, "", "PUNJAB", "", "Demo Road, Multan"),
    ("Demo Exports LLC", F, "", "", "United Arab Emirates", "Demo Road, Dubai"),
    ("Demo Imports Ltd", F, "", "", "United Kingdom", "Demo Road, Bradford"),
]

# Days ago, customer, final state, lines of (product, sold by, quantity, pieces per lot, discount).
# A pack line uses the fourth place for its KG.
INVOICES = [
    (2, "Demo Textile Mills", "saved", [("Demo Duvet Set, Processing", "pack", "400", "1200", "0"), ("Demo Duvet Set, Processing", "pack", "100", "280", "0")]),
    (2, "Demo Textile Mills", "saved", [("Demo Processing Work", "kg", "750", "", "0")]),
    (9, "Demo Textile Mills", "accepted", [("Demo Quilt, Double", "lot", "4", "25", "5000")]),
    (7, "Demo Retail Shop", "accepted", [("Demo Cushion, 16 inch", "piece", "40", "", "0"), ("Demo Pillow, Standard", "piece", "30", "", "1000")]),
    (5, "Demo Home Textiles", "rejected", [("Demo Comforter, King", "piece", "20", "", "0")]),
    (3, "Demo Weaving Company", "approved", [("Demo Sleeping Bag", "lot", "2", "30", "2000"), ("Demo Pouffe", "piece", "15", "", "0")]),
    (1, "Demo Textile Mills", "approved", [("Demo Quilt, Single", "lot", "3", "40", "0")]),
    (1, "Demo Exports LLC", "saved", [("Demo Eiderdown", "lot", "5", "100", "0")]),
    (0, "Demo Imports Ltd", "saved", [("Demo Cushion, 20 inch", "lot", "10", "60", "0")]),
    (0, "Demo Walk-in Buyer", "saved", [("Demo Pillow, Fibre Filled", "piece", "4", "", "200")]),
    (0, "Demo Home Textiles", "saved", [("Demo Quilt, Double", "lot", "2", "20", "3000"), ("Demo Cushion, 16 inch", "piece", "50", "", "0")]),
]


class Command(BaseCommand):
    help = "Add demo products, customers and invoices. Safe to run more than once."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Business name, needed when there is more than one company.")

    def handle(self, *args, **options):
        name = options.get("company")
        companies = Company.objects.filter(business_name__iexact=name) if name else Company.objects.all()
        count = companies.count()
        if count == 0:
            raise CommandError("No company found. Finish the setup screen in the app first." if not name
                               else f"No company is named {name}.")
        if count > 1:
            names = ", ".join(c.business_name for c in companies)
            raise CommandError(f"There is more than one company ({names}). Run it with --company and the name.")
        company = companies.get()

        with transaction.atomic():
            call_command("add_demo_products", company=company.business_name, stdout=self.stdout)
            customers = self._customers(company)
            invoices = self._invoices(company)
        self.stdout.write(f"Added {customers} demo customers and {invoices} demo invoices to {company.business_name}.")

    def _customers(self, company):
        added = 0
        for name, kind, ntn, province, country, address in CUSTOMERS:
            _, created = Customer.objects.get_or_create(
                company=company, name=name,
                defaults={"kind": kind, "ntn_cnic": ntn, "province": province, "country": country, "address": address},
            )
            added += created
        return added

    def _invoices(self, company):
        if company.invoices.filter(your_reference__startswith="DEMO").exists():
            return 0
        member = company.memberships.select_related("user").first()
        user = member.user if member else None
        today = timezone.localdate()
        for days_ago, customer_name, state, rows in INVOICES:
            lines = []
            for product_name, sold_by, quantity, per_lot, discount in rows:
                product = Product.objects.get(company=company, name=product_name)
                if sold_by == "pack":
                    lines.append(LineInput(product, sold_by, quantity, "", product.price_per_piece, Decimal(discount), kg=per_lot, pack_unit=product.pack_unit))
                else:
                    lines.append(LineInput(product, sold_by, quantity, per_lot, product.price_per_piece, Decimal(discount)))
            invoice = create_invoice(
                company=company,
                customer=Customer.objects.get(company=company, name=customer_name),
                invoice_date=today - timedelta(days=days_ago),
                lines=lines,
                your_reference="DEMO order",
                user=user,
            )
            if state in ("approved", "accepted", "rejected"):
                invoice = approve_invoice(invoice, user)
            if state == "accepted":
                invoice.status = Invoice.Status.ACCEPTED
                invoice.fbr_invoice_number = f"DEMO-IRN-{invoice.pk:06d}"
                invoice.fbr_environment = "demo"
                invoice.save(update_fields=["status", "fbr_invoice_number", "fbr_environment"])
            elif state == "rejected":
                invoice.status = Invoice.Status.REJECTED
                invoice.save(update_fields=["status"])
        return len(INVOICES)
