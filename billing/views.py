import json
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Min, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from django.views.decorators.http import require_POST

from core.decorators import company_required
from fbr.sending import mark_not_found_in_iris, record_found_in_iris, send_invoice
from fbr.views import assigned_scenarios

from .models import Invoice
from .services import (
    InvoiceError,
    LineInput,
    approve_invoice,
    create_invoice,
    delete_invoice,
    next_invoice_number,
    parse_date,
    update_invoice,
)


@company_required
def dashboard(request):
    invoices = request.company.invoices.all()
    today = timezone.localdate()
    waiting = invoices.filter(status=Invoice.Status.WAITING)
    stats = invoices.filter(invoice_date=today).aggregate(
        count=Count("id"),
        total=Sum("grand_total"),
        accepted=Count("id", filter=Q(status=Invoice.Status.ACCEPTED)),
    )
    return render(request, "billing/dashboard.html", {
        "has_invoices": invoices.exists(),
        "saved_count": invoices.filter(status=Invoice.Status.SAVED).count(),
        "waiting_count": waiting.count(),
        "oldest_waiting": waiting.aggregate(t=Min("created_at"))["t"],
        "held_count": invoices.filter(status=Invoice.Status.HELD).count(),
        "rejected_count": invoices.filter(status=Invoice.Status.REJECTED).count(),
        "today_count": stats["count"],
        "today_total": stats["total"] or Decimal("0"),
        "today_accepted": stats["accepted"],
        "recent": invoices[:10],
        "has_products": request.company.products.filter(is_active=True).exists(),
    })


@company_required
def invoice_list(request):
    invoices = request.company.invoices.all()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        invoices = invoices.filter(Q(number__icontains=q) | Q(buyer_name__icontains=q))
    if status in Invoice.Status.values:
        invoices = invoices.filter(status=status)
    return render(request, "billing/invoice_list.html", {
        "invoices": invoices[:300],
        "q": q,
        "status": status,
        "statuses": Invoice.Status.choices,
    })


def _lines_from_post(request, products):
    try:
        raw_lines = json.loads(request.POST.get("lines") or "[]")
    except json.JSONDecodeError:
        raise InvoiceError("The items couldn't be read. Add them again.")
    if not isinstance(raw_lines, list):
        raise InvoiceError("The items couldn't be read. Add them again.")
    products = {p.pk: p for p in products}
    lines = []
    for row in raw_lines:
        try:
            product = products[int(row.get("product"))]
        except (AttributeError, KeyError, TypeError, ValueError):
            raise InvoiceError("Choose a product for every item.")
        lines.append(LineInput(
            product=product,
            sold_by=row.get("sold_by", "piece"),
            quantity=row.get("quantity", ""),
            pieces_per_lot=row.get("pieces_per_lot", ""),
            price=row.get("price", ""),
            discount=row.get("discount", "0"),
        ))
    return lines


def _invoice_form(request, invoice=None):
    """The new invoice and edit invoice screen."""
    company = request.company
    products = company.products.filter(is_active=True)
    customers = company.customers.filter(is_active=True)
    initial_lines = []
    selected_customer = selected_date = your_reference = ""

    if invoice:
        # Keep records already on this invoice, even if they've since been made unavailable.
        products = company.products.filter(Q(is_active=True) | Q(pk__in=invoice.items.values("product"))).distinct()
        customers = company.customers.filter(Q(is_active=True) | Q(pk=invoice.customer_id))
        initial_lines = [
            {
                "product": item.product_id,
                "sold_by": item.sold_by,
                "quantity": f"{item.entered_quantity.normalize():f}",
                "pieces_per_lot": item.pieces_per_lot or "",
                "price": str(item.price_per_piece),
                "discount": str(item.discount),
            }
            for item in invoice.items.all()
        ]
        selected_customer = str(invoice.customer_id)
        selected_date = invoice.invoice_date.isoformat()
        your_reference = invoice.your_reference

    if request.method == "POST":
        selected_customer = request.POST.get("customer", "")
        selected_date = request.POST.get("invoice_date", "")
        your_reference = request.POST.get("your_reference", "").strip()[:100]
        try:
            initial_lines = json.loads(request.POST.get("lines") or "[]")
        except json.JSONDecodeError:
            initial_lines = []
        try:
            customer = customers.filter(pk=selected_customer or None).first()
            if customer is None:
                raise InvoiceError("Choose a buyer.")
            details = {
                "customer": customer,
                "invoice_date": parse_date(selected_date),
                "lines": _lines_from_post(request, products),
                "your_reference": your_reference,
            }
            if invoice:
                saved = update_invoice(invoice, **details)
                messages.success(request, f"Invoice {saved.number} updated. Approve it to send it to FBR.")
            else:
                saved = create_invoice(company=company, user=request.user, **details)
                messages.success(request, f"Invoice {saved.number} saved on this computer. Approve it to send it to FBR.")
        except (InvoiceError, ValueError) as exc:
            messages.error(request, str(exc))
        else:
            return redirect("invoice_detail", pk=saved.pk)

    return render(request, "billing/invoice_form.html", {
        "invoice": invoice,
        "customers": customers,
        "has_products": products.exists(),
        "next_number": next_invoice_number(company),
        "today": timezone.localdate().isoformat(),
        "selected_customer": selected_customer,
        "selected_date": selected_date,
        "your_reference": your_reference,
        "products_data": [
            {
                "id": p.pk,
                "name": p.name,
                "price": str(p.price_per_piece),
                "rate": str(p.rate_percent),
                "further": str(p.further_tax_percent),
                "fed": str(p.fed_percent),
                "hs": p.hs_code,
            }
            for p in products
        ],
        "customers_data": {str(c.pk): c.kind for c in customers},
        "initial_lines": initial_lines,
    })


