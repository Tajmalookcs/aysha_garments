import json
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from billing.models import Invoice, InvoiceItem
from billing.services import (
    InvoiceError,
    LineInput,
    approve_invoice,
    compute_line,
    create_invoice,
    delete_invoice,
    update_invoice,
)
from core.forms import CompanyForm, ProductForm
from core.testing import DEMO_PASSWORD, register_copy, use_test_licensing
from core.models import Company, Customer, Membership, Product

User = get_user_model()


def make_company(name, prefix="AG", ntn="1234567"):
    return Company.objects.create(business_name=name, ntn=f"{ntn}-1", province="PUNJAB", address="Addr", invoice_prefix=prefix)


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
        self.admin_b = User.objects.create_user("admin_b", password="x")
        Membership.objects.create(user=self.admin_a, company=self.a, role="admin")
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
        for name in ["dashboard", "invoice_list", "invoice_new", "customer_list", "product_list"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn("/login/", response["Location"])

    def test_all_screens_open_for_admin(self):
        self.client.force_login(self.admin_a)
        for name in ["dashboard", "invoice_list", "invoice_new", "customer_list", "customer_new", "product_list",
                     "product_new", "company_edit", "fbr_setup", "registration"]:
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
            {**base, "kind": "registered", "ntn_cnic": self.a.fbr_registration},
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
        use_test_licensing(self)
        self.assertRedirects(self.client.get("/"), reverse("first_run"))
        response = self.client.post(reverse("first_run"), {
            "business_name": "AYESHA GARMENTS", "ntn": "1234567-1", "province": "PUNJAB", "address": "Addr",
            "invoice_prefix": "AG", "username": "owner", "password": "Str0ng-pass-99",
            "developer_password": DEMO_PASSWORD,
        })
        self.assertRedirects(response, reverse("product_list"))
        self.assertEqual(Membership.objects.get().role, "admin")
        self.client.logout()
        self.assertRedirects(self.client.get(reverse("first_run")), reverse("login"))


class PrintTests(TestCase):
    def setUp(self):
        self.company = make_company("AYESHA GARMENTS")
        self.company.strn = "1111111111111"
        self.company.save()
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)
        register_copy(self, self.company)

    def _invoice(self, customer=None, reference=""):
        return create_invoice(company=self.company, customer=customer or self.customer, invoice_date=date(2026, 11, 2),
                              lines=[LineInput(self.product, "lot", "2", "5", "1000", "100")], your_reference=reference)

    def _page(self, inv):
        return self.client.get(reverse("invoice_print", args=[inv.pk]))

    def test_saved_invoice_prints_as_pending_without_logo(self):
        page = self._page(self._invoice())
        self.assertContains(page, "PENDING FBR")
        self.assertContains(page, "Not issued yet")
        self.assertContains(page, "2 lots of 5 pieces")
        self.assertContains(page, "1111111111111")
        self.assertNotContains(page, "fbr-digital-invoicing.png")

    def test_sandbox_acceptance_is_never_final(self):
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="X1", fbr_environment="sandbox")
        page = self._page(inv)
        self.assertContains(page, "SANDBOX TEST")
        self.assertContains(page, "X1")
        self.assertNotContains(page, "fbr-digital-invoicing.png")

    def test_demo_invoice_is_marked_and_has_no_logo(self):
        inv = self._invoice(reference="DEMO order")
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="DEMO-IRN-1", fbr_environment="demo")
        page = self._page(inv)
        self.assertContains(page, "DEMO ONLY")
        self.assertNotContains(page, "fbr-digital-invoicing.png")

    def test_rejected_and_unknown_are_not_final(self):
        for status in ["rejected", "check", "waiting", "held"]:
            inv = self._invoice()
            Invoice.objects.filter(pk=inv.pk).update(status=status)
            self.assertNotContains(self._page(inv), "fbr-digital-invoicing.png")

    def test_accepted_without_irn_is_not_final(self):
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_environment="production")
        self.assertNotContains(self._page(inv), "fbr-digital-invoicing.png")

    def test_production_acceptance_gets_logo_irn_and_no_watermark(self):
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="REALIRN1", fbr_environment="production")
        page = self._page(inv)
        self.assertContains(page, "fbr-digital-invoicing.png")
        self.assertContains(page, "REALIRN1")
        self.assertNotContains(page, 'class="stamp"')

    def test_final_copy_has_a_25x25_qr_of_the_irn(self):
        from billing.qr import irn_matrix
        for irn in ["7000007DI1747119701593", "1234567890123DI1747119701593"]:
            matrix = irn_matrix(irn)
            self.assertEqual((len(matrix), len(matrix[0])), (25, 25))
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="7000007DI1747119701593", fbr_environment="production")
        page = self._page(inv)
        self.assertContains(page, 'viewBox="0 0 25 25"')
        self.assertNotContains(page, "could not be made")

    def test_other_copies_have_no_qr(self):
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="7000007DI1747119701593", fbr_environment="sandbox")
        self.assertNotContains(self._page(inv), "<svg")

    def test_irn_too_long_for_the_qr_warns_instead_of_printing_a_bad_code(self):
        from billing.qr import irn_svg
        self.assertIsNone(irn_svg("X" * 40))
        inv = self._invoice()
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="X" * 40, fbr_environment="production")
        page = self._page(inv)
        self.assertContains(page, "could not be made")
        self.assertNotContains(page, "<svg")

    def test_further_tax_column_only_when_needed(self):
        registered = self._page(self._invoice())
        self.assertNotContains(registered, '<th class="n">Further tax</th>')
        walkin = make_customer(self.company, "Walk-in", Customer.Kind.UNREGISTERED)
        self.assertContains(self._page(self._invoice(customer=walkin)), '<th class="n">Further tax</th>')

    def test_other_company_cannot_print(self):
        other = User.objects.create_user("other", password="x")
        Membership.objects.create(user=other, company=make_company("B", prefix="BB", ntn="7777777"), role="admin")
        inv = self._invoice()
        self.client.force_login(other)
        self.assertEqual(self._page(inv).status_code, 404)

    def test_no_external_files(self):
        html = self._page(self._invoice()).content.decode()
        self.assertNotIn('src="http', html)
        self.assertNotIn('href="http', html)

    def test_amount_in_words(self):
        from billing.words import amount_in_words as w
        cases = {
            "0": "Rupees Zero Only",
            "5": "Rupees Five Only",
            "19": "Rupees Nineteen Only",
            "100": "Rupees One Hundred Only",
            "1098": "Rupees One Thousand Ninety Eight Only",
            "520380": "Rupees Five Lakh Twenty Thousand Three Hundred Eighty Only",
            "10000000": "Rupees One Crore Only",
            "123456789": "Rupees Twelve Crore Thirty Four Lakh Fifty Six Thousand Seven Hundred Eighty Nine Only",
            "1098.50": "Rupees One Thousand Ninety Eight and Fifty Paisa Only",
            "0.05": "Rupees Zero and Five Paisa Only",
        }
        for value, text in cases.items():
            self.assertEqual(w(value), text)


