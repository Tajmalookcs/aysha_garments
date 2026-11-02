from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Company, Customer, Membership, Product


def _use_fbr_list(form, field, name):
    """Suggest FBR's downloaded values on a field, while still allowing typing."""
    from fbr.refs import values

    options = values(name)
    if options:
        form.fields[field].widget.attrs["list"] = f"dl-{field}"
        form.datalists = {**getattr(form, "datalists", {}), f"dl-{field}": options}


class StyledMixin:
    """Apply the Bootstrap classes used across the app."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            else:
                widget.attrs["class"] = "form-control"
            if isinstance(widget, forms.Textarea):
                widget.attrs["rows"] = 2


class CompanyForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ["business_name", "ntn_cnic", "strn", "province", "address", "phone", "invoice_prefix"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _use_fbr_list(self, "province", "provinces")


class ProductForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name", "description_for_fbr", "hs_code", "uom", "sale_type", "rate_label",
            "rate_percent", "further_tax_percent", "fed_percent", "fixed_notified_value",
            "sro_schedule_no", "sro_item_serial_no", "price_per_piece", "is_active",
        ]

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        _use_fbr_list(self, "hs_code", "hs_codes")
        _use_fbr_list(self, "uom", "uom")
        _use_fbr_list(self, "sale_type", "transaction_types")

    def clean_name(self):
        name = self.cleaned_data["name"]
        clash = Product.objects.filter(company=self.company, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("A product with this name already exists.")
        return name


class CustomerForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "kind", "ntn_cnic", "province", "country", "address", "phone", "is_active"]

    def __init__(self, *args, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        _use_fbr_list(self, "province", "provinces")

    def clean_name(self):
        name = self.cleaned_data["name"]
        clash = Customer.objects.filter(company=self.company, name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("A customer with this name already exists.")
        return name

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        ntn = data.get("ntn_cnic")
        if kind == Customer.Kind.REGISTERED and not ntn and "ntn_cnic" not in self.errors:
            self.add_error("ntn_cnic", "Enter the NTN or CNIC for a registered buyer.")
        # PRAL error 0058: self-invoicing is rejected.
        if ntn and ntn == self.company.ntn_cnic:
            self.add_error("ntn_cnic", "The buyer can't have the same NTN or CNIC as your company.")
        if kind == Customer.Kind.FOREIGN:
            if not data.get("country"):
                self.add_error("country", "Enter the buyer's country.")
        elif kind:
            if not data.get("province"):
                self.add_error("province", "Enter the buyer's province.")
            if not data.get("address"):
                self.add_error("address", "Enter the buyer's address.")
        return data


class NewUserForm(StyledMixin, forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, help_text="At least 8 characters, not only numbers.")
    role = forms.ChoiceField(choices=Membership.Role.choices)

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password


class FirstRunForm(CompanyForm):
    username = forms.CharField(max_length=150, label="Your username")
    password = forms.CharField(widget=forms.PasswordInput, label="Your password",
                               help_text="At least 8 characters, not only numbers.")

    class Meta(CompanyForm.Meta):
        pass

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password
