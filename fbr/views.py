import re

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from billing.models import Invoice
from core.decorators import admin_required, company_required
from core.models import Customer

from . import client, refs
from .constants import REFERENCE_LISTS, SCENARIOS
from .models import FbrCredential, RefList


def assigned_scenarios(company):
    return [c for c in re.split(r"[\s,]+", company.sandbox_scenarios.upper()) if c in SCENARIOS]


@admin_required
def setup(request):
    company = request.company
    credential = FbrCredential.objects.filter(company=company, environment="sandbox").first()
    production_credential = FbrCredential.objects.filter(company=company, environment="production").first()
    done = {}
    for inv in company.invoices.filter(status=Invoice.Status.ACCEPTED, fbr_environment="sandbox").order_by("id"):
        done.setdefault(inv.scenario_id, inv)
    scenarios = [
        {"code": c, "description": SCENARIOS[c][0], "sale_type": SCENARIOS[c][1], "invoice": done.get(c)}
        for c in assigned_scenarios(company)
    ]
    return render(request, "fbr/setup.html", {
        "credential": credential,
        "production_credential": production_credential,
        "scenarios": scenarios,
        "done_count": sum(1 for s in scenarios if s["invoice"]),
        "lists": [
            {"name": n, "row": RefList.objects.filter(name=n).first()} for n in REFERENCE_LISTS
        ],
        "logs": company.fbr_logs.all()[:30],
    })


@require_POST
@admin_required
def save_token(request):
    raw = request.POST.get("token", "").strip()
    environment = request.POST.get("environment", "sandbox")
    if environment not in FbrCredential.Environment.values:
        environment = "sandbox"
    if len(raw) < 10 or any(c.isspace() for c in raw):
        messages.error(request, "That doesn't look like a token. Copy it again from IRIS, with no spaces.")
        return redirect("fbr_setup")
    credential = FbrCredential.objects.filter(company=request.company, environment=environment).first() or FbrCredential(
        company=request.company, environment=environment)
    credential.token = raw
    credential.save()
    messages.success(request, f"{environment.title()} token saved and encrypted.")
    return redirect("fbr_setup")


@require_POST
@admin_required
def switch_mode(request):
    """Moving to production means real invoices, so it needs a token and a clear confirmation."""
    company = request.company
    wanted = request.POST.get("mode")
    if wanted == "sandbox":
        company.fbr_mode = "sandbox"
        company.save(update_fields=["fbr_mode"])
        messages.success(request, "Sandbox mode is on. Invoices you send are tests.")
    elif wanted == "production":
        if not FbrCredential.objects.filter(company=company, environment="production").exists():
            messages.error(request, "Save the production token first.")
        elif request.POST.get("confirm") != "yes":
            messages.error(request, "Tick the box to confirm that you want to send real invoices.")
        else:
            company.fbr_mode = "production"
            company.save(update_fields=["fbr_mode"])
            messages.success(request, "Production mode is on. Invoices you send are now real.")
    return redirect("fbr_setup")


@require_POST
@admin_required
def save_scenarios(request):
    entered = [c for c in re.split(r"[\s,]+", request.POST.get("scenarios", "").upper()) if c]
    unknown = [c for c in entered if c not in SCENARIOS]
    if unknown:
        messages.error(request, f"These aren't FBR scenario codes: {', '.join(unknown)}.")
    else:
        request.company.sandbox_scenarios = ", ".join(entered)
        request.company.save(update_fields=["sandbox_scenarios"])
        messages.success(request, "Scenarios saved.")
    return redirect("fbr_setup")


@require_POST
@admin_required
def test_connection(request):
    try:
        result = client.call(request.company, "GET", REFERENCE_LISTS["provinces"][0])
    except client.NoToken as exc:
        messages.error(request, str(exc))
        return redirect("fbr_setup")
    if result.http_status == 200 and isinstance(result.data, list):
        messages.success(request, f"Connected to FBR. It returned {len(result.data)} provinces.")
    elif result.http_status == 401:
        messages.error(request, "FBR refused the token. Check it in IRIS, and that your IP is approved.")
    elif result.network_error:
        messages.error(request, f"{result.network_error}. Your IP may not be approved yet. Check its status in IRIS.")
    else:
        messages.error(request, f"FBR returned HTTP {result.http_status}. Your IP may not be approved yet. Check its status in IRIS.")
    return redirect("fbr_setup")