class SalesRegisterTests(TestCase):
    def setUp(self):
        self.company = make_company("A")
        self.product = make_product(self.company, price="1000")
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)

    def _invoice(self, day, company=None, customer=None, product=None):
        return create_invoice(company=company or self.company, customer=customer or self.customer, invoice_date=date(2026, 10, day),
                              lines=[LineInput(product or self.product, "piece", "1", "", "1000", "100")])

    def test_period_filter_and_totals(self):
        self._invoice(1)
        self._invoice(15)
        self._invoice(31)
        page = self.client.get(reverse("sales_register"), {"from": "2026-10-01", "to": "2026-10-15"})
        self.assertEqual(page.context["t"]["count"], 2)
        self.assertEqual(page.context["t"]["grand_total"], Decimal("2124.00"))
        self.assertEqual(page.context["t"]["after_discount"], Decimal("1800.00"))
        self.assertEqual(page.context["unaccepted"], 2)
        self.assertContains(page, "AG-000001")
        self.assertNotContains(page, "AG-000003")

    def test_status_filter(self):
        self._invoice(1)
        approve_invoice(self._invoice(2), None)
        page = self.client.get(reverse("sales_register"), {"from": "2026-10-01", "to": "2026-10-31", "status": "waiting"})
        self.assertEqual(page.context["t"]["count"], 1)

    def test_production_invoices_get_no_warning(self):
        inv = self._invoice(1)
        Invoice.objects.filter(pk=inv.pk).update(status="accepted", fbr_invoice_number="R1", fbr_environment="production")
        page = self.client.get(reverse("sales_register"), {"from": "2026-10-01", "to": "2026-10-31"})
        self.assertEqual(page.context["unaccepted"], 0)
        self.assertNotContains(page, "production system hasn't accepted")

    def test_bad_dates_fall_back_with_a_message(self):
        for params in [{"from": "bad"}, {"from": "2026-10-31", "to": "2026-10-01"}]:
            self.assertEqual(self.client.get(reverse("sales_register"), params).status_code, 200)
            self.assertContains(self.client.get(reverse("sales_register"), params), "this month instead")

    def test_only_this_companys_invoices(self):
        other = make_company("B", prefix="BB", ntn="7777777")
        self._invoice(1, company=other, customer=make_customer(other), product=make_product(other))
        page = self.client.get(reverse("sales_register"), {"from": "2026-10-01", "to": "2026-10-31"})
        self.assertEqual(page.context["t"]["count"], 0)
        export = self.client.get(reverse("sales_register_csv"), {"from": "2026-10-01", "to": "2026-10-31"})
        self.assertNotIn("BB-000001", export.content.decode())

    def test_export(self):
        self._invoice(1)
        response = self.client.get(reverse("sales_register_csv"), {"from": "2026-10-01", "to": "2026-10-31"})
        self.assertIn("attachment", response["Content-Disposition"])
        text = response.content.decode("utf-8-sig")
        self.assertIn("Document,Invoice no.,Date,Buyer", text)
        self.assertIn("Sale Invoice,AG-000001,2026-10-01,Buyer,Registered,7654321,PUNJAB,1000.00,100.00,900.00,162.00,0.00,0.00,1062.00", text)
        self.assertIn("Total,,,1 invoices,,,,1000.00,100.00,900.00,162.00,0.00,0.00,1062.00", text)

    def test_export_blocks_spreadsheet_formulas(self):
        bad = make_customer(self.company, "=HYPERLINK(1)", Customer.Kind.UNREGISTERED)
        self._invoice(1, customer=bad)
        text = self.client.get(reverse("sales_register_csv"), {"from": "2026-10-01", "to": "2026-10-31"}).content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK(1)", text)

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("sales_register")).status_code, 302)
        self.assertEqual(self.client.get(reverse("sales_register_csv")).status_code, 302)


