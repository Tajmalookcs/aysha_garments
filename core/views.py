import time

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .decorators import company_required
from . import licence
from .forms import CompanyForm, CustomerForm, DeveloperPasswordForm, FirstRunForm, ProductForm
from .models import Company, Customer, Membership, Product


def page_expired(request, reason=""):
    """Shown when a form was opened before a login change, or in another tab."""
    return render(request, "page_expired.html", status=403)


def _brand():
    """The login screen shows the company's own name."""
    company = Company.objects.first()
    return company.business_name.title() if company else "Digital Invoicing"


class StyledLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control form-control-lg"


class LoginView(auth_views.LoginView):
    template_name = "core/login.html"
    authentication_form = StyledLoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["brand"] = _brand()
        return context


def first_run(request):
    User = get_user_model()
    if User.objects.exists():
        return redirect("login")
    form = FirstRunForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            company = form.save()
            user = User.objects.create_user(form.cleaned_data["username"], password=form.cleaned_data["password"])
            Membership.objects.create(user=user, company=company, role=Membership.Role.ADMIN)
        login(request, user)
        messages.success(request, f"{company.business_name} is set up. Add your products next.")
        return redirect("product_list")
    return render(request, "core/first_run.html", {"form": form, "ready": bool(licence.demo_password_hash())})


# ---------- Products ----------

@company_required
def product_list(request):
    return render(request, "core/product_list.html", {"products": request.company.products.all()})


@company_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk, company=request.company) if pk else Product(company=request.company)
    form = ProductForm(request.POST or None, instance=product, company=request.company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{product.name} saved.")
        return redirect("product_list")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": product.name if pk else "New product",
        "intro": "Tax details are set here once. Get the HS code, unit, sale type and rate from the client, "
                 "and check them against FBR's lists.",
        "save_label": "Save product",
        "back": "product_list",
    })


# ---------- Customers ----------

@company_required
def customer_list(request):
    return render(request, "core/customer_list.html", {"customers": request.company.customers.all()})


@company_required
def customer_edit(request, pk=None):
    customer = get_object_or_404(Customer, pk=pk, company=request.company) if pk else Customer(company=request.company)
    form = CustomerForm(request.POST or None, instance=customer, company=request.company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{customer.name} saved.")
        return redirect("customer_list")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": customer.name if pk else "New customer",
        "save_label": "Save customer",
        "back": "customer_list",
    })


# ---------- Company ----------

UNLOCK_KEY = "developer_unlocked_until"
UNLOCK_SECONDS = 10 * 60


def _developer_unlocked(request):
    return request.session.get(UNLOCK_KEY, 0) > time.time()


@company_required
def company_edit(request):
    """Only the developer changes these details, so the page asks for the developer password."""
    if not _developer_unlocked(request):
        form = DeveloperPasswordForm(request.POST or None, company=request.company)
        if request.method == "POST" and form.is_valid():
            request.session[UNLOCK_KEY] = time.time() + UNLOCK_SECONDS
            return redirect("company_edit")
        return render(request, "core/form_page.html", {
            "form": form,
            "title": "Company details",
            "intro": "Only the developer can open this page.",
            "save_label": "Open company details",
        })
    form = CompanyForm(request.POST or None, instance=request.company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Company details saved.")
        return redirect("company_edit")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": "Company details",
        "save_label": "Save company",
    })


# ---------- Registration ----------

@company_required
def registration(request):
    if request.method == "POST":
        upload = request.FILES.get("licence")
        if upload is None:
            messages.error(request, "Choose the registration file first.")
        else:
            try:
                details = licence.install(request.company, upload.read(licence.MAX_FILE_BYTES + 1))
            except licence.LicenceError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, f"This copy is registered to {details['business_name']}. The demo has ended.")
        return redirect("registration")
    return render(request, "core/registration.html")
