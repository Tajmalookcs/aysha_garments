import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice
from billing.services import (
    InvoiceError,
    LineInput,
    approve_invoice,
    compute_line,
    create_invoice,
    delete_invoice,
    update_invoice,
)
from core.models import Company, Customer, Membership, Product

User = get_user_model()


def make_company(name, prefix="AG", ntn="1234567"):
    return Company.objects.create(business_name=name, ntn_cnic=ntn, province="PUNJAB", address="Addr", invoice_prefix=prefix)


def make_product(company, name="Quilt", price="4200", rate="18", further="4"):
    return Product.objects.create(
        company=company, name=name, hs_code="0000.0000", uom="Numbers, pieces, units", sale_type="Sample",
        rate_label=f"{rate}%", rate_percent=Decimal(rate), further_tax_percent=Decimal(further), price_per_piece=Decimal(price),
    )


def make_customer(company, name="Buyer", kind=Customer.Kind.REGISTERED):
    return Customer.objects.create(
        company=company, name=name, kind=kind, ntn_cnic="7654321" if kind == Customer.Kind.REGISTERED else "",
        province="PUNJAB", address="Addr", country="UAE" if kind == Customer.Kind.FOREIGN else "",
    )


class TaxTests(TestCase):
    def setUp(self):
        self.company = make_company("A")
        self.product = make_product(self.company)

    def test_registered_buyer_has_no_further_tax(self):
        r = compute_line(LineInput(self.product, "piece", "1", "", "4200"), Customer.Kind.REGISTERED)
        self.assertEqual(r["sales_tax"], Decimal("756.00"))
        self.assertEqual(r["further_tax"], Decimal("0.00"))
        self.assertEqual(r["total"], Decimal("4956.00"))

    def test_unregistered_buyer_pays_further_tax(self):
        r = compute_line(LineInput(self.product, "piece", "1", "", "4200"), Customer.Kind.UNREGISTERED)
        self.assertEqual(r["further_tax"], Decimal("168.00"))
        self.assertEqual(r["total"], Decimal("5124.00"))

    def test_lots_become_pieces(self):
        r = compute_line(LineInput(self.product, "lot", "3", "50", "4200"), Customer.Kind.UNREGISTERED)
        self.assertEqual(r["quantity"], Decimal("150"))
        self.assertEqual(r["pieces_per_lot"], 50)
        self.assertEqual(r["total"], Decimal("768600.00"))

    def test_tax_is_worked_out_after_discount(self):
        r = compute_line(LineInput(self.product, "piece", "1", "", "1000", "100"), Customer.Kind.UNREGISTERED)
        self.assertEqual(r["value_excl_tax"], Decimal("1000.00"))
        self.assertEqual(r["sales_tax"], Decimal("162.00"))
        self.assertEqual(r["further_tax"], Decimal("36.00"))
        self.assertEqual(r["total"], Decimal("1098.00"))

    def test_rounds_half_up_to_paisa(self):
        p = make_product(self.company, "Small", price="0.25", rate="18")
        self.assertEqual(compute_line(LineInput(p, "piece", "1", "", "0.25"), "registered")["sales_tax"], Decimal("0.05"))

    def test_bad_input_is_refused(self):
        bad = [
            LineInput(self.product, "piece", "0", "", "10"),
            LineInput(self.product, "piece", "-1", "", "10"),
            LineInput(self.product, "piece", "abc", "", "10"),
            LineInput(self.product, "piece", "NaN", "", "10"),
            LineInput(self.product, "piece", "1", "", "0"),
            LineInput(self.product, "lot", "1", "", "10"),
            LineInput(self.product, "lot", "1", "2.5", "10"),
            LineInput(self.product, "crate", "1", "", "10"),
            LineInput(self.product, "piece", "1", "", "10", "11"),
            LineInput(self.product, "piece", "1", "", "10", "-1"),
        ]
        for line in bad:
            with self.subTest(line=line), self.assertRaises(InvoiceError):
                compute_line(line, "registered")


