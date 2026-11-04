from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def quantity(value):
    """Show a quantity with commas and without trailing zeros."""
    text = f"{Decimal(value or 0).normalize():,f}"
    return text


@register.filter
def rupees(value):
    """Show money with commas and 2 decimals, using Decimal so nothing is rounded by float."""
    return f"{Decimal(value or 0):,.2f}"


@register.filter
def strn(value):
    """STRN is saved as 13 digits. On screen and in print it shows as 00-00-0000-000-00."""
    text = str(value or "")
    if len(text) == 13 and text.isdigit():
        return f"{text[:2]}-{text[2:4]}-{text[4:8]}-{text[8:11]}-{text[11:]}"
    return text
