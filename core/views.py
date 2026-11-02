from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import admin_required, company_required
from .forms import CompanyForm, CustomerForm, FirstRunForm, NewUserForm, ProductForm
from .middleware import SESSION_KEY
from .models import Company, Customer, Membership, Product


def _brand():
    """One company shows its own name on the login screen; several show a neutral one."""
    companies = list(Company.objects.all()[:2])
    return companies[0].business_name.title() if len(companies) == 1 else "Digital Invoicing"


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
    return render(request, "core/first_run.html", {"form": form})


@require_POST
@company_required
def switch_company(request):
    wanted = request.POST.get("company")
    if any(str(m.company_id) == wanted for m in request.memberships):
        request.session[SESSION_KEY] = int(wanted)
    return redirect("dashboard")


# ---------- Products (admins only, because they carry the tax details) ----------

@admin_required
def product_list(request):
    return render(request, "core/product_list.html", {"products": request.company.products.all()})


@admin_required
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

@admin_required
def company_edit(request):
    form = CompanyForm(request.POST or None, instance=request.company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Company details saved.")
        return redirect("company_edit")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": "Company details",
        "save_label": "Save company",
        "extra_link": ("company_new", "Add another company"),
    })


@admin_required
def company_new(request):
    form = CompanyForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            company = form.save()
            Membership.objects.create(user=request.user, company=company, role=Membership.Role.ADMIN)
        request.session[SESSION_KEY] = company.pk
        messages.success(request, f"{company.business_name} added. You're now working in this company.")
        return redirect("product_list")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": "Add a company",
        "intro": "Each company has its own products, customers, invoices and numbering.",
        "save_label": "Add company",
        "back": "company_edit",
    })


# ---------- Users ----------

@admin_required
def user_list(request):
    return render(request, "core/user_list.html", {"members": request.company.memberships.select_related("user")})


@admin_required
def user_new(request):
    form = NewUserForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.create_user(form.cleaned_data["username"], password=form.cleaned_data["password"])
            Membership.objects.create(user=user, company=request.company, role=form.cleaned_data["role"])
        messages.success(request, f"{user.username} can now log in.")
        return redirect("user_list")
    return render(request, "core/form_page.html", {
        "form": form,
        "title": "Add a user",
        "intro": "Operators can make invoices and manage customers. Admins can also change products, users and company details.",
        "save_label": "Add user",
        "back": "user_list",
    })


@require_POST
@admin_required
def user_remove(request, pk):
    member = get_object_or_404(Membership, pk=pk, company=request.company)
    if member.user_id == request.user.pk:
        messages.error(request, "You can't remove your own access.")
    else:
        name = member.user.username
        member.delete()
        messages.success(request, f"{name} no longer has access to {request.company.business_name}.")
    return redirect("user_list")