class InvoiceFlowTests(TestCase):
    def setUp(self):
        self.company = make_company("A")
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.admin = User.objects.create_user("admin", password="x")
        Membership.objects.create(user=self.admin, company=self.company, role="admin")

    def _invoice(self, customer=None, company=None):
        return create_invoice(
            company=company or self.company, customer=customer or self.customer, invoice_date=date(2026, 11, 2),
            lines=[LineInput(self.product, "piece", "2", "", "100")], user=self.admin,
        )

    def test_new_invoice_is_saved_not_approved(self):
        inv = self._invoice()
        self.assertEqual(inv.status, Invoice.Status.SAVED)
        self.assertIsNone(inv.approved_at)
        self.assertFalse(inv.is_final)

    def test_numbers_run_in_sequence(self):
        self.assertEqual(self._invoice().number, "AG-000001")
        self.assertEqual(self._invoice().number, "AG-000002")

    def test_each_company_has_its_own_numbers(self):
        other = make_company("B", prefix="BB", ntn="7777777")
        self._invoice()
        p = make_product(other)
        inv = create_invoice(company=other, customer=make_customer(other), invoice_date=date(2026, 11, 2),
                             lines=[LineInput(p, "piece", "1", "", "1")])
        self.assertEqual(inv.number, "BB-000001")

    def test_approve_once_only(self):
        inv = self._invoice()
        approved = approve_invoice(inv, self.admin)
        self.assertEqual(approved.status, Invoice.Status.WAITING)
        self.assertEqual(approved.approved_by, self.admin)
        with self.assertRaises(InvoiceError):
            approve_invoice(approved, self.admin)

    def test_edit_keeps_number_and_replaces_lines(self):
        inv = self._invoice()
        unreg = make_customer(self.company, "Walk-in", Customer.Kind.UNREGISTERED)
        out = update_invoice(inv, customer=unreg, invoice_date=date(2026, 11, 3),
                             lines=[LineInput(self.product, "piece", "1", "", "1000", "100")], your_reference="R1")
        self.assertEqual(out.number, inv.number)
        self.assertEqual(out.buyer_name, "Walk-in")
        self.assertEqual(out.items.count(), 1)
        self.assertEqual(out.grand_total, Decimal("1098.00"))
        self.assertEqual(out.your_reference, "R1")

    def test_failed_edit_changes_nothing(self):
        inv = self._invoice()
        with self.assertRaises(InvoiceError):
            update_invoice(inv, customer=self.customer, invoice_date=date(2026, 11, 3),
                           lines=[LineInput(self.product, "piece", "0", "", "1")])
        inv.refresh_from_db()
        self.assertEqual(inv.invoice_date, date(2026, 11, 2))
        self.assertEqual(inv.items.count(), 1)

    def test_edit_can_move_between_saved_and_held(self):
        inv = self._invoice()
        foreign = make_customer(self.company, "Abroad", Customer.Kind.FOREIGN)
        line = [LineInput(self.product, "piece", "1", "", "1")]
        out = update_invoice(inv, customer=foreign, invoice_date=date(2026, 11, 2), lines=line)
        self.assertEqual(out.status, Invoice.Status.HELD)
        out = update_invoice(out, customer=self.customer, invoice_date=date(2026, 11, 2), lines=line)
        self.assertEqual(out.status, Invoice.Status.SAVED)

    def test_approved_invoice_is_locked(self):
        inv = approve_invoice(self._invoice(), self.admin)
        with self.assertRaises(InvoiceError):
            update_invoice(inv, customer=self.customer, invoice_date=date(2026, 11, 2),
                           lines=[LineInput(self.product, "piece", "1", "", "1")])
        with self.assertRaises(InvoiceError):
            delete_invoice(inv)
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())

    def test_deleted_number_is_used_again(self):
        first = self._invoice()
        second = self._invoice()
        third = self._invoice()
        delete_invoice(second)
        self.assertEqual(self._invoice().number, "AG-000002")
        self.assertEqual(self._invoice().number, "AG-000004")
        self.assertEqual((first.number, third.number), ("AG-000001", "AG-000003"))

    def test_last_deleted_number_is_used_again(self):
        self._invoice()
        delete_invoice(self._invoice())
        self.assertEqual(self._invoice().number, "AG-000002")

    def test_approved_invoice_keeps_its_number_taken(self):
        approve_invoice(self._invoice(), self.admin)
        self.assertEqual(self._invoice().number, "AG-000002")

    def test_foreign_invoice_is_held_and_cannot_be_approved(self):
        inv = self._invoice(customer=make_customer(self.company, "Abroad", Customer.Kind.FOREIGN))
        self.assertEqual(inv.status, Invoice.Status.HELD)
        with self.assertRaises(InvoiceError):
            approve_invoice(inv, self.admin)

    def test_invoice_keeps_details_after_customer_and_product_change(self):
        inv = self._invoice()
        self.customer.name = "Renamed"
        self.customer.save()
        self.product.hs_code = "9999.9999"
        self.product.save()
        inv.refresh_from_db()
        self.assertEqual(inv.buyer_name, "Buyer")
        self.assertEqual(inv.items.get().hs_code, "0000.0000")

    def test_other_companys_product_is_refused(self):
        other = make_company("B", prefix="BB", ntn="7777777")
        with self.assertRaises(InvoiceError):
            create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                           lines=[LineInput(make_product(other), "piece", "1", "", "1")])

    def test_failed_invoice_does_not_use_a_number(self):
        with self.assertRaises(InvoiceError):
            create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                           lines=[LineInput(self.product, "piece", "0", "", "1")])
        self.assertEqual(self._invoice().number, "AG-000001")