class DebitNoteTests(TestCase):
    def setUp(self):
        self.company = make_company("A")
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.original = create_invoice(company=self.company, customer=self.customer, invoice_date=self.today,
                                       lines=[LineInput(self.product, "piece", "10", "", "1000")])
        Invoice.objects.filter(pk=self.original.pk).update(status="accepted", fbr_invoice_number="7000007DI1", fbr_environment="sandbox")
        self.original.refresh_from_db()

    def _note(self, qty="1", day=None, customer=None):
        return create_invoice(company=self.company, customer=customer or self.customer, invoice_date=day or self.today,
                              lines=[LineInput(self.product, "piece", qty, "", "1000")], original=self.original)

    def test_note_links_to_the_original_irn(self):
        note = self._note()
        self.assertTrue(note.is_debit_note)
        self.assertEqual(note.invoice_ref_no, "7000007DI1")
        from fbr.payload import build_payload
        data = build_payload(note, "SN001")
        self.assertEqual((data["invoiceType"], data["invoiceRefNo"]), ("Debit Note", "7000007DI1"))

    def test_fbr_rules_are_enforced(self):
        from datetime import timedelta
        other = make_customer(self.company, "Other")
        for kwargs in [{"day": self.today - timedelta(days=1)}, {"day": self.today + timedelta(days=181)}, {"customer": other}, {"qty": "11"}]:
            with self.assertRaises(InvoiceError, msg=kwargs):
                self._note(**kwargs)
        self.assertEqual(self.company.invoices.count(), 1)

    def test_only_accepted_recent_sale_invoices(self):
        from datetime import timedelta
        self.assertTrue(self.original.can_add_debit_note)
        self.assertFalse(self._note().can_add_debit_note)
        Invoice.objects.filter(pk=self.original.pk).update(invoice_date=self.today - timedelta(days=181))
        self.original.refresh_from_db()
        self.assertFalse(self.original.can_add_debit_note)
        Invoice.objects.filter(pk=self.original.pk).update(invoice_date=self.today, fbr_environment="demo")
        self.original.refresh_from_db()
        self.assertFalse(self.original.can_add_debit_note)

    def test_screens(self):
        detail = reverse("invoice_detail", args=[self.original.pk])
        self.assertContains(self.client.get(detail), "Make debit note")
        url = reverse("debit_note_new", args=[self.original.pk])
        self.assertContains(self.client.get(url), "Save debit note")
        lines = json.dumps([{"product": self.product.pk, "sold_by": "piece", "quantity": "1", "price": "1000", "discount": "0"}])
        response = self.client.post(url, {"customer": self.customer.pk, "invoice_date": self.today.isoformat(), "lines": lines}, follow=True)
        note = Invoice.objects.get(invoice_type="Debit Note")
        self.assertContains(response, "Debit note")
        self.assertContains(self.client.get(reverse("invoice_print", args=[note.pk])), "Debit Note")
        self.assertContains(self.client.get(reverse("invoice_edit", args=[note.pk])), "Edit debit note")
        self.assertEqual(self.client.post(reverse("invoice_delete", args=[self.original.pk])).status_code, 302)
        self.assertTrue(Invoice.objects.filter(pk=self.original.pk).exists())

    def test_other_buyer_cannot_be_posted(self):
        other = make_customer(self.company, "Other")
        lines = json.dumps([{"product": self.product.pk, "sold_by": "piece", "quantity": "1", "price": "1000", "discount": "0"}])
        self.client.post(reverse("debit_note_new", args=[self.original.pk]), {"customer": other.pk, "invoice_date": self.today.isoformat(), "lines": lines})
        self.assertFalse(Invoice.objects.filter(invoice_type="Debit Note").exists())


class CompanyNtnTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(business_name="A", ntn="1234567-8", cnic="1111122222333", province="PUNJAB", address="Addr", invoice_prefix="AG")
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)

    def _invoice(self):
        return create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                              lines=[LineInput(self.product, "piece", "1", "", "1")])

    def test_invoice_shows_ntn_and_never_cnic(self):
        inv = self._invoice()
        for name in ["invoice_print", "invoice_detail"]:
            page = self.client.get(reverse(name, args=[inv.pk]))
            self.assertContains(page, "1234567-8")
            self.assertNotContains(page, "1111122222333")

    def test_fbr_receives_the_seven_digit_ntn(self):
        from fbr.payload import build_payload
        self.assertEqual(build_payload(self._invoice(), "SN001")["sellerNTNCNIC"], "1234567")

    def test_ntn_required_in_right_format_and_cnic_optional(self):
        base = {"business_name": "B", "province": "PUNJAB", "address": "A", "invoice_prefix": "BB"}
        from core.forms import CompanyForm
        for ntn in ["", "1234567", "1234567-", "123456-8", "1234567-89", "3310200000001"]:
            self.assertIn("ntn", CompanyForm({**base, "ntn": ntn}).errors, ntn)
        self.assertTrue(CompanyForm({**base, "ntn": "1234567-8"}).is_valid())
        self.assertIn("cnic", CompanyForm({**base, "ntn": "1234567-8", "cnic": "123"}).errors)
        self.assertTrue(CompanyForm({**base, "ntn": "1234567-8", "cnic": "1111122222333"}).is_valid())

    def test_no_invoice_without_ntn(self):
        Company.objects.filter(pk=self.company.pk).update(ntn="")
        self.company.refresh_from_db()
        with self.assertRaisesMessage(InvoiceError, "NTN"):
            self._invoice()

    def test_buyer_cannot_use_the_companys_ntn_or_cnic(self):
        from core.forms import CustomerForm
        base = {"name": "X", "kind": "registered", "province": "PUNJAB", "address": "A", "is_active": "on"}
        for value in ["1234567", "1111122222333"]:
            form = CustomerForm({**base, "ntn_cnic": value}, instance=Customer(company=self.company), company=self.company)
            self.assertIn("ntn_cnic", form.errors, value)


