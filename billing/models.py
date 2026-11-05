"""Invoices. The local invoice is the record; the FBR number (IRN) is added when FBR accepts it.

Details are copied onto the invoice at sale time, so later edits to a company,
customer or product never change an invoice that was already made. There is
deliberately no edit or delete screen.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Company, Customer, Product

ZERO = Decimal("0.00")


class Invoice(models.Model):
    class Status(models.TextChoices):
        SAVED = "saved", "Saved: needs approval"
        WAITING = "waiting", "Approved: waiting to send"
        HELD = "held", "Held: export rules not confirmed"
        CHECK = "check", "Unknown result: check in IRIS"
        ACCEPTED = "accepted", "Accepted by FBR"
        REJECTED = "rejected", "Rejected by FBR"

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="invoices")
    class Type(models.TextChoices):
        SALE = "Sale Invoice", "Sale Invoice"
        DEBIT_NOTE = "Debit Note", "Debit Note"

    number = models.CharField(max_length=30)
    invoice_type = models.CharField(max_length=15, choices=Type.choices, default=Type.SALE)
    original = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="debit_notes")
    invoice_ref_no = models.CharField("Original IRN", max_length=40, blank=True)
    local_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invoice_date = models.DateField()
    your_reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SAVED, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_invoices",
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    # Seller, as it was at sale time.
    seller_name = models.CharField(max_length=200)
    seller_ntn_cnic = models.CharField(max_length=13)
    seller_ntn = models.CharField(max_length=9, blank=True)
    seller_strn = models.CharField(max_length=20, blank=True)
    seller_province = models.CharField(max_length=60)
    seller_address = models.TextField()

    # Buyer, as it was at sale time.
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    buyer_name = models.CharField(max_length=200)
    buyer_kind = models.CharField(max_length=15, choices=Customer.Kind.choices)
    buyer_ntn_cnic = models.CharField(max_length=13, blank=True)
    buyer_strn = models.CharField(max_length=30, blank=True)
    buyer_province = models.CharField(max_length=60, blank=True)
    buyer_country = models.CharField(max_length=60, blank=True)
    buyer_address = models.TextField(blank=True)

    # Filled in by the FBR connection in a later build.
    fbr_invoice_number = models.CharField("IRN", max_length=40, blank=True, db_index=True)
    fbr_dated = models.CharField(max_length=40, blank=True)
    fbr_environment = models.CharField(max_length=10, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    scenario_id = models.CharField(max_length=5, blank=True)
    last_error_code = models.CharField(max_length=10, blank=True)
    last_error = models.TextField(blank=True)
    # Rule 150XC: an invoice issued during a failure must be identified as offline.
    issued_offline = models.BooleanField(default=False)

    total_excl_tax = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total_sales_tax = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total_further_tax = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total_fed = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total_discount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["company", "number"], name="unique_invoice_number_per_company")]

    def __str__(self):
        return self.number

    @property
    def is_final(self):
        """Only a production invoice FBR has accepted, with an IRN, can ever be final.

        A sandbox or demo acceptance is never a real invoice.
        """
        return (
            self.status == self.Status.ACCEPTED
            and bool(self.fbr_invoice_number)
            and self.fbr_environment == "production"
        )

    @property
    def print_copy(self):
        """Which printed copy this invoice gets. Only production acceptance is ever final."""
        if self.is_final:
            return {"kind": "final", "title": "", "stamp": "", "notice": ""}
        if self.status == self.Status.ACCEPTED and self.fbr_environment == "sandbox":
            return {"kind": "sandbox", "title": "Sandbox test", "stamp": "SANDBOX TEST",
                    "notice": "Test only. Accepted in FBR's sandbox. This is not a real invoice."}
        if self.your_reference.startswith("DEMO"):
            return {"kind": "demo", "title": "Demo", "stamp": "DEMO ONLY",
                    "notice": "Demo data only. This is not a real invoice."}
        return {"kind": "pending", "title": "Pending FBR", "stamp": "PENDING FBR",
                "notice": "Not a final invoice. FBR has not issued an IRN for this invoice."}

    @property
    def status_label(self):
        if self.status == self.Status.ACCEPTED:
            if self.fbr_environment == "sandbox":
                return "Accepted in FBR sandbox (test)"
            if self.fbr_environment != "production":
                return "Accepted (demo only)"
        if self.status == self.Status.REJECTED and self.your_reference.startswith("DEMO"):
            return "Rejected (demo only)"
        return self.get_status_display()

    @property
    def is_debit_note(self):
        return self.invoice_type == self.Type.DEBIT_NOTE

    @property
    def can_add_debit_note(self):
        """A sale invoice with a real or sandbox IRN, within FBR's 180 days (error 0034)."""
        if self.invoice_type != self.Type.SALE or self.status != self.Status.ACCEPTED:
            return False
        if self.fbr_environment not in ("sandbox", "production") or not self.fbr_invoice_number:
            return False
        return (timezone.localdate() - self.invoice_date).days <= 180

    @property
    def can_edit(self):
        """Editing and deleting stop once an invoice is approved, so what FBR gets is what was approved."""
        return self.status in (self.Status.SAVED, self.Status.HELD, self.Status.REJECTED)

    @property
    def can_approve(self):
        return self.status in (self.Status.SAVED, self.Status.REJECTED)

    @property
    def has_pack_lines(self):
        return any(i.sold_by == InvoiceItem.SoldBy.PACK for i in self.items.all())

    @property
    def total_kg(self):
        return sum((i.quantity for i in self.items.all() if i.quantity_unit == "KG"), Decimal("0"))

    @property
    def total_quantity(self):
        return sum((i.display_quantity for i in self.items.all()), Decimal("0"))

    @property
    def can_send(self):
        return self.status == self.Status.WAITING

    @property
    def status_class(self):
        return {"accepted": "ok", "rejected": "bad"}.get(self.status, "wait")


