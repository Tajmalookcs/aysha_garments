import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice
from billing.services import LineInput, approve_invoice, create_invoice
from core.models import Company, Customer, Membership, Product
from fbr.constants import POST_SANDBOX, VALIDATE_SANDBOX
from fbr.models import FbrApiLog, FbrCredential, RefList
from fbr.parsing import INVALID, UNCLEAR, VALID, parse
from fbr.payload import build_payload
from fbr.sending import mark_not_found_in_iris, record_found_in_iris, send_invoice

TOKEN = "secret-test-token-12345"

# The spec's own samples, sections 4.1.3 to 4.1.5 and 4.2.4.
VALID_POST = {"invoiceNumber": "7000007DI1747119701593", "dated": "2025-05-13 12:01:41", "validationResponse": {
    "statusCode": "00", "status": "Valid", "error": "", "invoiceStatuses": [
        {"itemSNo": "1", "statusCode": "00", "status": "Valid", "invoiceNo": "7000007DI1747119701593-1", "errorCode": "", "error": ""}]}}
INVALID_WHOLE = {"dated": "2025-05-13 13:09:05", "validationResponse": {
    "statusCode": "01", "status": "Invalid", "errorCode": "0052", "error": "Provide proper HS Code with invoice no. null", "invoiceStatuses": None}}
INVALID_ITEM = {"dated": "2025-05-13 13:10:00", "validationResponse": {
    "statusCode": "00", "status": "invalid", "error": "", "invoiceStatuses": [
        {"itemSNo": "1", "statusCode": "01", "status": "Invalid", "invoiceNo": None, "errorCode": "0046", "error": "Provide rate."}]}}
VALID_CHECK = {"dated": "2025-05-13 13:13:54", "validationResponse": {
    "statusCode": "00", "status": "Valid", "error": "", "invoiceStatuses": [
        {"itemSNo": "1", "statusCode": "00", "status": "Valid", "errorCode": None, "error": ""}]}}


def reply(data=None, status=200, text=None):
    r = MagicMock(status_code=status)
    r.text = text if text is not None else json.dumps(data)
    if data is None:
        r.json.side_effect = ValueError
    else:
        r.json.return_value = data
    return r


class ParsingTests(TestCase):
    def test_spec_valid_post(self):
        p = parse(VALID_POST, needs_irn=True)
        self.assertEqual((p.outcome, p.irn), (VALID, "7000007DI1747119701593"))
        self.assertEqual(p.item_numbers["1"], "7000007DI1747119701593-1")

    def test_spec_whole_rejection(self):
        p = parse(INVALID_WHOLE, needs_irn=True)
        self.assertEqual((p.outcome, p.error_code), (INVALID, "0052"))
        self.assertIn("HS code", p.message)

    def test_spec_trap_outer_00_with_failed_item_is_not_accepted(self):
        p = parse(INVALID_ITEM, needs_irn=True)
        self.assertEqual((p.outcome, p.error_code), (INVALID, "0046"))

    def test_validate_reply_needs_no_irn(self):
        self.assertEqual(parse(VALID_CHECK, needs_irn=False).outcome, VALID)
        self.assertEqual(parse(VALID_CHECK, needs_irn=True).outcome, UNCLEAR)

    def test_irn_with_failed_item_is_unclear(self):
        data = dict(INVALID_ITEM, invoiceNumber="X")
        self.assertEqual(parse(data, needs_irn=True).outcome, UNCLEAR)

    def test_strange_replies_are_unclear_never_valid(self):
        for data in [None, [], {}, "x", {"validationResponse": None}, {"validationResponse": {}},
                     {"invoiceNumber": "X", "validationResponse": {"statusCode": "00", "status": "Valid"}},
                     {"invoiceNumber": "X", "validationResponse": {"statusCode": "00", "status": "Valid", "invoiceStatuses": []}},
                     {"invoiceNumber": "X", "validationResponse": {"statusCode": "00", "status": "Valid", "invoiceStatuses": ["bad"]}}]:
            self.assertEqual(parse(data, needs_irn=True).outcome, UNCLEAR, data)

    def test_status_case_is_ignored(self):
        data = json.loads(json.dumps(VALID_POST))
        data["validationResponse"]["status"] = "VALID"
        self.assertEqual(parse(data, needs_irn=True).outcome, VALID)


class Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(business_name="SELLER", ntn="1234567-1", province="PUNJAB", address="Addr", invoice_prefix="AG", sandbox_scenarios="SN001, SN002")
        self.user = get_user_model().objects.create_user("owner", password="x")
        Membership.objects.create(user=self.user, company=self.company, role="admin")
        self.product = Product.objects.create(company=self.company, name="Quilt", hs_code="9404.9000", uom="Numbers, pieces, units", sale_type="Goods at standard rate (default)", rate_label="18%", rate_percent=Decimal("18"), further_tax_percent=Decimal("4"), price_per_piece=Decimal("1000"))
        self.reg = Customer.objects.create(company=self.company, name="Reg Buyer", kind="registered", ntn_cnic="7654321", province="SINDH", address="Karachi")
        self.unreg = Customer.objects.create(company=self.company, name="Unreg Buyer", kind="unregistered", province="PUNJAB", address="FSD")
        cred = FbrCredential(company=self.company, environment="sandbox")
        cred.token = TOKEN
        cred.save()
        self.client.force_login(self.user)

    def invoice(self, customer=None, discount="0"):
        inv = create_invoice(company=self.company, customer=customer or self.reg, invoice_date=date(2026, 11, 2),
                             lines=[LineInput(self.product, "piece", "1", "", "1000", discount)], user=self.user)
        return inv

    def approved(self, **kw):
        return approve_invoice(self.invoice(**kw), self.user, "SN001")


class PayloadTests(Base):
    def test_matches_spec_fields(self):
        data = build_payload(self.invoice(customer=self.unreg, discount="100"), "SN002")
        self.assertEqual(data["invoiceDate"], "2026-11-02")
        self.assertEqual(data["sellerNTNCNIC"], "1234567")
        self.assertEqual(data["buyerRegistrationType"], "Unregistered")
        self.assertEqual(data["scenarioId"], "SN002")
        item = data["items"][0]
        self.assertEqual(item["hsCode"], "9404.9000")
        self.assertEqual(item["rate"], "18%")
        self.assertEqual(item["valueSalesExcludingST"], 900.0)
        self.assertEqual(item["salesTaxApplicable"], 162.0)
        self.assertEqual(item["furtherTax"], 36.0)
        self.assertEqual(item["discount"], 100.0)
        self.assertEqual(item["totalValues"], 1098.0)
        self.assertEqual(item["salesTaxWithheldAtSource"], 0.0)
        json.dumps(data)

    def test_money_survives_as_exact_number(self):
        self.assertEqual(json.loads(json.dumps(float(Decimal("12345678.90")))), 12345678.9)