class OfflineAndPrintRuleTests(TestCase):
    def setUp(self):
        self.company = make_company("A")
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)

    def _lines(self):
        return json.dumps([{"product": self.product.pk, "sold_by": "piece", "quantity": "1", "price": "100", "discount": "0"}])

    def _post(self, offline="0"):
        return self.client.post(reverse("invoice_new"), {"customer": self.customer.pk, "invoice_date": "2026-11-03", "lines": self._lines(), "issued_offline": offline})

    def test_saved_while_offline_is_marked_everywhere(self):
        self._post("1")
        inv = Invoice.objects.get()
        self.assertTrue(inv.issued_offline)
        self.assertContains(self.client.get(reverse("invoice_print", args=[inv.pk])), "Issued in offline mode")
        self.assertContains(self.client.get(reverse("invoice_detail", args=[inv.pk])), "Issued in offline mode")
        self.assertContains(self.client.get(reverse("dashboard")), "1 offline invoice")

    def test_online_invoice_has_no_offline_mark(self):
        self._post("0")
        inv = Invoice.objects.get()
        self.assertFalse(inv.issued_offline)
        self.assertNotContains(self.client.get(reverse("invoice_print", args=[inv.pk])), "Issued in offline mode")
        self.assertNotContains(self.client.get(reverse("dashboard")), "offline invoice")

    def test_edit_keeps_the_offline_mark(self):
        self._post("1")
        inv = Invoice.objects.get()
        self.client.post(reverse("invoice_edit", args=[inv.pk]), {"customer": self.customer.pk, "invoice_date": "2026-11-03", "lines": self._lines(), "issued_offline": "0"})
        inv.refresh_from_db()
        self.assertTrue(inv.issued_offline)

    def test_print_shows_tax_period_unit_and_sro(self):
        Product.objects.filter(pk=self.product.pk).update(sro_schedule_no="SRO 297", sro_item_serial_no="12")
        self._post()
        page = self.client.get(reverse("invoice_print", args=[Invoice.objects.get().pk]))
        self.assertContains(page, "November 2026")
        self.assertContains(page, "Unit: Numbers, pieces, units")
        self.assertContains(page, "SRO SRO 297, serial 12")

    def test_print_leaves_out_sro_when_not_used(self):
        self._post()
        self.assertNotContains(self.client.get(reverse("invoice_print", args=[Invoice.objects.get().pk])), "serial")


