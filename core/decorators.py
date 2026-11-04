from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def company_required(view):
    """The user must be logged in and belong to the company."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.company is None:
            raise PermissionDenied("This account is not linked to a company.")
        return view(request, *args, **kwargs)

    return wrapper


def working_copy_required(view):
    """New invoices and sending stop when the demo ends. Old data stays open."""

    @wraps(view)
    @company_required
    def wrapper(request, *args, **kwargs):
        if request.licence.expired:
            messages.error(request, "The demo has ended, so invoices can't be made or sent. Your data is safe. Register this copy to continue.")
            return redirect("registration")
        return view(request, *args, **kwargs)

    return wrapper
