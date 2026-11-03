import django.core.validators
from django.db import migrations, models

NTN = django.core.validators.RegexValidator("^\\d{7}-\\d$", "Enter the NTN as 0000000-0.")
CNIC = django.core.validators.RegexValidator("^\\d{13}$", "Enter 13 digits, with no dashes.")


def split_registration(apps, schema_editor):
    """A 13 digit value was a CNIC. A 7 digit NTN is kept, and needs its check digit added under Company."""
    Company = apps.get_model("core", "Company")
    for company in Company.objects.all():
        old = company.ntn_cnic
        if len(old) == 13:
            company.cnic = old
        elif len(old) == 7:
            company.ntn = old
        company.save(update_fields=["ntn", "cnic"])


class Migration(migrations.Migration):
    dependencies = [("core", "0004_company_fbr_mode_customer_fbr_checked_at_and_more")]

    operations = [
        migrations.AddField(
            model_name="company", name="ntn",
            field=models.CharField("NTN", default="", max_length=9, validators=[NTN],
                                   help_text="Required. Use the format 0000000-0. This is what prints on invoices."),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="company", name="cnic",
            field=models.CharField("CNIC", blank=True, max_length=13, validators=[CNIC],
                                   help_text="Optional. 13 digits, with no dashes. It doesn't print on invoices."),
        ),
        migrations.RunPython(split_registration, migrations.RunPython.noop),
        migrations.RemoveField(model_name="company", name="ntn_cnic"),
    ]