class SellingByKgTests(TestCase):
    """Made-up figures. KG is the default way of selling; piece and lot stay available."""

    def setUp(self):
        self.company = make_company("Kg Co")
        self.kg_product = Product.objects.create(
            company=self.company, name="Processing", hs_code="0000.0000", uom="KG", sale_type="Sample",
            rate_label="18%", rate_percent=Decimal("18"), price_per_piece=Decimal("60"),
        )
        self.piece_product = make_product(self.company)
        self.customer = make_customer(self.company)
        self.user = User.objects.create_user("kg", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)

    def _invoice(self, quantity="100", price="60"):
        return create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                              lines=[LineInput(self.kg_product, "kg", quantity, "", price)])

    def test_kg_line_works_out_value_and_tax(self):
        r = compute_line(LineInput(self.kg_product, "kg", "100.5", "", "60"), Customer.Kind.REGISTERED)
        self.assertEqual(r["quantity"], Decimal("100.5"))
        self.assertEqual(r["value_excl_tax"], Decimal("6030.00"))
        self.assertEqual(r["sales_tax"], Decimal("1085.40"))
        self.assertEqual(r["total"], Decimal("7115.40"))
        self.assertIsNone(r["pieces_per_lot"])

    def test_both_spellings_of_the_unit_count_as_kg(self):
        for unit in ["KG", "kg", "Kilogram", " KILOGRAM "]:
            self.kg_product.uom = unit
            self.assertTrue(self.kg_product.is_kg, unit)
        self.kg_product.uom = "Numbers, pieces, units"
        self.assertFalse(self.kg_product.is_kg)

    def test_selling_method_must_fit_the_product_unit(self):
        for bad in [
            LineInput(self.piece_product, "kg", "1", "", "10"),
            LineInput(self.kg_product, "piece", "1", "", "10"),
            LineInput(self.kg_product, "lot", "1", "5", "10"),
            LineInput(self.kg_product, "gram", "1", "", "10"),
        ]:
            with self.assertRaises(InvoiceError):
                compute_line(bad, Customer.Kind.REGISTERED)

    def test_piece_and_lot_still_work(self):
        r = compute_line(LineInput(self.piece_product, "lot", "2", "5", "100"), Customer.Kind.REGISTERED)
        self.assertEqual(r["quantity"], Decimal("10"))
        r = compute_line(LineInput(self.piece_product, "piece", "3", "", "100"), Customer.Kind.REGISTERED)
        self.assertEqual(r["quantity"], Decimal("3"))

    def test_form_without_a_selling_method_follows_the_product(self):
        for product, expected in [(self.kg_product, "kg"), (self.piece_product, "piece")]:
            lines = json.dumps([{"product": product.pk, "quantity": "2", "price": "10", "discount": "0"}])
            response = self.client.post("/invoices/new/", {
                "customer": self.customer.pk, "invoice_date": "2026-11-02", "lines": lines,
            })
            self.assertEqual(response.status_code, 302)
            self.assertEqual(InvoiceItem.objects.latest("pk").sold_by, expected)

    def test_new_invoice_form_tells_the_page_which_products_are_kg(self):
        response = self.client.get("/invoices/new/")
        flags = {p["name"]: p["kg"] for p in response.context["products_data"]}
        self.assertEqual(flags, {"Processing": True, "Quilt": False})

    def test_screens_and_print_show_kg(self):
        invoice = self._invoice()
        for url in [f"/invoices/{invoice.pk}/", f"/invoices/{invoice.pk}/print/"]:
            html = self.client.get(url).content.decode()
            self.assertIn("100 KG", html, url)
            self.assertNotIn(">Pieces<", html, url)

    def test_fbr_receives_the_kg_quantity_and_unit(self):
        from fbr.payload import build_payload

        item = build_payload(self._invoice())["items"][0]
        self.assertEqual(item["uoM"], "KG")
        self.assertEqual(item["quantity"], 100.0)
        self.assertEqual(item["valueSalesExcludingST"], 6000.0)
        self.assertEqual(item["salesTaxApplicable"], 1080.0)

    def test_new_product_form_starts_on_kg(self):
        self.assertEqual(ProductForm(company=self.company)["uom"].value(), "KG")
        self.assertEqual(ProductForm(company=self.company, instance=self.piece_product)["uom"].value(), "Numbers, pieces, units")
        self.assertIn('value="KG"', self.client.get("/products/new/").content.decode())

    def test_processing_invoice_suggests_its_sandbox_scenario(self):
        self.company.sandbox_scenarios = "SN001, SN016"
        self.company.save()
        for name in ["Processing/Conversion of Goods", "Processing/ Conversion of Goods"]:
            self.kg_product.sale_type = name
            self.kg_product.save()
            response = self.client.get(f"/invoices/{self._invoice().pk}/")
            self.assertEqual(response.context["suggested"], "SN016", name)

    def test_other_invoices_keep_their_suggested_scenario(self):
        response = self.client.get(f"/invoices/{self._invoice().pk}/")
        self.assertEqual(response.context["suggested"], "SN001")


