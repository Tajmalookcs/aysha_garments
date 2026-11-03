"""Sales register: one row per invoice for a period, for reconciling against the monthly return."""

import csv
from datetime import date
from decimal import Decimal

from django.http import HttpResponse

from .models import Invoice

HEADERS = [
    "Invoice no.", "Date", "Buyer", "Buyer type", "NTN or CNIC", "Province or country",
    "Value before discount", "Discount", "Value after discount", "Sales tax", "Further tax", "FED",
    "Total", "IRN", "FBR status",
]
TOTAL_FIELDS = ["total_excl_tax", "total_discount", "total_sales_tax", "total_further_tax", "total_fed", "grand_total"]


def parse_period(raw_from, raw_to, today):
    """Returns (start, end, error). Defaults to the current month so far."""
    error = ""
    try:
        start = date.fromisoformat(raw_from) if raw_from else today.replace(day=1)
        end = date.fromisoformat(raw_to) if raw_to else today
    except ValueError:
        return today.replace(day=1), today, "Enter valid dates. Showing this month instead."
    if start > end:
        return today.replace(day=1), today, "The start date is after the end date. Showing this month instead."
    return start, end, error


def filtered(company, start, end, status=""):
    invoices = company.invoices.filter(invoice_date__range=(start, end))
    if status in Invoice.Status.values:
        invoices = invoices.filter(status=status)
    return invoices.order_by("invoice_date", "number")


def totals(invoices):
    # Added up here in Decimal, because SQLite's SUM works in floating point.
    rows = list(invoices)
    data = {"count": len(rows)}
    for field in TOTAL_FIELDS:
        data[field] = sum((getattr(i, field) for i in rows), Decimal("0.00"))
    data["after_discount"] = data["total_excl_tax"] - data["total_discount"]
    return data


def _safe(text):
    """Stop a spreadsheet treating a name like =SUM(...) as a formula."""
    text = str(text)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def csv_response(invoices, start, end):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="sales-register-{start}-to-{end}.csv"'
    response.write("\ufeff")  # So Excel reads it as UTF-8.
    writer = csv.writer(response)
    writer.writerow(HEADERS)
    for i in invoices:
        writer.writerow([
            _safe(i.number), i.invoice_date.isoformat(), _safe(i.buyer_name), i.get_buyer_kind_display(),
            _safe(i.buyer_ntn_cnic), _safe(i.buyer_country or i.buyer_province),
            i.total_excl_tax, i.total_discount, i.total_excl_tax - i.total_discount,
            i.total_sales_tax, i.total_further_tax, i.total_fed, i.grand_total,
            _safe(i.fbr_invoice_number), i.status_label,
        ])
    t = totals(invoices)
    writer.writerow(["Total", "", f"{t['count']} invoices", "", "", "", t["total_excl_tax"], t["total_discount"],
                     t["after_discount"], t["total_sales_tax"], t["total_further_tax"], t["total_fed"], t["grand_total"], "", ""])
    return response
