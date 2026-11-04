from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from billing.services import next_invoice_number
from core.models import Company, Membership, Product


def make(name, ntn):
    return Company.objects.create(business_name=name, ntn=f"{ntn}-1", province="PUNJAB", address="A", invoice_prefix="AG")


class DemoProductTests(TestCase):
    def test_adds_labelled_samples_once(self):
        company = make("A", "1234567")
        out = StringIO()
        call_command("add_demo_products", stdout=out)
        self.assertIn("Added 11", out.getvalue())
        call_command("add_demo_products", stdout=StringIO())
        products = Product.objects.filter(company=company)
        self.assertEqual(products.count(), 11)
        for product in products:
            self.assertTrue(product.name.startswith("Demo "))
            product.full_clean()

    def test_needs_a_company(self):
        with self.assertRaises(CommandError):
            call_command("add_demo_products", stdout=StringIO())

    def test_several_companies_need_a_name(self):
        a = make("A", "1234567")
        b = make("B", "7654321")
        with self.assertRaises(CommandError):
            call_command("add_demo_products", stdout=StringIO())
        call_command("add_demo_products", company="b", stdout=StringIO())
        self.assertEqual(b.products.count(), 11)
        self.assertEqual(a.products.count(), 0)


class DemoDataTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        self.company = make("A", "1234567")
        self.user = get_user_model().objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")

    def test_full_set_once_and_every_status_shows(self):
        call_command("add_demo_data", stdout=StringIO())
        call_command("add_demo_data", stdout=StringIO())
        self.assertEqual(self.company.products.count(), 11)
        self.assertEqual(self.company.customers.count(), 7)
        self.assertEqual(self.company.invoices.count(), 10)
        counts = {s: self.company.invoices.filter(status=s).count() for s in ["saved", "waiting", "held", "accepted", "rejected"]}
        self.assertEqual(counts, {"saved": 3, "waiting": 2, "held": 2, "accepted": 2, "rejected": 1})
        for customer in self.company.customers.all():
            self.assertTrue(customer.name.startswith("Demo "))
            customer.full_clean()
        for invoice in self.company.invoices.all():
            self.assertTrue(invoice.your_reference.startswith("DEMO"))
            if invoice.fbr_invoice_number:
                self.assertTrue(invoice.fbr_invoice_number.startswith("DEMO-IRN-"))
            self.assertGreater(invoice.grand_total, 0)

    def test_screens_open_with_demo_data(self):
        call_command("add_demo_data", stdout=StringIO())
        self.client.force_login(self.user)
        for url in ["/", "/invoices/", "/invoices/new/", "/products/", "/customers/"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for invoice in self.company.invoices.all():
            self.assertEqual(self.client.get(f"/invoices/{invoice.pk}/").status_code, 200)
        self.assertContains(self.client.get("/"), "3 invoices need your approval")

    def test_new_invoice_after_demo_gets_next_number(self):
        call_command("add_demo_data", stdout=StringIO())
        self.assertEqual(next_invoice_number(self.company), "AG-000011")


class PageExpiredTests(TestCase):
    def test_stale_form_gets_a_clear_page_and_saves_nothing(self):
        from django.contrib.auth import get_user_model
        from django.test import Client

        company = make("A", "1234567")
        user = get_user_model().objects.create_user("owner", password="x")
        Membership.objects.create(user=user, company=company, role="admin")
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.post("/company/", {"business_name": "CHANGED"})
        self.assertContains(response, "This page has expired", status_code=403)
        company.refresh_from_db()
        self.assertEqual(company.business_name, "A")


class BackupTests(TestCase):
    def test_refuses_inside_project_and_empty_install(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from django.conf import settings
        from django.test import override_settings

        with self.assertRaisesMessage(CommandError, "outside the project"):
            call_command("backup_data", str(Path(settings.BASE_DIR) / "backups"), stdout=StringIO())
        with TemporaryDirectory() as tmp:
            missing = {**settings.DATABASES["default"], "NAME": Path(tmp) / "none.sqlite3"}
            with override_settings(DATABASES={"default": missing}):
                with self.assertRaisesMessage(CommandError, "nothing to back up"):
                    call_command("backup_data", tmp, stdout=StringIO())