class PackAndKgTests(TestCase):
    """Made-up figures. The charge is by the pack, and FBR is told the weight."""

    def setUp(self):
        self.company = make_company("Pack Co")
        self.duvet = self._product("Duvet", "SET PACK")
        self.fitted = self._product("Fitted", "PAIR PACK")
        self.customer = make_customer(self.company)
        self.customer.strn = "11-22-3333-444-55"
        self.customer.save()
        self.user = User.objects.create_user("pack", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.client.force_login(self.user)

    def _product(self, name, pack_unit, hs="0000.0000", rate="18"):
        return Product.objects.create(
            company=self.company, name=name, hs_code=hs, uom="KG", pack_unit=pack_unit, sale_type="Sample",
            rate_label=f"{rate}%", rate_percent=Decimal(rate), price_per_piece=Decimal("85"),
        )

    def _line(self, product, packs, rate, kg, unit="SET PACK"):
        return LineInput(product, "pack", packs, "", rate, "0", kg=kg, pack_unit=unit)

    def _invoice(self, *lines, reference="JOB-1"):
        return create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                              lines=list(lines), your_reference=reference)

    def test_value_comes_from_packs_and_quantity_from_kg(self):
        r = compute_line(self._line(self.duvet, "100", "85", "300.5"), Customer.Kind.REGISTERED)
        self.assertEqual(r["entered_quantity"], Decimal("100"))
        self.assertEqual(r["quantity"], Decimal("300.5"))
        self.assertEqual(r["value_excl_tax"], Decimal("8500.00"))
        self.assertEqual(r["sales_tax"], Decimal("1530.00"))
        self.assertEqual(r["pack_unit"], "SET PACK")

    def test_bad_pack_lines_are_refused(self):
        piece_product = make_product(self.company)
        for bad in [
            self._line(self.duvet, "100", "85", ""),
            self._line(self.duvet, "100", "85", "0"),
            self._line(self.duvet, "100", "85", "1.12345"),
            self._line(self.duvet, "100", "85", "1", unit="BOX"),
            self._line(self.duvet, "100", "85", "1", unit=""),
            self._line(piece_product, "100", "85", "1"),
        ]:
            with self.assertRaises(InvoiceError):
                compute_line(bad, Customer.Kind.REGISTERED)

    def test_matching_lines_go_to_fbr_as_one_item(self):
        from fbr.payload import build_payload

        invoice = self._invoice(self._line(self.duvet, "100", "85", "300"),
                                self._line(self.fitted, "200", "95", "700", unit="PAIR PACK"))
        self.assertEqual(invoice.items.count(), 2)
        self.assertEqual(invoice.total_kg, Decimal("1000"))
        data = build_payload(invoice, "SN016")
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["uoM"], "KG")
        self.assertEqual(item["quantity"], 1000.0)
        self.assertEqual(item["valueSalesExcludingST"], 27500.0)
        self.assertEqual(item["salesTaxApplicable"], 4950.0)
        self.assertEqual(item["totalValues"], 32450.0)
        self.assertEqual(item["productDescription"], "Duvet, Fitted")
        self.assertEqual(data["items"][0]["discount"], 0.0)

    def test_same_description_appears_once(self):
        from fbr.payload import build_payload

        invoice = self._invoice(self._line(self.duvet, "1", "75", "1"), self._line(self.duvet, "1", "85", "1"))
        self.assertEqual(build_payload(invoice)["items"][0]["productDescription"], "Duvet")

    def test_different_lines_go_as_separate_items(self):
        from fbr.payload import build_payload

        other_hs = self._product("Other code", "SET PACK", hs="1111.1111")
        other_rate = self._product("Other rate", "SET PACK", rate="5")
        invoice = self._invoice(self._line(self.duvet, "100", "85", "300"), self._line(other_hs, "10", "10", "50"),
                                self._line(self.fitted, "200", "95", "700"), self._line(other_rate, "10", "10", "5"))
        items = build_payload(invoice)["items"]
        self.assertEqual([i["hsCode"] for i in items], ["0000.0000", "1111.1111", "0000.0000"])
        self.assertEqual([i["quantity"] for i in items], [1000.0, 50.0, 5.0])
        self.assertEqual([i["rate"] for i in items], ["18%", "18%", "5%"])

    def test_other_ways_of_selling_are_not_combined(self):
        from fbr.payload import build_payload

        piece = make_product(self.company)
        invoice = self._invoice(LineInput(piece, "piece", "1", "", "10"), LineInput(piece, "piece", "2", "", "10"))
        self.assertEqual(len(build_payload(invoice)["items"]), 2)

    def test_job_number_and_buyer_strn_print_but_stay_out_of_the_fbr_data(self):
        from fbr.payload import build_payload

        invoice = self._invoice(self._line(self.duvet, "100", "85", "300"), reference="JOB-777")
        html = self.client.get(f"/invoices/{invoice.pk}/print/").content.decode()
        for text in ["Job no.", "JOB-777", "11-22-3333-444-55", "100 SET PACK", "Total weight", "300 KG"]:
            self.assertIn(text, html)
        sent = json.dumps(build_payload(invoice))
        self.assertNotIn("JOB-777", sent)
        self.assertNotIn("11-22-3333-444-55", sent)

    def test_form_saves_and_reopens_a_pack_line(self):
        lines = json.dumps([{"product": self.duvet.pk, "quantity": "100", "price": "85", "discount": "0", "kg": "300", "pack_unit": "SET PACK"}])
        response = self.client.post("/invoices/new/", {"customer": self.customer.pk, "invoice_date": "2026-11-02", "lines": lines})
        self.assertEqual(response.status_code, 302)
        item = InvoiceItem.objects.get()
        self.assertEqual((item.sold_by, item.quantity), ("pack", Decimal("300")))
        reopened = self.client.get(f"/invoices/{item.invoice_id}/edit/").context["initial_lines"][0]
        self.assertEqual((reopened["quantity"], reopened["kg"], reopened["pack_unit"]), ("100", "300", "SET PACK"))

    def test_pack_unit_needs_a_kg_product(self):
        data = {"name": "X", "hs_code": "0000.0000", "uom": "Dozen", "pack_unit": "SET PACK", "sale_type": "S", "rate_label": "18%",
                "rate_percent": "18", "further_tax_percent": "0", "fed_percent": "0", "fixed_notified_value": "0", "price_per_piece": "1"}
        form = ProductForm(data, company=self.company)
        self.assertIn("pack_unit", form.errors)
        self.assertTrue(ProductForm({**data, "uom": "KG"}, company=self.company).is_valid())


