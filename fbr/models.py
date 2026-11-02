"""FBR token, downloaded lists and the permanent record of every call."""

from django.db import models

from core.models import Company

from .crypto import decrypt, encrypt


class FbrCredential(models.Model):
    """A PRAL token. It lets its holder act as the taxpayer, so it's stored encrypted."""

    class Environment(models.TextChoices):
        SANDBOX = "sandbox", "Sandbox"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="fbr_credentials")
    environment = models.CharField(max_length=10, choices=Environment.choices, default=Environment.SANDBOX)
    token_encrypted = models.TextField(editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["company", "environment"], name="one_token_per_environment")]

    def __str__(self):
        return f"{self.company} {self.environment} token"

    @property
    def token(self) -> str:
        return decrypt(self.token_encrypted)

    @token.setter
    def token(self, raw: str):
        self.token_encrypted = encrypt(raw.strip())


class RefList(models.Model):
    """A list downloaded from FBR, kept so it's available offline."""

    name = models.CharField(max_length=30, unique=True)
    data = models.JSONField(default=list)
    fetched_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class FbrApiLog(models.Model):
    """Append-only record of every call. The token is never stored here."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="fbr_logs")
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="fbr_logs")
    invoice_number = models.CharField(max_length=30, blank=True)
    method = models.CharField(max_length=6)
    path = models.CharField(max_length=200)
    request_body = models.TextField(blank=True)
    response_body = models.TextField(blank=True)
    http_status = models.IntegerField(null=True, blank=True)
    network_error = models.CharField(max_length=200, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"{self.method} {self.path} {self.http_status}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("FBR log entries can't be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("FBR log entries can't be deleted.")