@patch("fbr.client.requests.request")
class SendingTests(Base):
    def test_accepted_flow_validates_then_posts(self, req):
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        inv = self.approved()
        result = send_invoice(inv)
        self.assertTrue(result.ok)
        urls = [c.args[1] for c in req.call_args_list]
        self.assertTrue(urls[0].endswith(VALIDATE_SANDBOX))
        self.assertTrue(urls[1].endswith(POST_SANDBOX))
        self.assertEqual(req.call_args.kwargs["headers"]["Authorization"], f"Bearer {TOKEN}")
        inv.refresh_from_db()
        self.assertEqual(inv.status, "accepted")
        self.assertEqual(inv.fbr_invoice_number, "7000007DI1747119701593")
        self.assertEqual(inv.items.get().fbr_invoice_no, "7000007DI1747119701593-1")
        self.assertEqual(inv.status_label, "Accepted in FBR sandbox (test)")
        self.assertFalse(inv.is_final)

    def test_validation_failure_never_posts_and_can_be_fixed(self, req):
        req.side_effect = [reply(INVALID_ITEM)]
        inv = self.approved()
        self.assertFalse(send_invoice(inv).ok)
        self.assertEqual(req.call_count, 1)
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.last_error_code), ("rejected", "0046"))
        self.assertTrue(inv.can_edit)
        self.assertTrue(inv.can_approve)

    def test_validate_network_failure_stays_waiting(self, req):
        for error in [requests.exceptions.ConnectTimeout(), requests.exceptions.ReadTimeout(), requests.exceptions.ConnectionError("x")]:
            req.side_effect = [error]
            inv = self.approved()
            self.assertFalse(send_invoice(inv).ok)
            inv.refresh_from_db()
            self.assertEqual(inv.status, "waiting", error)

    def test_token_refused_stays_waiting(self, req):
        req.side_effect = [reply(status=401, text="Unauthorized")]
        inv = self.approved()
        self.assertIn("token", send_invoice(inv).message)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "waiting")

    def test_post_timeout_needs_a_person_and_never_reposts(self, req):
        req.side_effect = [reply(VALID_CHECK), requests.exceptions.ReadTimeout()]
        inv = self.approved()
        send_invoice(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "check")
        self.assertEqual(req.call_count, 2)
        self.assertFalse(send_invoice(inv).ok)
        self.assertEqual(req.call_count, 2)

    def test_post_failures_that_may_have_landed_need_a_check(self, req):
        for bad in [reply(status=500, text="error"), reply(text="not json"), reply({"odd": 1})]:
            req.side_effect = [reply(VALID_CHECK), bad]
            inv = self.approved()
            send_invoice(inv)
            inv.refresh_from_db()
            self.assertEqual(inv.status, "check")

    def test_post_connect_failure_is_safe_to_retry(self, req):
        req.side_effect = [reply(VALID_CHECK), requests.exceptions.ConnectTimeout()]
        inv = self.approved()
        send_invoice(inv)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "waiting")

    def test_post_rejection(self, req):
        req.side_effect = [reply(VALID_CHECK), reply(INVALID_WHOLE)]
        inv = self.approved()
        send_invoice(inv)
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.last_error_code), ("rejected", "0052"))

    def test_second_send_cannot_post_twice(self, req):
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        inv = self.approved()
        send_invoice(inv)
        self.assertFalse(send_invoice(inv).ok)
        self.assertEqual(req.call_count, 2)

    def test_check_resolutions(self, req):
        req.side_effect = [reply(VALID_CHECK), requests.exceptions.ReadTimeout()]
        inv = self.approved()
        send_invoice(inv)
        inv.refresh_from_db()
        self.assertFalse(record_found_in_iris(inv, "bad value!").ok)
        self.assertTrue(record_found_in_iris(inv, "7000007DI1747119701593").ok)
        inv.refresh_from_db()
        self.assertEqual(inv.status, "accepted")
        other = self.approved()
        req.side_effect = [reply(VALID_CHECK), requests.exceptions.ReadTimeout()]
        send_invoice(other)
        other.refresh_from_db()
        self.assertTrue(mark_not_found_in_iris(other).ok)
        other.refresh_from_db()
        self.assertEqual(other.status, "waiting")

    def test_blocked_without_any_call(self, req):
        demo = Product.objects.create(company=self.company, name="Demo", hs_code="0000.0000", uom="u", sale_type="s", rate_label="18%", rate_percent=Decimal("18"), price_per_piece=Decimal("1"))
        inv = create_invoice(company=self.company, customer=self.reg, invoice_date=date(2026, 11, 2), lines=[LineInput(demo, "piece", "1", "", "1")])
        inv = approve_invoice(inv, self.user, "SN001")
        self.assertIn("sample", send_invoice(inv).message)
        no_scenario = approve_invoice(self.invoice(), self.user, "")
        self.assertIn("scenario", send_invoice(no_scenario).message)
        FbrCredential.objects.all().delete()
        no_token = self.approved()
        self.assertIn("token", send_invoice(no_token).message)
        req.assert_not_called()
        self.assertEqual(Invoice.objects.get(pk=no_token.pk).status, "waiting")

    def test_token_is_encrypted_and_never_logged(self, req):
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        send_invoice(self.approved())
        self.assertNotIn(TOKEN, FbrCredential.objects.get().token_encrypted)
        self.assertEqual(FbrCredential.objects.get().token, TOKEN)
        self.assertEqual(FbrApiLog.objects.count(), 2)
        for entry in FbrApiLog.objects.all():
            self.assertNotIn(TOKEN, entry.request_body + entry.response_body + entry.path)

    def test_log_cannot_change(self, req):
        entry = FbrApiLog.objects.create(company=self.company, method="GET", path="/x")
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()