class StartingInvoiceNumberTests(TestCase):
    def setUp(self):
        self.company = make_company("Num Co")
        self.product = make_product(self.company)
        self.customer = make_customer(self.company)

    def _invoice(self):
        return create_invoice(company=self.company, customer=self.customer, invoice_date=date(2026, 11, 2),
                              lines=[LineInput(self.product, "piece", "1", "", "1")])

    def test_blank_prefix_continues_after_the_last_number(self):
        self.company.invoice_prefix = ""
        self.company.last_invoice_number = 118
        self.company.save()
        first, second = self._invoice(), self._invoice()
        self.assertEqual((first.number, second.number), ("119", "120"))

    def test_deleted_number_is_used_again(self):
        self.company.invoice_prefix = ""
        self.company.last_invoice_number = 118
        self.company.save()
        first = self._invoice()
        self._invoice()
        delete_invoice(first)
        self.assertEqual(self._invoice().number, "119")

    def test_prefix_keeps_its_format(self):
        self.company.last_invoice_number = 41
        self.company.save()
        self.assertEqual(self._invoice().number, "AG-000042")

    def test_no_last_number_starts_at_one(self):
        self.assertEqual(self._invoice().number, "AG-000001")

    def test_company_form_takes_a_blank_prefix(self):
        base = {"business_name": "B", "ntn": "1234567-1", "province": "PUNJAB", "address": "A"}
        form = CompanyForm({**base, "invoice_prefix": ""}, instance=self.company)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().invoice_prefix, "")
