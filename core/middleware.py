from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse

from . import licence
from .models import Membership


class FirstRunMiddleware:
    """Send a brand new install to the setup screen until the first admin exists."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        setup_url = reverse("first_run")
        if request.path != setup_url and not request.path.startswith("/static/"):
            if not get_user_model().objects.exists():
                return redirect(setup_url)
        return self.get_response(request)


class ActiveCompanyMiddleware:
    """Each install has one company, reached only through the user's own membership."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.company = None
        if request.user.is_authenticated:
            membership = Membership.objects.filter(user=request.user).select_related("company").first()
            if membership:
                request.company = membership.company
        return self.get_response(request)


class LicenceMiddleware:
    """Work out whether this copy is a demo, and how long it has left."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.licence = licence.status(request.company) if request.company else None
        return self.get_response(request)