@patch("fbr.client.requests.request")
class ScreenTests(Base):
    def test_setup_never_shows_token(self, req):
        response = self.client.get(reverse("fbr_setup"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, TOKEN)
        self.assertContains(response, "SN001")

    def test_save_token_replaces_and_refuses_junk(self, req):
        self.client.post(reverse("fbr_save_token"), {"token": "has space"})
        self.assertEqual(FbrCredential.objects.get().token, TOKEN)
        self.client.post(reverse("fbr_save_token"), {"token": "new-token-abcdefgh"})
        self.assertEqual(FbrCredential.objects.get().token, "new-token-abcdefgh")
        self.assertEqual(FbrCredential.objects.count(), 1)

    def test_scenarios_must_be_real_codes(self, req):
        self.client.post(reverse("fbr_save_scenarios"), {"scenarios": "SN001, SN999"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.sandbox_scenarios, "SN001, SN002")
        self.client.post(reverse("fbr_save_scenarios"), {"scenarios": "sn005 SN006"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.sandbox_scenarios, "SN005, SN006")

    def test_connection_results(self, req):
        for answer, text in [(reply([{"stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB"}]), "1 provinces"),
                             (reply(status=401, text="no"), "refused the token"),
                             (requests.exceptions.ConnectTimeout(), "IP may not be approved")]:
            req.side_effect = [answer]
            self.assertContains(self.client.post(reverse("fbr_test"), follow=True), text)

    def test_download_and_use_lists(self, req):
        req.side_effect = lambda m, url, **k: reply(
            [{"stateProvinceCode": 7, "stateProvinceDesc": "PUNJAB"}] if "provinces" in url else
            [{"hS_CODE": "9404.9000", "description": "Quilts"}] if "itemdesc" in url else
            [{"transactioN_TYPE_ID": 18, "transactioN_DESC": "Goods at standard rate"}] if "transtype" in url else
            [{"uoM_ID": 13, "description": "KG"}] if "uom" in url else [])
        self.client.post(reverse("fbr_download"))
        self.assertEqual(RefList.objects.count(), 6)
        page = self.client.get(reverse("product_new"))
        self.assertContains(page, 'list="dl-hs_code"')
        self.assertContains(page, "9404.9000")
        req.side_effect = [reply([{"ratE_ID": 1, "ratE_DESC": "18%", "ratE_VALUE": 18}])]
        page = self.client.get(reverse("fbr_rates"), {"tt": "18", "pr": "7"})
        self.assertContains(page, "18%")
        self.assertEqual(req.call_args.kwargs["params"]["transTypeId"], "18")
        self.assertRegex(req.call_args.kwargs["params"]["date"], r"^\d{2}-[A-Z][a-z]{2}-\d{4}$")

    def test_approve_button_sends_with_chosen_scenario(self, req):
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        inv = self.invoice()
        response = self.client.post(reverse("invoice_approve", args=[inv.pk]), {"scenario": "SN002"}, follow=True)
        self.assertContains(response, "7000007DI1747119701593")
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.scenario_id), ("accepted", "SN002"))
        self.assertEqual(json.loads(FbrApiLog.objects.first().request_body)["scenarioId"], "SN002")
        self.assertContains(self.client.get(reverse("fbr_setup")), inv.number)

    def test_scenario_outside_assigned_is_ignored(self, req):
        inv = self.invoice()
        self.client.post(reverse("invoice_approve", args=[inv.pk]), {"scenario": "SN099"})
        req.assert_not_called()
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.scenario_id), ("waiting", ""))

    def test_rejected_invoice_can_be_edited_and_resent(self, req):
        req.side_effect = [reply(INVALID_ITEM)]
        inv = self.invoice()
        self.client.post(reverse("invoice_approve", args=[inv.pk]), {"scenario": "SN001"})
        inv.refresh_from_db()
        self.assertEqual(inv.status, "rejected")
        lines = json.dumps([{"product": self.product.pk, "sold_by": "piece", "quantity": "2", "price": "1000", "discount": "0"}])
        self.client.post(reverse("invoice_edit", args=[inv.pk]), {"customer": self.reg.pk, "invoice_date": "2026-11-02", "lines": lines})
        inv.refresh_from_db()
        self.assertEqual((inv.status, inv.last_error), ("saved", ""))

    def test_other_companys_invoice_and_log_blocked(self, req):
        other = Company.objects.create(business_name="OTHER", ntn="7777777-1", province="P", address="A", invoice_prefix="OO")
        customer = Customer.objects.create(company=other, name="B", kind="unregistered", province="P", address="A")
        product = Product.objects.create(company=other, name="P", hs_code="9404.9000", uom="u", sale_type="s", rate_label="18%", rate_percent=Decimal("18"), price_per_piece=Decimal("1"))
        inv = create_invoice(company=other, customer=customer, invoice_date=date(2026, 11, 2), lines=[LineInput(product, "piece", "1", "", "1")])
        entry = FbrApiLog.objects.create(company=other, method="GET", path="/x")
        for name in ["invoice_send", "invoice_found", "invoice_not_found", "invoice_approve"]:
            self.assertEqual(self.client.post(reverse(name, args=[inv.pk])).status_code, 404, name)
        self.assertEqual(self.client.get(reverse("fbr_log", args=[entry.pk])).status_code, 404)
        req.assert_not_called()


