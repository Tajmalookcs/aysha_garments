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
