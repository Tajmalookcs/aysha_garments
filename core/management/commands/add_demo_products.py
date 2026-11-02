"""Add clearly labelled sample products for a demo. These are not real tax details."""

from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from core.models import Company, Product

# Name, price per piece. All prices, codes and rates here are placeholders.
SAMPLES = [
    ("Demo Quilt, Single", "2800"),
    ("Demo Quilt, Double", "4200"),
    ("Demo Comforter, King", "6500"),
    ("Demo Eiderdown", "5200"),
    ("Demo Cushion, 16 inch", "650"),
    ("Demo Cushion, 20 inch", "850"),
    ("Demo Pillow, Standard", "900"),
    ("Demo Pillow, Fibre Filled", "1200"),
    ("Demo Pouffe", "3500"),
    ("Demo Sleeping Bag", "5400"),
]


class Command(BaseCommand):
    help = "Add sample products for a demo. Safe to run more than once."

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

        added = 0
        for product_name, price in SAMPLES:
            _, created = Product.objects.get_or_create(
                company=company,
                name=product_name,
                defaults={
                    "hs_code": "0000.0000",
                    "uom": "Sample unit",
                    "sale_type": "Sample only, not for FBR",
                    "rate_label": "18%",
                    "rate_percent": Decimal("18"),
                    "further_tax_percent": Decimal("4"),
                    "price_per_piece": Decimal(price),
                },
            )
            added += created
        self.stdout.write(f"Added {added} sample products to {company.business_name}.")