class ScreenTests(TestCase):
    def setUp(self):
        self.a = make_company("A")
        self.b = make_company("B", prefix="BB", ntn="7777777")
        self.product_a = make_product(self.a)
        self.customer_a = make_customer(self.a)
        self.product_b = make_product(self.b, "B product")
        self.customer_b = make_customer(self.b, "B buyer")
        self.admin_a = User.objects.create_user("admin_a", password="x")
        self.oper_a = User.objects.create_user("oper_a", password="x")
        self.admin_b = User.objects.create_user("admin_b", password="x")
        Membership.objects.create(user=self.admin_a, company=self.a, role="admin")
        Membership.objects.create(user=self.oper_a, company=self.a, role="operator")
        Membership.objects.create(user=self.admin_b, company=self.b, role="admin")
        self.inv_b = create_invoice(company=self.b, customer=self.customer_b, invoice_date=date(2026, 11, 2),
                                    lines=[LineInput(self.product_b, "piece", "1", "", "1")])

    def _post_invoice(self, **extra):
        data = {
            "customer": self.customer_a.pk, "invoice_date": "2026-11-02",
            "lines": json.dumps([{"product": self.product_a.pk, "sold_by": "piece", "quantity": "1", "price": "100", "discount": "0"}]),
        }
        data.update(extra)
        return self.client.post(reverse("invoice_new"), data)

    def test_login_required(self):
        for name in ["dashboard", "invoice_list", "invoice_new", "customer_list", "product_list", "user_list"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("/login/", response["Location"])

    def test_all_screens_open_for_admin(self):
        self.client.force_login(self.admin_a)
        for name in ["dashboard", "invoice_list", "invoice_new", "customer_list", "customer_new", "product_list",
                     "product_new", "company_edit", "company_new", "user_list", "user_new"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_save_then_approve_flow(self):
        self.client.force_login(self.admin_a)
        response = self._post_invoice()
        inv = Invoice.objects.get(company=self.a)
        self.assertRedirects(response, reverse("invoice_detail", args=[inv.pk]))
        self.assertEqual(inv.status, Invoice.Status.SAVED)
        self.assertContains(self.client.get(reverse("invoice_detail", args=[inv.pk])), "Approve and send to FBR")
        self.client.post(reverse("invoice_approve", args=[inv.pk]))
        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.WAITING)
        self.assertNotContains(self.client.get(reverse("invoice_detail", args=[inv.pk])), "Approve and send to FBR")

    def test_approve_needs_post(self):
        self.client.force_login(self.admin_a)
        self._post_invoice()
        inv = Invoice.objects.get(company=self.a)
        self.assertEqual(self.client.get(reverse("invoice_approve", args=[inv.pk])).status_code, 405)

    def test_edit_and_delete_screens(self):
        self.client.force_login(self.admin_a)
        self._post_invoice()
        inv = Invoice.objects.get(company=self.a)
        edit = reverse("invoice_edit", args=[inv.pk])
        self.assertContains(self.client.get(edit), "Save changes")
        lines = json.dumps([{"product": self.product_a.pk, "sold_by": "lot", "quantity": "2", "pieces_per_lot": "5", "price": "10", "discount": "0"}])
        response = self.client.post(edit, {"customer": self.customer_a.pk, "invoice_date": "2026-11-03", "lines": lines})
        self.assertRedirects(response, reverse("invoice_detail", args=[inv.pk]))
        inv.refresh_from_db()
        self.assertEqual(inv.items.get().quantity, Decimal("10"))
        # The delete link only asks first. Only the POST deletes.
        delete = reverse("invoice_delete", args=[inv.pk])
        self.assertContains(self.client.get(delete), inv.number)
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())
        self.assertRedirects(self.client.post(delete), reverse("invoice_list"))
        self.assertFalse(Invoice.objects.filter(pk=inv.pk).exists())

    def test_approved_invoice_screens_are_locked(self):
        self.client.force_login(self.admin_a)
        self._post_invoice()
        inv = Invoice.objects.get(company=self.a)
        self.client.post(reverse("invoice_approve", args=[inv.pk]))
        detail = reverse("invoice_detail", args=[inv.pk])
        self.assertNotContains(self.client.get(detail), 'id="edit"')
        self.assertRedirects(self.client.get(reverse("invoice_edit", args=[inv.pk])), detail)
        self.assertRedirects(self.client.post(reverse("invoice_delete", args=[inv.pk])), detail)
        self.assertTrue(Invoice.objects.filter(pk=inv.pk).exists())

    def test_operator_cannot_change_products_or_users(self):
        self.client.force_login(self.oper_a)
        for name in ["product_list", "product_new", "company_edit", "company_new", "user_list", "user_new"]:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_company_data_is_separate(self):
        self.client.force_login(self.admin_a)
        self.assertEqual(self.client.get(reverse("invoice_detail", args=[self.inv_b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("invoice_approve", args=[self.inv_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("invoice_edit", args=[self.inv_b.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("invoice_delete", args=[self.inv_b.pk])).status_code, 404)
        self.assertTrue(Invoice.objects.filter(pk=self.inv_b.pk).exists())
        self.assertEqual(self.client.get(reverse("product_edit", args=[self.product_b.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("customer_edit", args=[self.customer_b.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("product_list")), "B product")
        self.assertNotContains(self.client.get(reverse("customer_list")), "B buyer")
        self.assertNotContains(self.client.get(reverse("invoice_list")), self.inv_b.number)

    def test_cannot_use_another_companys_records_in_a_post(self):
        self.client.force_login(self.admin_a)
        self._post_invoice(customer=self.customer_b.pk)
        self._post_invoice(lines=json.dumps([{"product": self.product_b.pk, "quantity": "1", "price": "1"}]))
        self.assertFalse(Invoice.objects.filter(company=self.a).exists())

    def test_cannot_switch_to_a_company_you_are_not_in(self):
        self.client.force_login(self.admin_a)
        self.client.post(reverse("switch_company"), {"company": self.b.pk})
        self.assertNotContains(self.client.get(reverse("invoice_list")), self.inv_b.number)

    def test_bad_post_keeps_the_form_and_saves_nothing(self):
        self.client.force_login(self.admin_a)
        for lines in ["not json", "{}", "[]", json.dumps([{"product": "x"}]), json.dumps(["x"])]:
            response = self._post_invoice(lines=lines)
            self.assertEqual(response.status_code, 200, lines)
        response = self._post_invoice(invoice_date="bad")
        self.assertContains(response, "Enter a valid invoice date")
        self.assertFalse(Invoice.objects.filter(company=self.a).exists())

    def test_product_name_with_html_is_escaped(self):
        make_product(self.a, "</script><b>x")
        self.client.force_login(self.admin_a)
        self.assertNotContains(self.client.get(reverse("invoice_new")), "</script><b>x")

    def test_customer_rules(self):
        self.client.force_login(self.admin_a)
        base = {"name": "New", "province": "PUNJAB", "address": "A", "is_active": "on"}
        cases = [
            {**base, "kind": "registered", "ntn_cnic": ""},
            {**base, "kind": "registered", "ntn_cnic": "12345"},
            {**base, "kind": "registered", "ntn_cnic": self.a.ntn_cnic},
            {**base, "kind": "unregistered", "province": ""},
            {**base, "kind": "foreign", "country": ""},
        ]
        for data in cases:
            self.assertEqual(self.client.post(reverse("customer_new"), data).status_code, 200, data)
        self.assertFalse(Customer.objects.filter(name="New").exists())

    def test_no_external_assets_in_pages(self):
        self.client.force_login(self.admin_a)
        html = self.client.get(reverse("invoice_new")).content.decode()
        self.assertNotIn('src="http', html)
        self.assertNotIn('href="http', html)


class FirstRunTests(TestCase):
    def test_new_install_goes_to_setup_then_closes(self):
        self.assertRedirects(self.client.get("/"), reverse("first_run"))
        response = self.client.post(reverse("first_run"), {
            "business_name": "AYESHA GARMENTS", "ntn_cnic": "1234567", "province": "PUNJAB", "address": "Addr",
            "invoice_prefix": "AG", "username": "owner", "password": "Str0ng-pass-99",
        })
        self.assertRedirects(response, reverse("product_list"))
        self.assertEqual(Membership.objects.get().role, "admin")
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("first_run")), reverse("login"))
