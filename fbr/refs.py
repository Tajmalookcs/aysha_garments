"""Download and read FBR's lists."""

from . import client
from .constants import REFERENCE_LISTS, SALE_TYPE_TO_RATE
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
