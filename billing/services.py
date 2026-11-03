"""Invoice numbering and tax calculation. All money is Decimal, never float."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from core.models import Company, Customer

from .models import Invoice, InvoiceItem

PAISA = Decimal("0.01")
LIMIT = Decimal("1000000000000")


class InvoiceError(ValueError):
    """A problem the operator can fix. The message is shown on screen."""


def money(value) -> Decimal:
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


def _number(raw, label, minimum=None, above=None) -> Decimal:
    try:
        value = Decimal(str(raw).strip() or "0")
    except InvalidOperation:
        raise InvoiceError(f"{label} must be a number.")
    if not value.is_finite() or abs(value) >= LIMIT:
        raise InvoiceError(f"{label} must be a number.")
    if minimum is not None and value < minimum:
        raise InvoiceError(f"{label} can't be less than {minimum}.")
    if above is not None and value <= above:
        raise InvoiceError(f"{label} must be more than {above}.")
    return value


@dataclass
class LineInput:
    product: object
    sold_by: str
    quantity: object
    pieces_per_lot: object
    price: object
    discount: object = "0"


def compute_line(line: LineInput, buyer_kind: str) -> dict:
    """Work out one invoice line. Tax is worked out after the discount, as the owner confirmed."""
    name = line.product.name
    entered = _number(line.quantity, f"Quantity for {name}", above=0)
    if entered.as_tuple().exponent < -4:
        raise InvoiceError(f"Quantity for {name} can have at most 4 decimal places.")

    per_lot = None
    pieces = entered
    if line.sold_by == InvoiceItem.SoldBy.LOT:
        per_lot_value = _number(line.pieces_per_lot, f"Pieces in each lot for {name}", above=0)
        if per_lot_value != per_lot_value.to_integral_value():
            raise InvoiceError(f"Pieces in each lot for {name} must be a whole number.")
        per_lot = int(per_lot_value)
        pieces = entered * per_lot
    elif line.sold_by != InvoiceItem.SoldBy.PIECE:
        raise InvoiceError(f"Choose piece or lot for {name}.")

    price = money(_number(line.price, f"Price for {name}", above=0))
    discount = money(_number(line.discount or "0", f"Discount for {name}", minimum=0))

    value = money(pieces * price)
    if discount > value:
        raise InvoiceError(f"Discount for {name} can't be more than its value.")
    taxable = value - discount
    sales_tax = money(taxable * line.product.rate_percent / 100)
    further_tax = Decimal("0.00")
    if buyer_kind == Customer.Kind.UNREGISTERED:
        further_tax = money(taxable * line.product.further_tax_percent / 100)
    fed = money(taxable * line.product.fed_percent / 100)

    return {
        "product": line.product,
        "description": line.product.description_for_fbr or line.product.name,
        "hs_code": line.product.hs_code,
        "uom": line.product.uom,
        "sale_type": line.product.sale_type,
        "rate_label": line.product.rate_label,
        "rate_percent": line.product.rate_percent,
        "sold_by": line.sold_by,
        "entered_quantity": entered,
        "pieces_per_lot": per_lot,
        "quantity": pieces,
        "price_per_piece": price,
        "value_excl_tax": value,
        "sales_tax": sales_tax,
        "further_tax": further_tax,
        "discount": discount,
        "fed_payable": fed,
        "fixed_notified_value": line.product.fixed_notified_value,
        "sro_schedule_no": line.product.sro_schedule_no,
        "sro_item_serial_no": line.product.sro_item_serial_no,
        "total": taxable + sales_tax + further_tax + fed,
    }


def parse_date(raw) -> date:
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        raise InvoiceError("Enter a valid invoice date.")


def next_invoice_number(company) -> str:
    """The company's lowest free number, so a deleted invoice's number is used again.

    Only unapproved invoices can be deleted, so a reused number has never reached FBR.
    """
    start = f"{company.invoice_prefix}-"
    used = set()
    for number in Invoice.objects.filter(company=company, number__startswith=start).values_list("number", flat=True):
        suffix = number[len(start):]
        if suffix.isdigit():
            used.add(int(suffix))
    seq = 1
    while seq in used:
        seq += 1
    return f"{start}{seq:06d}"


def _check_records(company, customer, lines):
    if customer.company_id != company.pk:
        raise InvoiceError("Choose one of this company's customers.")
    if not lines:
        raise InvoiceError("Add at least one item.")
    for line in lines:
        if line.product.company_id != company.pk:
            raise InvoiceError("Choose products from this company only.")


def _check_debit_note(original, customer, invoice_date, computed):
    """FBR's debit note rules, from errors 0026, 0029, 0034, 0035 and 0067."""
    if not original.can_add_debit_note:
        raise InvoiceError("A debit note needs an accepted sale invoice from the last 180 days.")
    if customer.pk != original.customer_id:
        raise InvoiceError("A debit note must be for the same buyer as the original invoice.")
    if invoice_date < original.invoice_date:
        raise InvoiceError("The debit note's date can't be before the original invoice's date.")
    if (invoice_date - original.invoice_date).days > 180:
        raise InvoiceError("A debit note is only allowed within 180 days of the original invoice.")
    tax = sum((c["sales_tax"] for c in computed), Decimal("0.00"))
    if tax > original.total_sales_tax:
        raise InvoiceError("The debit note's sales tax can't be more than the original invoice's sales tax.")


