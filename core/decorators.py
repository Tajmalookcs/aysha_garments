import time
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

UNLOCK_KEY = "developer_unlocked_until"
UNLOCK_SECONDS = 10 * 60


def developer_unlocked(request):
    return request.session.get(UNLOCK_KEY, 0) > time.time()


def unlock_developer(request):
    request.session[UNLOCK_KEY] = time.time() + UNLOCK_SECONDS


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


def developer_required(view):
    """FBR setup is for the developer, because a wrong change can stop real invoices going to FBR."""

    @wraps(view)
    @company_required
    def wrapper(request, *args, **kwargs):
        if developer_unlocked(request):
            return view(request, *args, **kwargs)
        from .forms import DeveloperPasswordForm

        data = request.POST if "developer_password" in request.POST else None
        form = DeveloperPasswordForm(data, company=request.company)
        if form.is_valid():
            unlock_developer(request)
            return redirect("fbr_setup")
        return render(request, "core/form_page.html", {
            "form": form,
            "title": "FBR setup",
            "intro": "Only the developer can open this page.",
            "save_label": "Open FBR setup",
        })

    return wrapper
