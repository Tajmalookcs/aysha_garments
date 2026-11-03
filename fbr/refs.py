"""Download and read FBR's lists."""

from . import client
from .constants import GET_REG_TYPE, HS_UOM, REFERENCE_LISTS, SALE_TYPE_TO_RATE, SRO_ITEM, SRO_SCHEDULE, STATL
from .models import RefList


def download_all(company):
    """Returns (rows saved per list, list of problems)."""
    saved, problems = {}, []
    for name, (path, key) in REFERENCE_LISTS.items():
        result = client.call(company, "GET", path)
        if result.http_status == 200 and isinstance(result.data, list):
            RefList.objects.update_or_create(name=name, defaults={"data": result.data})
            saved[name] = len(result.data)
        else:
            problems.append(f"{name}: {result.network_error or f'HTTP {result.http_status}'}")
    return saved, problems


def rows(name):
    ref = RefList.objects.filter(name=name).first()
    return ref.data if ref else []


def values(name):
    key = REFERENCE_LISTS[name][1]
    return sorted({str(r[key]) for r in rows(name) if isinstance(r, dict) and r.get(key) is not None})


def rates(company, *, on_date, transaction_type_id, province_code):
    """Spec 5.8. The date format is 24-Feb-2024."""
    return client.call(company, "GET", SALE_TYPE_TO_RATE, params={
        "date": on_date.strftime("%d-%b-%Y"),
        "transTypeId": transaction_type_id,
        "originationSupplier": province_code,
    })


def units_for_hs(company, *, hs_code, annexure_id):
    """Spec 5.9."""
    return client.call(company, "GET", HS_UOM, params={"hs_code": hs_code, "annexure_id": annexure_id})


def sro_schedules(company, *, on_date, rate_id, province_code):
    """Spec 5.7. The date format is 04-Feb-2024."""
    return client.call(company, "GET", SRO_SCHEDULE, params={
        "rate_id": rate_id,
        "date": on_date.strftime("%d-%b-%Y"),
        "origination_supplier_csv": province_code,
    })


def sro_items(company, *, on_date, sro_id):
    """Spec 5.10. The date format is 2025-03-25."""
    return client.call(company, "GET", SRO_ITEM, params={"date": on_date.isoformat(), "sro_id": sro_id})


def _json_lookup(company, path, body):
    """Spec 5.11 and 5.12 name the method as Get but show a JSON body, so POST is tried if GET is refused."""
    result = client.call(company, "GET", path, payload=body)
    if result.http_status == 405:
        result = client.call(company, "POST", path, payload=body)
    return result


def registration_type(company, number):
    """Spec 5.12. Returns (text, result). Text is empty if FBR's reply wasn't readable."""
    result = _json_lookup(company, GET_REG_TYPE, {"Registration_No": number})
    text = result.data.get("REGISTRATION_TYPE", "") if isinstance(result.data, dict) else ""
    return str(text or ""), result


def active_status(company, number, on_date):
    """Spec 5.11. Note the space in the reply's "status code" key. Returns (text, result)."""
    result = _json_lookup(company, STATL, {"regno": number, "date": on_date.isoformat()})
    text = result.data.get("status", "") if isinstance(result.data, dict) else ""
    return str(text or ""), result
