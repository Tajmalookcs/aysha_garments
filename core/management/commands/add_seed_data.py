"""Add one client's records from a local file. The file holds tax numbers, so it never goes in the repository."""

import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from billing.models import Invoice
from billing.services import InvoiceError, LineInput, create_invoice
from core.models import Company, Customer, Product
from fbr.views import assigned_scenarios

TEST_PREFIX = "TEST-"
PRODUCT_DECIMALS = ("rate_percent", "further_tax_percent", "fed_percent", "fixed_notified_value", "price_per_piece")


def _add_product(company, details):
    fields = {k: Decimal(str(v)) if k in PRODUCT_DECIMALS else v for k, v in details.items() if k != "name"}
    product = Product.objects.filter(company=company, name=details["name"]).first()
    if product:
        return product, False
    product = Product(company=company, name=details["name"], **fields)
    product.full_clean()
    product.save()
    return product, True


def _add_buyer(company, details):
    fields = {k: v for k, v in details.items() if k != "name"}
    if "strn" in fields:
        fields["strn"] = fields["strn"].replace("-", "").replace(" ", "")
    buyer = Customer.objects.filter(company=company, name=details["name"]).first()
    if buyer:
        return buyer, False
    buyer = Customer(company=company, name=details["name"], **fields)
    buyer.full_clean()
    buyer.save()
    return buyer, True


def _add_test_invoice(company, user, details):
    """Saved only. Nothing is approved or sent, so the owner still decides when it goes to FBR."""
    scenario = details["scenario"]
    reference = f"{TEST_PREFIX}{scenario}"
    if company.invoices.filter(your_reference=reference).exists():
        return False
    product = Product.objects.get(company=company, name=details["product"])
    buyer = Customer.objects.get(company=company, name=details["buyer"])
    line = LineInput(product, "kg" if product.is_kg else "piece", details["quantity"], "", details["price"])
    invoice = create_invoice(
        company=company, customer=buyer, invoice_date=timezone.localdate(), lines=[line],
        your_reference=reference, user=user,
    )
    Invoice.objects.filter(pk=invoice.pk).update(scenario_id=scenario)
    return True


class Command(BaseCommand):
    help = "Add a client's products and buyers, and sandbox test records, from a local file. Safe to run more than once."

    def add_arguments(self, parser):
        parser.add_argument("--file", help="The data file. By default, seed_data.json in the instance folder.")
        parser.add_argument("--real-only", action="store_true", help="Skip the test records, for a client's install.")

    def handle(self, *args, **options):
        path = Path(options["file"] or Path(settings.INSTANCE_DIR) / "seed_data.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            raise CommandError(f"No data file found at {path}.")
        except ValueError as exc:
            raise CommandError(f"The data file can't be read: {exc}")

        companies = Company.objects.all()
        if companies.count() != 1:
            raise CommandError("This needs exactly one company. Finish the setup screen in the app first.")
        company = companies.get()
        member = company.memberships.select_related("user").first()
        user = member.user if member else get_user_model().objects.first()

        add_tests = not options["real_only"]
        if add_tests and company.fbr_mode != "sandbox":
            add_tests = False
            self.stdout.write("This company isn't in sandbox mode, so no test records were added.")

        try:
            with transaction.atomic():
                counts = self._add_all(company, user, data, add_tests)
        except (ValidationError, InvoiceError, KeyError, TypeError, Product.DoesNotExist, Customer.DoesNotExist) as exc:
            raise CommandError(f"Nothing was added. There's a problem in the data file: {exc}")
        self.stdout.write(
            f"Added {counts['products']} products, {counts['buyers']} buyers and {counts['invoices']} test invoices "
            f"to {company.business_name}. Nothing was sent to FBR."
        )

    def _add_all(self, company, user, data, add_tests):
        counts = {"products": 0, "buyers": 0, "invoices": 0}
        products = list(data.get("products", []))
        buyers = list(data.get("buyers", []))
        if add_tests:
            products += data.get("test_products", [])
            buyers += data.get("test_buyers", [])
        for details in products:
            counts["products"] += _add_product(company, details)[1]
        for details in buyers:
            counts["buyers"] += _add_buyer(company, details)[1]
        if add_tests:
            assigned = assigned_scenarios(company)
            for details in data.get("test_invoices", []):
                if details["scenario"] not in assigned:
                    self.stdout.write(f"Skipped {details['scenario']}: it isn't assigned to this company.")
                    continue
                counts["invoices"] += _add_test_invoice(company, user, details)
        return counts