class InvoiceItem(models.Model):
    class SoldBy(models.TextChoices):
        KG = "kg", "KG"
        PACK = "pack", "Pack and KG"
        PIECE = "piece", "Piece"
        LOT = "lot", "Lot"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL)
    line_no = models.PositiveIntegerField()

    # Product details, as they were at sale time.
    description = models.CharField(max_length=255)
    hs_code = models.CharField(max_length=9)
    uom = models.CharField(max_length=100)
    sale_type = models.CharField(max_length=150)
    rate_label = models.CharField(max_length=100)
    rate_percent = models.DecimalField(max_digits=6, decimal_places=2)

    sold_by = models.CharField(max_length=5, choices=SoldBy.choices, default=SoldBy.KG)
    pack_unit = models.CharField(max_length=20, blank=True)
    entered_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    pieces_per_lot = models.PositiveIntegerField(null=True, blank=True)
    quantity = models.DecimalField("Total quantity", max_digits=14, decimal_places=4)
    price_per_piece = models.DecimalField(max_digits=14, decimal_places=2)

    value_excl_tax = models.DecimalField(max_digits=16, decimal_places=2)
    sales_tax = models.DecimalField(max_digits=16, decimal_places=2)
    further_tax = models.DecimalField(max_digits=16, decimal_places=2)
    fed_payable = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    fixed_notified_value = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    sro_schedule_no = models.CharField(max_length=50, blank=True)
    sro_item_serial_no = models.CharField(max_length=50, blank=True)
    fbr_invoice_no = models.CharField(max_length=50, blank=True)
    discount = models.DecimalField(max_digits=16, decimal_places=2, default=ZERO)
    total = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["line_no"]

    def __str__(self):
        return f"{self.invoice.number} line {self.line_no}"

    @property
    def quantity_unit(self):
        if self.sold_by in (self.SoldBy.KG, self.SoldBy.PACK):
            return "KG"
        return "piece" if self.quantity == 1 else "pieces"

    @property
    def display_quantity(self):
        return self.entered_quantity if self.sold_by == self.SoldBy.PACK else self.quantity

    @property
    def display_unit(self):
        if self.sold_by == self.SoldBy.PACK:
            return self.pack_unit
        if self.sold_by == self.SoldBy.PIECE and self.uom.strip().lower() not in {"", "numbers, pieces, units"}:
            return self.uom
        return self.quantity_unit