@require_POST
@admin_required
def download_lists(request):
    try:
        saved, problems = refs.download_all(request.company)
    except client.NoToken as exc:
        messages.error(request, str(exc))
        return redirect("fbr_setup")
    if saved:
        messages.success(request, f"Downloaded {len(saved)} FBR lists.")
    if problems:
        messages.error(request, "Couldn't download: " + "; ".join(problems))
    return redirect("fbr_setup")


@admin_required
def rate_lookup(request):
    types = refs.rows("transaction_types")
    provinces = refs.rows("provinces")
    context = {"types": types, "provinces": provinces, "rates": None, "tt": "", "pr": "", "today": timezone.localdate()}
    tt, pr = request.GET.get("tt", ""), request.GET.get("pr", "")
    if tt and pr:
        context.update(tt=tt, pr=pr)
        try:
            result = refs.rates(request.company, on_date=context["today"], transaction_type_id=tt, province_code=pr)
        except client.NoToken as exc:
            messages.error(request, str(exc))
        else:
            if result.http_status == 200 and isinstance(result.data, list):
                context["rates"] = [
                    {"id": r.get("ratE_ID"), "desc": r.get("ratE_DESC"), "value": r.get("ratE_VALUE")} for r in result.data if isinstance(r, dict)
                ]
            else:
                messages.error(request, f"Couldn't get rates: {result.network_error or f'HTTP {result.http_status}'}.")
    return render(request, "fbr/rate_lookup.html", context)


@admin_required
def log_detail(request, pk):
    entry = get_object_or_404(request.company.fbr_logs, pk=pk)
    return render(request, "fbr/log_detail.html", {"entry": entry})


@admin_required
def lookups(request):
    kind = request.GET.get("kind", "")
    query = {k: request.GET.get(k, "").strip() for k in ("hs", "an", "rate", "pr", "sro")}
    context = {"kind": kind, "q": query, "rows": [], "asked": False, "provinces": refs.rows("provinces")}
    today = timezone.localdate()
    call, keys = None, None
    if kind == "uom" and query["hs"]:
        call = lambda: refs.units_for_hs(request.company, hs_code=query["hs"], annexure_id=query["an"] or "3")
        keys = ("uoM_ID", "description")
    elif kind == "sro" and query["rate"] and query["pr"]:
        call = lambda: refs.sro_schedules(request.company, on_date=today, rate_id=query["rate"], province_code=query["pr"])
        keys = ("srO_ID", "srO_DESC")
    elif kind == "item" and query["sro"]:
        call = lambda: refs.sro_items(request.company, on_date=today, sro_id=query["sro"])
        keys = ("srO_ITEM_ID", "srO_ITEM_DESC")
    if call:
        try:
            result = call()
        except client.NoToken as exc:
            messages.error(request, str(exc))
        else:
            if result.http_status == 200 and isinstance(result.data, list):
                context["asked"] = True
                context["rows"] = [
                    {"id": r.get(keys[0]), "desc": r.get(keys[1])} for r in result.data if isinstance(r, dict)
                ]
            else:
                messages.error(request, f"FBR didn't answer: {result.network_error or f'HTTP {result.http_status}'}.")
    return render(request, "fbr/lookups.html", context)


@require_POST
@company_required
def check_customer(request, pk):
    """Ask FBR about a buyer's registration and active status, and keep the answer for offline use."""
    customer = get_object_or_404(Customer, pk=pk, company=request.company)
    if not customer.ntn_cnic:
        messages.error(request, "Add this customer's NTN or CNIC first.")
        return redirect("customer_list")
    today = timezone.localdate()
    try:
        reg_type, reg_result = refs.registration_type(request.company, customer.ntn_cnic)
        status, status_result = refs.active_status(request.company, customer.ntn_cnic, today)
    except client.NoToken as exc:
        messages.error(request, str(exc))
        return redirect("customer_list")
    if not reg_type and not status:
        problem = reg_result.network_error or f"HTTP {reg_result.http_status}"
        messages.error(request, f"FBR didn't answer: {problem}. Nothing was changed.")
        return redirect("customer_list")
    customer.fbr_reg_type = reg_type
    customer.fbr_status = status
    customer.fbr_checked_at = timezone.now()
    customer.save(update_fields=["fbr_reg_type", "fbr_status", "fbr_checked_at"])
    report = f"{customer.name}: {reg_type or 'registration type not returned'}, {status or 'status not returned'}."
    if customer.fbr_mismatch:
        messages.warning(request, f"{report} This doesn't match the buyer type saved here, so please check it.")
    else:
        messages.success(request, report)
    return redirect("customer_list")