@company_required
def invoice_new(request):
    return _invoice_form(request)


@company_required
def invoice_edit(request, pk):
    invoice = get_object_or_404(request.company.invoices.prefetch_related("items"), pk=pk)
    if not invoice.can_edit:
        messages.error(request, f"Invoice {invoice.number} is approved, so it can't be changed.")
        return redirect("invoice_detail", pk=invoice.pk)
    return _invoice_form(request, invoice)


@company_required
def invoice_delete(request, pk):
    invoice = get_object_or_404(request.company.invoices, pk=pk)
    if not invoice.can_edit:
        messages.error(request, f"Invoice {invoice.number} is approved, so it can't be deleted.")
        return redirect("invoice_detail", pk=invoice.pk)
    if request.method == "POST":
        number = delete_invoice(invoice)
        messages.success(request, f"Invoice {number} deleted. The next new invoice can use its number.")
        return redirect("invoice_list")
    return render(request, "billing/invoice_delete.html", {"invoice": invoice})


@company_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(request.company.invoices.prefetch_related("items"), pk=pk)
    scenarios = assigned_scenarios(request.company)
    suggested = invoice.scenario_id or {"registered": "SN001", "unregistered": "SN002"}.get(invoice.buyer_kind, "")
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "scenarios": scenarios,
        "suggested": suggested,
    })


def _chosen_scenario(request):
    wanted = request.POST.get("scenario", "")
    return wanted if wanted in assigned_scenarios(request.company) else ""


def _report(request, result):
    (messages.success if result.ok else messages.error)(request, result.message)


@require_POST
@company_required
def invoice_approve(request, pk):
    """Approve and send: the button saved invoices use."""
    invoice = get_object_or_404(request.company.invoices, pk=pk)
    try:
        invoice = approve_invoice(invoice, request.user, _chosen_scenario(request))
    except InvoiceError as exc:
        messages.error(request, str(exc))
    else:
        result = send_invoice(invoice)
        invoice.refresh_from_db()
        if result.ok:
            messages.success(request, result.message)
        elif invoice.status == Invoice.Status.WAITING:
            messages.warning(request, f"Invoice {invoice.number} is approved. {result.message}")
    return redirect("invoice_detail", pk=invoice.pk)


@require_POST
@company_required
def invoice_send(request, pk):
    invoice = get_object_or_404(request.company.invoices, pk=pk)
    if invoice.can_send:
        chosen = _chosen_scenario(request)
        if chosen and chosen != invoice.scenario_id:
            invoice.scenario_id = chosen
            invoice.save(update_fields=["scenario_id"])
        _report(request, send_invoice(invoice))
    return redirect("invoice_detail", pk=invoice.pk)


@require_POST
@company_required
def invoice_found(request, pk):
    invoice = get_object_or_404(request.company.invoices, pk=pk)
    _report(request, record_found_in_iris(invoice, request.POST.get("irn", "")))
    return redirect("invoice_detail", pk=invoice.pk)


@require_POST
@company_required
def invoice_not_found(request, pk):
    invoice = get_object_or_404(request.company.invoices, pk=pk)
    _report(request, mark_not_found_in_iris(invoice))
    return redirect("invoice_detail", pk=invoice.pk)
