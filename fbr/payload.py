"""Builds the invoice JSON, using the field names and order of the PRAL spec and IRIS sample."""

from decimal import Decimal


def _n(value) -> float:
    # JSON numbers. Values with up to 4 decimals keep their exact value through float here.
    return float(Decimal(value))


def build_payload(invoice, scenario_id: str) -> dict:
    """Sandbox payload. scenarioId must be left out in production.

    To confirm in sandbox: the spec doesn't say whether valueSalesExcludingST is before or
    after discount. It's sent after discount, the same base the tax is worked out on.
    extraTax is an empty string, as in the sample shown in IRIS.
    """
    return {
        "invoiceType": "Sale Invoice",
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
        "invoiceRefNo": "",
        "scenarioId": scenario_id,
        "items": [
            {
                "hsCode": item.hs_code,
                "productDescription": item.description,
                "rate": item.rate_label,
                "uoM": item.uom,
                "quantity": _n(item.quantity),
                "totalValues": _n(item.total),
                "valueSalesExcludingST": _n(item.value_excl_tax - item.discount),
                "fixedNotifiedValueOrRetailPrice": _n(item.fixed_notified_value),
                "salesTaxApplicable": _n(item.sales_tax),
                "salesTaxWithheldAtSource": 0.0,
                "extraTax": "",
                "furtherTax": _n(item.further_tax),
                "sroScheduleNo": item.sro_schedule_no,
                "fedPayable": _n(item.fed_payable),
                "discount": _n(item.discount),
                "saleType": item.sale_type,
                "sroItemSerialNo": item.sro_item_serial_no,
            }
            for item in invoice.items.all()
        ],
    }
