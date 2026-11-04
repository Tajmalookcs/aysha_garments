"""Validate then post an approved invoice, and record exactly what happened.

The invoice is moved to CHECK before anything is sent, and only leaves it once the outcome
is known. If the app stops mid-send, or two clicks arrive together, it can't post twice.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from billing.models import Invoice
from core import licence

from . import client
from .constants import POST_PATH, VALIDATE_PATH
from .parsing import INVALID, VALID, parse
from .payload import build_payload, group_items


@dataclass
class SendResult:
    ok: bool
    message: str


def _finish(invoice, status, *, code="", error=""):
    invoice.status = status
    invoice.last_error_code = code
    invoice.last_error = error
    invoice.save(update_fields=["status", "last_error_code", "last_error"])


def _mark_offline(invoice):
    """Rule 150XC: FBR couldn't be reached, so this invoice is now an offline invoice."""
    invoice.issued_offline = True
    invoice.save(update_fields=["issued_offline"])


def send_invoice(invoice) -> SendResult:
    company = invoice.company
    mode = company.fbr_mode
    state = licence.status(company)
    if state.expired:
        return SendResult(False, "The demo has ended, so invoices can't be sent. Register this copy to continue.")
    if mode == "production" and not state.registered:
        return SendResult(False, "Production needs a registered copy. Register this copy first.")
    if mode == "sandbox" and not invoice.scenario_id:
        return SendResult(False, "Choose a scenario before sending to the sandbox.")
    if invoice.your_reference.startswith("DEMO"):
        return SendResult(False, "This is a demo invoice, so it can't be sent to FBR.")
    items = list(invoice.items.all())
    if any(i.hs_code == "0000.0000" for i in items):
        return SendResult(False, "This invoice has sample products, so it can't be sent to FBR.")
    if invoice.buyer_kind == "foreign":
        return SendResult(False, "Export invoices can't be sent until FBR's rules for foreign buyers are confirmed.")
    try:
        client.token_for(company)
    except client.NoToken as exc:
        return SendResult(False, str(exc))

    with transaction.atomic():
        claimed = Invoice.objects.filter(pk=invoice.pk, status=Invoice.Status.WAITING).update(
            status=Invoice.Status.CHECK, fbr_environment=mode
        )
    if not claimed:
        return SendResult(False, "This invoice is already being sent, or isn't waiting to send.")
    invoice.refresh_from_db()
    payload = build_payload(invoice, invoice.scenario_id if mode == "sandbox" else "")

    # Step 1: validate. It issues no IRN, so any failure here is safe to retry.
    checked = client.call(invoice.company, "POST", VALIDATE_PATH[mode], payload=payload, invoice=invoice)
    problem = _http_problem(checked)
    if problem:
        if checked.network_error:
            _mark_offline(invoice)
        _finish(invoice, Invoice.Status.WAITING, error=problem)
        return SendResult(False, problem)
    parsed = parse(checked.data, needs_irn=False)
    if parsed.outcome == INVALID:
        _finish(invoice, Invoice.Status.REJECTED, code=parsed.error_code, error=parsed.message)
        return SendResult(False, f"FBR refused this invoice. {parsed.message}")
    if parsed.outcome != VALID:
        message = "FBR's validation reply wasn't clear, so the invoice wasn't posted. Check the FBR log."
        _finish(invoice, Invoice.Status.WAITING, error=message)
        return SendResult(False, message)

    # Step 2: post. From here, an unclear result might mean FBR has already issued an IRN.
    posted = client.call(invoice.company, "POST", POST_PATH[mode], payload=payload, invoice=invoice)
    if posted.not_sent or posted.http_status == 401:
        if posted.not_sent:
            _mark_offline(invoice)
        message = _http_problem(posted) or "Couldn't reach FBR."
        _finish(invoice, Invoice.Status.WAITING, error=message)
        return SendResult(False, message)
    if posted.http_status == 200:
        parsed = parse(posted.data, needs_irn=True)
        if parsed.outcome == VALID:
            _accept(invoice, parsed)
            where = "FBR sandbox" if mode == "sandbox" else "FBR"
            return SendResult(True, f"{where} accepted invoice {invoice.number}. IRN: {parsed.irn}")
        if parsed.outcome == INVALID:
            _finish(invoice, Invoice.Status.REJECTED, code=parsed.error_code, error=parsed.message)
            return SendResult(False, f"FBR refused this invoice. {parsed.message}")
    message = ("The result of sending is unknown, and FBR may have issued an IRN. "
               "Check the invoice dashboard in IRIS before doing anything else.")
    _finish(invoice, Invoice.Status.CHECK, error=message)
    return SendResult(False, message)


def _http_problem(result) -> str:
    if result.network_error:
        return f"{result.network_error}. Check the internet connection and try again."
    if result.http_status == 401:
        return "FBR refused the token. Check the token in FBR setup, and that your IP is approved in IRIS."
    if result.http_status != 200:
        return f"FBR returned an error (HTTP {result.http_status}). Try again later."
    return ""


@transaction.atomic
def _accept(invoice, parsed):
    invoice.status = Invoice.Status.ACCEPTED
    invoice.fbr_invoice_number = parsed.irn
    invoice.fbr_dated = parsed.dated
    invoice.posted_at = timezone.now()
    invoice.last_error_code = ""
    invoice.last_error = ""
    invoice.save()
    # FBR numbers the items as they were sent, and combined lines share one item.
    for position, lines in enumerate(group_items(invoice.items.all()), start=1):
        number = parsed.item_numbers.get(str(position), "")
        if number:
            for item in lines:
                item.fbr_invoice_no = number
                item.save(update_fields=["fbr_invoice_no"])


def record_found_in_iris(invoice, irn: str) -> SendResult:
    """The person found this invoice in IRIS after an unknown result."""
    irn = irn.strip()
    if invoice.status != Invoice.Status.CHECK:
        return SendResult(False, "This invoice isn't waiting for a check in IRIS.")
    if not irn or not irn.replace("-", "").isalnum() or len(irn) > 40:
        return SendResult(False, "Enter the invoice number exactly as IRIS shows it.")
    invoice.status = Invoice.Status.ACCEPTED
    invoice.fbr_invoice_number = irn
    invoice.fbr_environment = invoice.fbr_environment or "sandbox"
    invoice.posted_at = timezone.now()
    invoice.last_error_code = ""
    invoice.last_error = ""
    invoice.save()
    return SendResult(True, f"Invoice {invoice.number} saved with IRN {irn}.")


def mark_not_found_in_iris(invoice) -> SendResult:
    """The person confirmed it isn't in IRIS, so sending again can't duplicate it."""
    if invoice.status != Invoice.Status.CHECK:
        return SendResult(False, "This invoice isn't waiting for a check in IRIS.")
    _finish(invoice, Invoice.Status.WAITING)
    return SendResult(True, f"Invoice {invoice.number} is ready to send again.")