def _invoice_fields(company, customer, computed):
    """The details copied onto an invoice, so later edits elsewhere never change it."""
    zero = Decimal("0.00")
    is_foreign = customer.kind == Customer.Kind.FOREIGN
    return {
        "status": Invoice.Status.HELD if is_foreign else Invoice.Status.SAVED,
        "seller_name": company.business_name,
        "seller_ntn_cnic": company.ntn_cnic,
        "seller_strn": company.strn,
        "seller_province": company.province,
        "seller_address": company.address,
        "customer": customer,
        "buyer_name": customer.name,
        "buyer_kind": customer.kind,
        "buyer_ntn_cnic": customer.ntn_cnic,
        "buyer_province": customer.province,
        "buyer_country": customer.country,
        "buyer_address": customer.address,
        "total_excl_tax": sum((c["value_excl_tax"] for c in computed), zero),
        "total_sales_tax": sum((c["sales_tax"] for c in computed), zero),
        "total_further_tax": sum((c["further_tax"] for c in computed), zero),
        "total_fed": sum((c["fed_payable"] for c in computed), zero),
        "total_discount": sum((c["discount"] for c in computed), zero),
        "grand_total": sum((c["total"] for c in computed), zero),
    }


def _save_items(invoice, computed):
    InvoiceItem.objects.bulk_create(
        InvoiceItem(invoice=invoice, line_no=i, **c) for i, c in enumerate(computed, start=1)
    )


@transaction.atomic
def create_invoice(*, company, customer, invoice_date, lines, your_reference="", user=None, original=None) -> Invoice:
    """Save an invoice with its lines, and give it the company's lowest free number."""
    _check_records(company, customer, lines)
    computed = [compute_line(line, customer.kind) for line in lines]
    if original is not None:
        _check_debit_note(original, customer, invoice_date, computed)

    locked = Company.objects.select_for_update().get(pk=company.pk)

    invoice = Invoice.objects.create(
        company=locked,
        number=next_invoice_number(locked),
        invoice_date=invoice_date,
        your_reference=your_reference,
        created_by=user,
        invoice_type=Invoice.Type.DEBIT_NOTE if original else Invoice.Type.SALE,
        original=original,
        invoice_ref_no=original.fbr_invoice_number if original else "",
        **_invoice_fields(locked, customer, computed),
    )
    _save_items(invoice, computed)
    return invoice


@transaction.atomic
def update_invoice(invoice, *, customer, invoice_date, lines, your_reference="") -> Invoice:
    """Change an invoice that hasn't been approved. It keeps its number."""
    locked = Invoice.objects.select_for_update().select_related("company").get(pk=invoice.pk)
    if not locked.can_edit:
        raise InvoiceError(f"Invoice {locked.number} is approved, so it can't be changed.")
    _check_records(locked.company, customer, lines)
    computed = [compute_line(line, customer.kind) for line in lines]
    if locked.original_id:
        _check_debit_note(locked.original, customer, invoice_date, computed)

    for field, value in _invoice_fields(locked.company, customer, computed).items():
        setattr(locked, field, value)
    locked.invoice_date = invoice_date
    locked.approved_by = None
    locked.approved_at = None
    locked.last_error_code = ""
    locked.last_error = ""
    locked.your_reference = your_reference
    locked.save()
    locked.items.all().delete()
    _save_items(locked, computed)
    return locked


@transaction.atomic
def delete_invoice(invoice) -> str:
    """Delete an invoice that hasn't been approved. Its number becomes free for the next invoice."""
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not locked.can_edit:
        raise InvoiceError(f"Invoice {locked.number} is approved, so it can't be deleted.")
    number = locked.number
    locked.delete()
    return number


@transaction.atomic
def approve_invoice(invoice, user, scenario_id="") -> Invoice:
    """Release a saved invoice for sending. Nothing can reach FBR without this step."""
    locked = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if not locked.can_approve:
        raise InvoiceError(f"Invoice {locked.number} can't be approved. Its status is: {locked.get_status_display()}.")
    locked.status = Invoice.Status.WAITING
    locked.approved_by = user
    locked.approved_at = timezone.now()
    locked.scenario_id = scenario_id
    locked.last_error_code = ""
    locked.last_error = ""
    locked.save(update_fields=["status", "approved_by", "approved_at", "scenario_id", "last_error_code", "last_error"])
    return locked