@patch("fbr.client.requests.request")
class ProductionModeTests(Base):
    def _production(self):
        cred = FbrCredential(company=self.company, environment="production")
        cred.token = "prod-token-abcdefgh"
        cred.save()
        self.company.fbr_mode = "production"
        self.company.save()

    def test_stays_in_sandbox_until_deliberately_switched(self, req):
        self.client.post(reverse("fbr_mode"), {"mode": "production", "confirm": "yes"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.fbr_mode, "sandbox")
        cred = FbrCredential(company=self.company, environment="production")
        cred.token = "prod-token-abcdefgh"
        cred.save()
        self.client.post(reverse("fbr_mode"), {"mode": "production"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.fbr_mode, "sandbox")
        self.client.post(reverse("fbr_mode"), {"mode": "production", "confirm": "yes"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.fbr_mode, "production")
        self.client.post(reverse("fbr_mode"), {"mode": "sandbox"})
        self.company.refresh_from_db()
        self.assertEqual(self.company.fbr_mode, "sandbox")

    def test_production_send_uses_real_urls_and_no_scenario(self, req):
        self._production()
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        inv = approve_invoice(self.invoice(), self.user, "")
        self.assertTrue(send_invoice(inv).ok)
        urls = [c.args[1] for c in req.call_args_list]
        self.assertTrue(urls[0].endswith("/validateinvoicedata"))
        self.assertTrue(urls[1].endswith("/postinvoicedata"))
        self.assertEqual(req.call_args.kwargs["headers"]["Authorization"], "Bearer prod-token-abcdefgh")
        self.assertNotIn("scenarioId", json.loads(req.call_args.kwargs["data"]))
        inv.refresh_from_db()
        self.assertTrue(inv.is_final)
        page = self.client.get(reverse("invoice_print", args=[inv.pk]))
        self.assertContains(page, "fbr-digital-invoicing.png")
        self.assertContains(page, 'viewBox="0 0 25 25"')

    def test_sandbox_send_uses_sandbox_token_even_with_production_saved(self, req):
        cred = FbrCredential(company=self.company, environment="production")
        cred.token = "prod-token-abcdefgh"
        cred.save()
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        inv = self.approved()
        send_invoice(inv)
        self.assertEqual(req.call_args.kwargs["headers"]["Authorization"], f"Bearer {TOKEN}")
        self.assertTrue(req.call_args.args[1].endswith("_sb"))
        inv.refresh_from_db()
        self.assertFalse(inv.is_final)

    def test_demo_invoice_is_never_sent(self, req):
        self._production()
        inv = create_invoice(company=self.company, customer=self.reg, invoice_date=date(2026, 11, 2),
                             lines=[LineInput(self.product, "piece", "1", "", "1000")], your_reference="DEMO order")
        inv = approve_invoice(inv, self.user, "")
        self.assertIn("demo", send_invoice(inv).message)
        req.assert_not_called()

    def test_debit_note_payload_is_sent_with_reference(self, req):
        Invoice.objects.update()
        original = self.invoice()
        Invoice.objects.filter(pk=original.pk).update(status="accepted", fbr_invoice_number="7000007DI1", fbr_environment="sandbox", invoice_date=date.today())
        original.refresh_from_db()
        note = create_invoice(company=self.company, customer=self.reg, invoice_date=date.today(),
                              lines=[LineInput(self.product, "piece", "1", "", "1000")], original=original)
        note = approve_invoice(note, self.user, "SN001")
        req.side_effect = [reply(VALID_CHECK), reply(VALID_POST)]
        send_invoice(note)
        sent = json.loads(req.call_args.kwargs["data"])
        self.assertEqual((sent["invoiceType"], sent["invoiceRefNo"]), ("Debit Note", "7000007DI1"))


@patch("fbr.client.requests.request")
class LookupTests(Base):
    def test_units_and_sro_calls_match_the_spec(self, req):
        req.side_effect = [reply([{"uoM_ID": 77, "description": "Square Meter"}])]
        page = self.client.get(reverse("fbr_lookups"), {"kind": "uom", "hs": "5904.9000", "an": "3"})
        self.assertContains(page, "Square Meter")
        self.assertEqual(req.call_args.kwargs["params"], {"hs_code": "5904.9000", "annexure_id": "3"})
        self.assertTrue(req.call_args.args[1].endswith("/pdi/v2/HS_UOM"))
        req.side_effect = [reply([{"srO_ID": 7, "srO_DESC": "Zero Rated Gas"}])]
        page = self.client.get(reverse("fbr_lookups"), {"kind": "sro", "rate": "413", "pr": "7"})
        self.assertContains(page, "Zero Rated Gas")
        self.assertRegex(req.call_args.kwargs["params"]["date"], r"^\d{2}-[A-Z][a-z]{2}-\d{4}$")
        req.side_effect = [reply([{"srO_ITEM_ID": 17853, "srO_ITEM_DESC": "50"}])]
        page = self.client.get(reverse("fbr_lookups"), {"kind": "item", "sro": "389"})
        self.assertContains(page, "17853")
        self.assertRegex(req.call_args.kwargs["params"]["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_failed_lookup_shows_a_message(self, req):
        req.side_effect = [requests.exceptions.ConnectTimeout()]
        self.assertContains(self.client.get(reverse("fbr_lookups"), {"kind": "uom", "hs": "1"}), "didn&#x27;t answer")

    def test_customer_check_saves_fbr_answers(self, req):
        req.side_effect = [reply({"statuscode": "00", "REGISTRATION_NO": "7654321", "REGISTRATION_TYPE": "Registered"}),
                           reply({"status code": "00", "status": "Active"})]
        self.client.post(reverse("fbr_check_customer", args=[self.reg.pk]))
        self.reg.refresh_from_db()
        self.assertEqual((self.reg.fbr_reg_type, self.reg.fbr_status), ("Registered", "Active"))
        self.assertFalse(self.reg.fbr_mismatch)
        self.assertEqual(json.loads(req.call_args_list[0].kwargs["data"]), {"Registration_No": "7654321"})
        self.assertEqual(json.loads(req.call_args_list[1].kwargs["data"])["regno"], "7654321")
        self.assertContains(self.client.get(reverse("customer_list")), "Registered, Active")

    def test_mismatch_warns(self, req):
        req.side_effect = [reply({"statuscode": "01", "REGISTRATION_NO": "7654321", "REGISTRATION_TYPE": "unregistered"}),
                           reply({"status code": "01", "status": "In-Active"})]
        response = self.client.post(reverse("fbr_check_customer", args=[self.reg.pk]), follow=True)
        self.assertContains(response, "doesn&#x27;t match")
        self.reg.refresh_from_db()
        self.assertTrue(self.reg.fbr_mismatch)

    def test_get_refused_falls_back_to_post(self, req):
        req.side_effect = [reply(status=405, text="no"), reply({"REGISTRATION_TYPE": "Registered"}),
                           reply(status=405, text="no"), reply({"status": "Active"})]
        self.client.post(reverse("fbr_check_customer", args=[self.reg.pk]))
        self.assertEqual([c.args[0] for c in req.call_args_list], ["GET", "POST", "GET", "POST"])

    def test_network_failure_changes_nothing_and_other_company_blocked(self, req):
        req.side_effect = [requests.exceptions.ConnectTimeout(), requests.exceptions.ConnectTimeout()]
        self.client.post(reverse("fbr_check_customer", args=[self.reg.pk]))
        self.reg.refresh_from_db()
        self.assertIsNone(self.reg.fbr_checked_at)
        other = Company.objects.create(business_name="OTHER", ntn="7777777-1", province="P", address="A", invoice_prefix="OO")
        customer = Customer.objects.create(company=other, name="B", kind="registered", ntn_cnic="1111111", province="P", address="A")
        self.assertEqual(self.client.post(reverse("fbr_check_customer", args=[customer.pk])).status_code, 404)
