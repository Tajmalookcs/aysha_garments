"""Builds the invoice JSON, using the field names and order of the PRAL spec and IRIS sample."""

from decimal import Decimal


def _n(value) -> float:
    # JSON numbers. Values with up to 4 decimals keep their exact value through float here.
    return float(Decimal(value))


def item_key(record) -> tuple:
    """What FBR checks on an item. Works for a product or an invoice line."""
    return (record.hs_code, record.sale_type, record.rate_label, record.uom, record.sro_schedule_no,
            record.sro_item_serial_no, record.fixed_notified_value)


def group_items(items) -> list:
    """The FBR items for an invoice, each a list of invoice lines.

    Pack lines that match on everything FBR checks go as one item, with their KG, value and tax
    added up. Pack lines that differ stay separate. Every other line is its own item.
    The sandbox accepted a combined item on 2026-11-04.
    """
    groups, by_key = [], {}
    for item in items:
        key = item_key(item)
        if item.sold_by == "pack" and key in by_key:
            by_key[key].append(item)
            continue
        group = [item]
        groups.append(group)
        if item.sold_by == "pack":
            by_key[key] = group
    return groups


def _fbr_item(lines) -> dict:
    first = lines[0]
    add = lambda field: sum((getattr(line, field) for line in lines), Decimal("0"))
    return {
        "hsCode": first.hs_code,
        "productDescription": ", ".join(dict.fromkeys(line.description for line in lines)),
        "rate": first.rate_label,
        "uoM": first.uom,
        "quantity": _n(add("quantity")),
        "totalValues": _n(add("total")),
        "valueSalesExcludingST": _n(add("value_excl_tax") - add("discount")),
        "fixedNotifiedValueOrRetailPrice": _n(first.fixed_notified_value),
        "salesTaxApplicable": _n(add("sales_tax")),
        "salesTaxWithheldAtSource": 0.0,
        "extraTax": "",
        "furtherTax": _n(add("further_tax")),
        "sroScheduleNo": first.sro_schedule_no,
        "fedPayable": _n(add("fed_payable")),
        "discount": _n(add("discount")),
        "saleType": first.sale_type,
        "sroItemSerialNo": first.sro_item_serial_no,
    }


def build_payload(invoice, scenario_id: str = "") -> dict:
    """The invoice JSON. scenarioId is sandbox only, so it's left out in production.

    To confirm in sandbox: the spec doesn't say whether valueSalesExcludingST is before or
    after discount. It's sent after discount, the same base the tax is worked out on.
    extraTax is an empty string, as in the sample shown in IRIS.
    """
    data = {
        "invoiceType": invoice.invoice_type,
        "invoiceDate": invoice.invoice_date.isoformat(),
        "sellerNTNCNIC": invoice.seller_ntn_cnic,
        "sellerBusinessName": invoice.seller_name,
        "sellerProvince": invoice.seller_province,
        "sellerAddress": invoice.seller_address,
        "buyerNTNCNIC": invoice.buyer_ntn_cnic,
        "buyerBusinessName": invoice.buyer_name,
        "buyerProvince": invoice.buyer_province,
        "buyerAddress": invoice.buyer_address,
        "buyerRegistrationType": "Registered" if invoice.buyer_kind == "registered" else "Unregistered",
        "invoiceRefNo": invoice.invoice_ref_no,
        # Not in PRAL's specification. In the sandbox on 2026-11-06, this filled Source Invoice No. in IRIS.
        "sourceInvoiceNo": invoice.number,
        "items": [_fbr_item(lines) for lines in group_items(invoice.items.all())],
    }
    if scenario_id:
        data["scenarioId"] = scenario_id
    return data
