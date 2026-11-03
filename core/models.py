"""Companies, their users, products and customers.

Every business record belongs to one company. Views must always read through
``request.company`` so one client's data can never appear for another.
"""

from django.conf import settings
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

# PRAL spec v1.12: seller is 7 or 13 digits.
seller_reg_validator = RegexValidator(r"^(\d{7}|\d{13})$", "Enter 7 or 13 digits, with no dashes.")
# PRAL error 0002: buyer is a 13 digit CNIC or a 7 or 9 digit NTN.
buyer_reg_validator = RegexValidator(r"^(\d{7}|\d{9}|\d{13})$", "Enter 7, 9 or 13 digits, with no dashes.")
hs_code_validator = RegexValidator(r"^\d{4}\.\d{4}$", "Use the format 0000.0000.")
# PRAL errors 0088 and 0173: letters and digits, hyphens only between them.
prefix_validator = RegexValidator(r"^[A-Za-z0-9]+$", "Use letters and digits only.")


class Company(models.Model):
    business_name = models.CharField(
        max_length=200, unique=True,
        help_text="Exactly as registered with FBR. This is the name sent to FBR.",
    )
    ntn_cnic = models.CharField(
        "NTN or CNIC", max_length=13, validators=[seller_reg_validator],
        help_text="7 digit NTN or 13 digit CNIC, with no dashes.",
    )
    strn = models.CharField("STRN", max_length=20, blank=True)
    province = models.CharField(max_length=60)
    address = models.TextField()
    phone = models.CharField(max_length=60, blank=True)
    invoice_prefix = models.CharField(
        max_length=10, default="INV", validators=[prefix_validator],
        help_text="Invoice numbers will look like AG-000001.",
    )
    sandbox_scenarios = models.CharField(max_length=200, blank=True)
    fbr_mode = models.CharField(max_length=10, default="sandbox", editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["business_name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.business_name


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        OPERATOR = "operator", "Operator"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OPERATOR)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "company"], name="one_membership_per_company")]
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user} at {self.company} ({self.role})"


class Product(models.Model):
    """Tax details live here so operators never type them on an invoice."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=200)
    description_for_fbr = models.CharField(
        "Description for FBR", max_length=255, blank=True,
        help_text="Leave blank to use the product name.",
    )
    hs_code = models.CharField("HS code", max_length=9, validators=[hs_code_validator])
    uom = models.CharField("Unit reported to FBR", max_length=100, help_text="Must be a unit FBR allows for this HS code.")
    sale_type = models.CharField(max_length=150, help_text="The FBR sale type for this product.")
    rate_label = models.CharField(
        "Rate as FBR writes it", max_length=100,
        help_text="The exact FBR rate text. Confirm it with the client before use.",
    )
    rate_percent = models.DecimalField(
        "Sales tax rate (%)", max_digits=6, decimal_places=2, validators=[MinValueValidator(0)],
    )
    further_tax_percent = models.DecimalField(
        "Further tax rate (%)", max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Applied to unregistered buyers only.",
    )
    fed_percent = models.DecimalField(
        "FED rate (%)", max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Leave at 0 unless FED applies to this product.",
    )
    fixed_notified_value = models.DecimalField(
        "Fixed or retail price for FBR", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)],
        help_text="Leave at 0 unless FBR notifies one for this product.",
    )
    sro_schedule_no = models.CharField("SRO schedule no.", max_length=50, blank=True, help_text="Only if this sale falls under an SRO.")
    sro_item_serial_no = models.CharField("SRO item serial no.", max_length=50, blank=True, help_text="Only if this sale falls under an SRO.")
    price_per_piece = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    is_active = models.BooleanField("Available on new invoices", default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_product_name_per_company")]

    def __str__(self):
        return self.name


class Customer(models.Model):
    class Kind(models.TextChoices):
        REGISTERED = "registered", "Registered"
        UNREGISTERED = "unregistered", "Unregistered"
        FOREIGN = "foreign", "Foreign (export)"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customers")
    name = models.CharField("Business or person name", max_length=200)
    kind = models.CharField("Buyer type", max_length=15, choices=Kind.choices, default=Kind.REGISTERED)
    ntn_cnic = models.CharField(
        "NTN or CNIC", max_length=13, blank=True, validators=[buyer_reg_validator],
        help_text="Required for registered buyers. 7, 9 or 13 digits, with no dashes.",
    )
    province = models.CharField(max_length=60, blank=True, help_text="Required unless the buyer is foreign.")
    country = models.CharField(max_length=60, blank=True, help_text="For foreign buyers.")
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=60, blank=True)
    is_active = models.BooleanField("Available on new invoices", default=True)
    # FBR's latest answers about this buyer, kept for offline use.
    fbr_reg_type = models.CharField(max_length=30, blank=True, editable=False)
    fbr_status = models.CharField(max_length=30, blank=True, editable=False)
    fbr_checked_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "name"], name="unique_customer_name_per_company")]

    def __str__(self):
        return self.name

    @property
    def fbr_mismatch(self):
        """True when FBR's answer disagrees with the buyer type saved here."""
        answer = self.fbr_reg_type.strip().lower()
        if answer == "registered":
            return self.kind != self.Kind.REGISTERED
        if answer == "unregistered":
            return self.kind == self.Kind.REGISTERED
        return False
