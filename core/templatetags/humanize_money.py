from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def rupees(value):
    """Show money with commas and 2 decimals, using Decimal so nothing is rounded by float."""
    return f"{Decimal(value or 0):,.2f}"
